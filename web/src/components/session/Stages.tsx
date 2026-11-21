"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { Dialog, ErrorBox, LiveRegion, MathText, OriginLabel } from "../ui";
import { RubricFeedback } from "./RubricFeedback";

/* ---------- recall (UC11 step 1): "I don't know" always valid; no grading ---------- */
export function RecallStage({ view, draft, onDraft, onContinue }: { view: any; draft: string; onDraft: (t: string) => void; onContinue: () => void }) {
  const [oriented, setOriented] = useState(false);
  return (
    <section className="space-y-4" aria-labelledby="st-h">
      <h2 id="st-h" tabIndex={-1} className="text-section">Before we start: what do you already remember about {view.concept.title.toLowerCase()}?</h2>
      <label htmlFor="recall" className="sr-only">Your recall</label>
      <textarea id="recall" className="field" value={draft} onChange={(e) => onDraft(e.target.value)} placeholder="Anything you remember — or nothing at all." />
      <p className="text-meta text-ink-muted">Not graded. It just helps you connect what comes next.</p>
      {oriented && <p className="hint-in rounded-detail bg-help-surface p-3">Orientation: this concept is about — {view.concept.objective}. The next step shows the cited course section.</p>}
      <div className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={onContinue}>Continue</button>
        <button className="btn-help" onClick={() => setOriented(true)} disabled={oriented}>I don&apos;t know</button>
      </div>
    </section>
  );
}

/* ---------- learn (UC11): cited chunk + different example + retrieval; reading = exposure only ---------- */
export function LearnStage({ view, subjectId, sessionId, draft, onDraft, onContinue }:
  { view: any; subjectId: string; sessionId: string; draft: string; onDraft: (t: string) => void; onContinue: () => void }) {
  const lesson = view.lesson;
  if (lesson?.locked) return <p>Lesson content is unavailable while an independent application is in progress.</p>;
  const ex = lesson?.excerpt;
  return (
    <section className="space-y-5" aria-labelledby="st-h">
      <h2 id="st-h" tabIndex={-1} className="text-section">What your course says</h2>
      {ex && !ex.tombstone ? (
        <figure className="card">
          <blockquote className="whitespace-pre-line text-problem"><MathText text={ex.text} /></blockquote>
          <figcaption className="mt-3 text-meta text-ink-muted">
            Cited from <Link className="underline" href={`/subjects/${subjectId}/resources/${ex.source_id}?page=${ex.page}&return=${encodeURIComponent(`/subjects/${subjectId}/sessions/${sessionId}`)}`}>{ex.filename}, page {ex.page}</Link>
          </figcaption>
        </figure>
      ) : ex?.tombstone ? (
        <p className="card">The cited source was removed. <Link className="underline" href={`/subjects/${subjectId}/resources`}>Replace it in Resources</Link>.</p>
      ) : (
        <p className="card"><span className="pill text-ink-muted">✦ AI-generated</span> No course citation exists for this concept (guided topic). Objective: {view.concept.objective}</p>
      )}
      {lesson?.example && (
        <div className="card">
          <OriginLabel origin={lesson.example.origin} />
          <p className="mt-2 text-problem"><MathText text={lesson.example.text} /></p>
        </div>
      )}
      {lesson?.retrieval_prompt && (
        <div>
          <label htmlFor="retr" className="label">{lesson.retrieval_prompt}</label>
          <textarea id="retr" className="field !min-h-[80px]" value={draft} onChange={(e) => onDraft(e.target.value)} />
          <p className="mt-1 text-meta text-ink-muted">Reading creates exposure only — it is recorded as “Introduced”, not as performance.</p>
        </div>
      )}
      <button className="btn-primary" onClick={onContinue}>Continue to practice</button>
    </section>
  );
}

/* ---------- practice (UC12/UC13/UC14) ---------- */
export function PracticeStage({ view, subjectId, draft, onDraft, onHelp, onReload, onContinue }:
  { view: any; subjectId: string; draft: string; onDraft: (t: string) => void; onHelp: () => void; onReload: () => void; onContinue: () => void }) {
  const t = view.current_task;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const key = useRef(newKey());
  const fbRef = useRef<HTMLDivElement>(null);
  useEffect(() => { key.current = newKey(); }, [t?.revision]);
  if (!t) return (
    <section className="space-y-4"><p>No exercise was extracted for this concept, and none could be generated and checked automatically.</p>
      <button className="btn-primary" onClick={onContinue}>Continue to explain-back</button></section>
  );
  const a = t.last_assessment;
  const done = t.status === "committed";
  const check = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api(`/tasks/${t.id}/submit`, { method: "POST", json: { answer: draft, expected_revision: t.revision, idempotency_key: key.current } });
      setAnnounce(r.assessment.outcome === "demonstrated" ? "Correct and fully expanded." : "Feedback ready.");
      onReload();
      setTimeout(() => fbRef.current?.focus(), 50);
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="space-y-5" aria-labelledby="st-h">
      <LiveRegion message={announce} />
      <div className="flex flex-wrap items-center gap-2"><OriginLabel origin={t.origin} detail={t.origin_detail} /><span className="text-meta text-ink-muted">{t.origin_detail}</span></div>
      <h2 id="st-h" tabIndex={-1} className="text-problem font-bold"><MathText text={t.prompt} /></h2>
      {t.revealed && t.solution && (
        <div className="card"><p className="font-semibold">Worked solution (this attempt is assisted)</p><p className="mt-1"><MathText text={t.solution.steps} /></p></div>
      )}
      {!done && !t.revealed && (
        <>
          <div>
            <label htmlFor="ans" className="label">Your answer</label>
            <input id="ans" className="field text-problem" value={draft} onChange={(e) => onDraft(e.target.value)} autoComplete="off" inputMode="text"
              aria-describedby="ans-hint" />
            <p id="ans-hint" className="mt-1 text-meta text-ink-muted">Type an expression, for example 3x + 5. No minimum effort needed before asking for help.</p>
          </div>
          {err && <ErrorBox message={err} />}
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={check} disabled={busy || !draft.trim()} aria-busy={busy}>{busy ? "Checking reasoning..." : "Check my reasoning"}</button>
            <button className="btn-help" onClick={onHelp}>Get help</button>
          </div>
        </>
      )}
      {a && (
        <div ref={fbRef} tabIndex={-1} className={`fade-in rounded-card border-2 p-4 ${a.outcome === "demonstrated" ? "border-success bg-success-surface" : a.outcome === "unscored" ? "border-border bg-surface" : "border-review bg-review-surface"}`}>
          <p className="font-semibold">{a.feedback}</p>
          {a.misconception?.targeted_question && <p className="mt-2"><strong>One question:</strong> <MathText text={a.misconception.targeted_question} /></p>}
          {!done && <p className="mt-2 text-meta">Revise your answer above and check again. Help steps never cost points.</p>}
          <div className="mt-3"><RubricFeedback assessment={a} subjectId={subjectId} compact /></div>
        </div>
      )}
      {(done || t.revealed) && <button className="btn-primary" onClick={t.revealed && !done ? onReload : onContinue}>{done ? "Continue to explain-back" : "Try the fresh check"}</button>}
    </section>
  );
}

/* ---------- transfer (UC15): commit mode before reveal; lock; guided conversion ---------- */
export function TransferStage({ view, subjectId, draft, onDraft, onReload, onReflect, onHelp, onPauseCapture }:
  { view: any; subjectId: string; draft: string; onDraft: (t: string) => void; onReload: () => void; onReflect: () => void;
    onHelp: () => void; onPauseCapture?: () => void }) {
  const t = view.current_task;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [convert, setConvert] = useState(false);
  const [converting, setConverting] = useState(false);
  const key = useRef(newKey());
  useEffect(() => { key.current = newKey(); }, [t?.revision]);

  if (!t) {
    const unavailable = view.pending_job?.result?.unavailable;
    if (unavailable) return (
      <section className="space-y-4"><p>{unavailable}</p><p className="text-meta text-ink-muted">Independent application stays “not shown yet”; nothing is invented.</p>
        <button className="btn-primary" onClick={onReflect}>Reflect</button></section>
    );
    return <div className="card" aria-busy="true"><p>Preparing a genuinely new problem…</p><button className="btn-primary mt-3" disabled>Preparing task</button></div>;
  }
  const commit = async (mode: "independent" | "guided") => {
    setBusy(true);
    try {
      await api(`/tasks/${t.id}/commit-mode`, { method: "POST", json: { mode, expected_revision: t.revision } });
      onReload();
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  const doConvert = async () => {
    setConverting(true);
    try {
      await api(`/tasks/${t.id}/convert`, { method: "POST", json: { expected_revision: t.revision } });
      setConvert(false);
      onReload();
    } catch (e) {
      setErr(`${(e as ApiError).message} You are still in independent mode; retry when ready.`);
    } finally { setConverting(false); }
  };
  const check = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/tasks/${t.id}/submit`, { method: "POST", json: { answer: draft, expected_revision: t.revision, idempotency_key: key.current } });
      onReload();
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.code === "STALE_REVISION" ? "This attempt changed in another tab (for example it was switched to guided practice). Reloading the current state." : ae.message);
      if (ae.code === "STALE_REVISION") onReload();
    } finally { setBusy(false); }
  };

  if (t.mode === "pending-commit") return (
    <section className="space-y-4" aria-labelledby="st-h" data-phase="transfer-introduction">
      <h2 id="st-h" tabIndex={-1} className="text-section">Try a new problem on your own</h2>
      <p>The next problem uses a different expression and situation. Choose how to attempt it before you see it.</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Lessons and hints stay unavailable until this attempt finishes or you switch to guided practice.</li>
        <li>Course pages, the Professor and earlier feedback are hidden for this subject meanwhile — on every tab and device.</li>
        <li>You can still pause, save, use scratch work and accessibility tools.</li>
      </ul>
      <p className="text-meta text-ink-muted">ThinkFirst can only control in-app help; the result is labeled “Completed without in-app help”.</p>
      {err && <ErrorBox message={err} />}
      <div className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={() => commit("independent")} disabled={busy}>Start without in-app help</button>
        <button className="btn-secondary" onClick={() => commit("guided")} disabled={busy}>Use guided help</button>
      </div>
    </section>
  );
  const a = t.last_assessment;
  const finished = ["committed", "abandoned"].includes(t.status);
  const independent = t.mode === "independent-transfer";
  return (
    <section className="space-y-5" aria-labelledby="st-h" data-phase={finished ? "transfer-feedback" : "transfer-answer"}>
      <div className="flex flex-wrap items-center gap-2">
        <OriginLabel origin={t.origin} detail={t.origin_detail} />
        <span className={`pill ${independent ? "text-ink" : "text-help bg-help-surface"}`}>{independent ? "Independent application: no in-app lesson or hint access" : "Guided practice (assisted)"}</span>
      </div>
      <h2 id="st-h" tabIndex={-1} className="text-problem font-bold">{t.prompt}</h2>
      {!finished && (
        <>
          <div>
            <label htmlFor="tr-ans" className="label">Your answer (write both forms)</label>
            <textarea id="tr-ans" className="field !min-h-[90px] text-problem" value={draft} onChange={(e) => onDraft(e.target.value)} />
          </div>
          {err && <ErrorBox message={err} />}
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={check} disabled={busy || !draft.trim()} aria-busy={busy}>{busy ? "Checking reasoning..." : "Check my answer"}</button>
            {independent ? <button className="btn-secondary" onClick={() => { onPauseCapture?.(); setConvert(true); }}>Use guided help</button>
              : <button className="btn-help" onClick={onHelp}>Get help</button>}
          </div>
        </>
      )}
      {a && (
        <div className="space-y-3">
          <RubricFeedback assessment={a} subjectId={subjectId} compact />
          {a.outcome === "unscored" && !finished && <p className="text-meta">Review your answer and check again, or keep it unscored.</p>}
          {independent && finished && a.outcome === "demonstrated" && <p className="pill text-success bg-success-surface">● Completed without in-app help</p>}
        </div>
      )}
      {a?.outcome === "unscored" && !finished && (
        <button className="btn-secondary" onClick={async () => { await api(`/tasks/${t.id}/keep-unscored`, { method: "POST" }); onReload(); }}>Keep unscored</button>
      )}
      {finished && <button className="btn-primary" onClick={onReflect}>Reflect</button>}
      <Dialog open={convert} title="Keep your work and switch to guided practice?" onClose={() => setConvert(false)}>
        <p>Your answer so far is kept. Help becomes available, and this attempt is recorded as guided (assisted) practice. This cannot be undone.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={doConvert} disabled={converting}>{converting ? "Switching" : "Switch to guided practice"}</button>
          <button className="btn-secondary" onClick={() => setConvert(false)}>Cancel</button>
        </div>
      </Dialog>
    </section>
  );
}
