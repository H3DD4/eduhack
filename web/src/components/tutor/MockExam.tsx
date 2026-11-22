"use client";
/* Mock exam: timed, no help, answers kept on this device until submitted, then graded per part. */
import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { tutor, type Artifact } from "@/lib/tutor";
import { Dialog } from "@/components/ui";
import { ItemPlayer } from "./ItemPlayer";
import { Md, Tex } from "./Tex";

const fmt = (s: number) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

export function MockExam({ trackId, artifact, onNew }: { trackId: string; artifact: Artifact; onNew?: (a: Artifact) => void }) {
  const exam = artifact.content;
  const storeKey = `tf-mock-${artifact.id}`;
  const [started, setStarted] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [now, setNow] = useState(Date.now());
  const [result, setResult] = useState<any>(artifact.verification?.submission ? { score: artifact.verification.submission.score, out_of: artifact.verification.submission.out_of, parts: [] } : null);
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submitted = useRef(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storeKey) || "null");
      if (saved) { setStarted(saved.started); setAnswers(saved.answers || {}); }
    } catch { /* ignore */ }
  }, [storeKey]);
  useEffect(() => {
    if (!started || result) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [started, result]);
  const persist = (a: Record<string, any>, s = started) => { try { localStorage.setItem(storeKey, JSON.stringify({ started: s, answers: a })); } catch { /* ignore */ } };

  const total = exam.duration_min * 60;
  const elapsed = started ? Math.floor((now - started) / 1000) : 0;
  const left = Math.max(0, total - elapsed);

  const submit = async () => {
    if (submitted.current) return;
    submitted.current = true;
    setConfirm(false);
    try {
      const r = await tutor.submitMock(artifact.id, answers, elapsed);
      setResult(r);
      try { localStorage.removeItem(storeKey); } catch { /* ignore */ }
    } catch (e) { setErr((e as ApiError).message); submitted.current = false; }
  };
  useEffect(() => { if (started && left === 0 && !result) submit(); }); // time is up

  if (result) {
    return (
      <div className="space-y-5">
        <section className="hero p-7">
          <p className="text-meta">Mock exam result</p>
          <h2 className="text-page">{result.score} / {result.out_of}{result.grade_20 != null && result.out_of !== 20 ? `  ·  ${result.grade_20}/20` : ""}</h2>
          {result.elapsed_s != null && <p>Time used: {fmt(result.elapsed_s)} of {fmt(total)}</p>}
        </section>
        {result.parts?.map((p: any, i: number) => (
          <section key={i} className="game-card space-y-2 p-5">
            <h3 className="text-problem font-semibold">{p.title} — {p.score} / {p.points}</h3>
            {p.items.map((it: any, j: number) => (
              <div key={j} className="border-l-4 border-hl pl-3">
                <p className="text-meta">Question {j + 1}: {Math.round(it.score * it.points * 100) / 100} / {it.points}</p>
                {it.feedback && <Md text={it.feedback} />}
                {it.solution?.explanation && <Md text={it.solution.explanation} />}
                {it.solution?.answer && <p>Answer: <Tex text={String(it.solution.answer)} /></p>}
                {it.solution?.parts?.map((s: any) => <p key={s.label}><span className="font-mono">{s.label}</span> <Tex text={s.answer || ""} /></p>)}
              </div>
            ))}
          </section>
        ))}
        {onNew && <button className="btn-primary" onClick={async () => onNew(await tutor.newMock(trackId))}>New mock exam</button>}
      </div>
    );
  }

  if (!started) {
    return (
      <section className="hero space-y-4 p-7">
        <h2 className="text-page">{exam.title}</h2>
        <p>{fmt(total)} · {exam.total_points} points · {exam.parts.length} parts</p>
        <p>{exam.instructions}</p>
        <button className="btn-primary" onClick={() => { const s = Date.now(); setStarted(s); persist(answers, s); }}>Start the timer</button>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sticky top-2 z-10 flex items-center justify-between rounded-card border-2 border-ink bg-surface p-3 shadow-hard">
        <span className={`font-mono text-problem ${left < 300 ? "text-[color:var(--needs-review)]" : ""}`} aria-live="off">{fmt(left)}</span>
        <span className="text-meta">{Object.keys(answers).length} answered</span>
        <button className="btn-primary" onClick={() => setConfirm(true)}>Submit</button>
      </div>
      {err && <p className="rounded-control bg-review-surface p-3">{err}</p>}
      {exam.parts.map((p: any, pi: number) => (
        <section key={pi} className="space-y-3">
          <h3 className="text-section">{p.title} <span className="text-meta text-ink-muted">({p.points} pt)</span></h3>
          {p.items.map((it: any, i: number) => (
            <ItemPlayer key={it.id} trackId={trackId} item={it} index={i} mode="mock" value={answers[it.id]}
              onChange={(v) => { const a = { ...answers, [it.id]: v }; setAnswers(a); persist(a); }} />
          ))}
        </section>
      ))}
      <Dialog open={confirm} title="Submit the mock exam?" onClose={() => setConfirm(false)}>
        <p>You answered {Object.keys(answers).length} questions. You cannot change answers after submitting.</p>
        <div className="mt-4 flex gap-2">
          <button className="btn-secondary" onClick={() => setConfirm(false)}>Keep working</button>
          <button className="btn-primary" onClick={submit}>Submit</button>
        </div>
      </Dialog>
    </div>
  );
}
