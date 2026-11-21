"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { SpeakButton } from "../avatar/AvatarSpeakerContext";
import { TeacherAvatar } from "../avatar/TeacherAvatar";
import { Dialog, ErrorBox, LiveRegion, MathText, OriginLabel } from "../ui";
import { RubricFeedback } from "./RubricFeedback";

/* ---------- recall (UC11 step 1): "I don't know" always valid; no grading ---------- */
export function RecallStage({ view, draft, onDraft, onContinue }: { view: any; draft: string; onDraft: (t: string) => void; onContinue: () => void }) {
  const [oriented, setOriented] = useState(false);
  const recallPrompt = `Before we start: what do you already remember about ${view.concept.title.toLowerCase()}? ${
    oriented ? `Orientation: this concept is about ${view.concept.objective}. The next step shows the cited course section.` : ""
  }`;
  return (
    <section className="space-y-4" aria-labelledby="st-h">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id="st-h" tabIndex={-1} className="text-section">Before we start: what do you already remember about {view.concept.title.toLowerCase()}?</h2>
        <SpeakButton text={recallPrompt} title={view.concept.title} hint={view.concept.title} label="Speak" />
      </div>
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
  const [showAvatar, setShowAvatar] = useState(true);
  const lesson = view.lesson;
  if (lesson?.locked) return <p>Lesson content is unavailable while an independent application is in progress.</p>;
  const ex = lesson?.excerpt;
  const fullLessonScript = [
    ex && !ex.tombstone ? ex.text : "",
    lesson?.generated?.summary || "",
    ...(lesson?.generated?.key_points || []),
    lesson?.example?.text ? `Worked example: ${lesson.example.text}` : "",
    !ex && !lesson?.generated ? view.concept?.objective || "" : "",
  ]
    .filter(Boolean)
    .join(". ");

  const askLessonProfessor = async (question: string) => {
    try {
      const r = await api("/professor/ask", {
        method: "POST",
        json: { subject_id: subjectId, question, idempotency_key: newKey() },
      });
      if (r?.message) return r.message as string;
    } catch {
      // Fallback handled by TeacherAvatar
    }
  };

  return (
    <section className="space-y-5" aria-labelledby="st-h">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="st-h" tabIndex={-1} className="text-section">What your course says</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAvatar((v) => !v)}
            className="btn-secondary !min-h-[36px] !px-3 text-meta"
          >
            🎓 {showAvatar ? "Hide 3D Teacher" : "Learn with 3D Teacher"}
          </button>
          <SpeakButton
            text={fullLessonScript}
            title={view.concept?.title}
            hint={view.concept?.title}
            subjectId={subjectId}
            label="Dock Avatar"
          />
        </div>
      </div>
      {showAvatar && fullLessonScript && (
        <TeacherAvatar
          text={fullLessonScript}
          hint={view.concept?.title}
          title={view.concept?.title}
          compact
          stageHeight={270}
          onAsk={askLessonProfessor}
        />
      )}
      {ex && !ex.tombstone ? (
        <figure className="card">
          <blockquote className="whitespace-pre-line text-problem"><MathText text={ex.text} /></blockquote>
          <figcaption className="mt-3 text-meta text-ink-muted">
            Cited from <Link className="underline" href={`/subjects/${subjectId}/resources/${ex.source_id}?page=${ex.page}&return=${encodeURIComponent(`/subjects/${subjectId}/sessions/${sessionId}`)}`}>{ex.filename}, page {ex.page}</Link>
          </figcaption>
        </figure>
      ) : ex?.tombstone ? (
        <p className="card">The cited source was removed. <Link className="underline" href={`/subjects/${subjectId}/resources`}>Replace it in Resources</Link>.</p>
      ) : lesson?.generated ? (
        <article className="game-card space-y-4 p-6">
          <p className="flex flex-wrap items-center gap-2"><OriginLabel origin="ai-generated" /><span className="text-meta text-ink-muted">{lesson.generated.label}</span></p>
          <p className="text-problem"><MathText text={lesson.generated.summary} /></p>
          {lesson.generated.key_points?.length > 0 && (
            <ul className="space-y-2">{lesson.generated.key_points.map((k: string, i: number) => (
              <li key={i} className="flex gap-3"><span aria-hidden className="node !h-8 !w-8 shrink-0 !text-meta !shadow-none node-progress">{i + 1}</span><span><MathText text={k} /></span></li>
            ))}</ul>
          )}
          {lesson.generated.sources?.length > 0 && (
            <div className="rounded-detail border border-border bg-canvas p-3 text-meta">
              <p className="font-semibold">Grounded in openly licensed sources</p>
              <ul className="mt-1 space-y-1">{lesson.generated.sources.map((src: any) => (
                <li key={src.id}><a className="underline" href={src.url} target="_blank" rel="noreferrer">{src.title}</a> — {src.attribution} <a className="underline" href={src.license_url} target="_blank" rel="noreferrer">License</a></li>
              ))}</ul>
            </div>
          )}
        </article>
      ) : view.pack_status === "pending" ? (
        <div className="hero p-6" aria-busy="true"><div className="relative z-10"><p className="text-section">Preparing your lesson…</p><p className="muted">Gathering open sources and writing a short lesson, practice and checks.</p></div></div>
      ) : (
        <p className="card"><span className="pill text-ink-muted">✦ AI-generated</span> No course citation exists for this concept. Objective: {view.concept.objective}</p>
      )}
      {lesson?.example && (
        <div className="card">
          <OriginLabel origin={lesson.example.origin} />
          <p className="mt-2 whitespace-pre-line text-problem"><MathText text={lesson.example.text} /></p>
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
  const [suggest, setSuggest] = useState<any>(null);
  const key = useRef(newKey());
  const fbRef = useRef<HTMLDivElement>(null);
  useEffect(() => { key.current = newKey(); }, [t?.revision]);
  useEffect(() => { setSuggest(null); }, [t?.id]);
  const newQuestion = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/sessions/${view.session.id}/practice/next`, { method: "POST", json: { expected_revision: view.session.revision } });
      onDraft("");
      onReload();
      setTimeout(() => document.getElementById("st-h")?.focus(), 80);
    } catch (e) {
      setErr((e as ApiError).code === "NO_MORE_ITEMS" ? "You have seen every question for this concept. Continue to explain-back." : (e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
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
      setAnnounce(r.assessment.outcome === "demonstrated" ? "Correct." : "Feedback ready.");
      setSuggest(r.suggested_help || null);
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <OriginLabel origin={t.origin} detail={t.origin_detail} />
          <span className="text-meta text-ink-muted">{t.origin_detail}</span>
          {t.context?.difficulty && <span className="pill text-ink">{({ easy: "Easy", medium: "Medium", hard: "Hard" } as any)[t.context.difficulty]}</span>}
          {t.context?.is_trigger && <span className="pill text-help bg-help-surface">Checks your earlier mistake</span>}
        </div>
        <SpeakButton text={t.prompt} title="Practice task" hint={view.concept?.title} subjectId={subjectId} taskId={t.id} label="Speak prompt" />
      </div>
      {t.context?.selection_reason && <p className="text-meta text-ink-muted">Why this question: {t.context.selection_reason}</p>}
      <h2 id="st-h" tabIndex={-1} className="text-problem font-bold"><MathText text={t.prompt} /></h2>
      {view.nudge && !t.last_assessment && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-detail bg-help-surface p-3 text-help">
          <p><strong>From your history:</strong> {view.nudge}</p>
          <SpeakButton text={`From your history: ${view.nudge}`} title="History nudge" hint={view.concept?.title} subjectId={subjectId} label="Speak" />
        </div>
      )}
      {t.revealed && t.solution && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">Worked solution (this attempt is assisted)</p>
            <SpeakButton text={t.solution.steps} title="Worked solution" hint={view.concept?.title} subjectId={subjectId} label="Speak solution" />
          </div>
          <p className="mt-1"><MathText text={t.solution.steps} /></p>
        </div>
      )}
      {!done && !t.revealed && (
        <>
          <div>
            <label htmlFor="ans" className="label">Your answer</label>
            {t.kind === "short_answer" ? (
              <textarea id="ans" className="field !min-h-[100px] text-problem" value={draft} onChange={(e) => onDraft(e.target.value)} aria-describedby="ans-hint" />
            ) : (
              <input id="ans" className="field text-problem" value={draft} onChange={(e) => onDraft(e.target.value)} autoComplete="off" inputMode="text"
                aria-describedby="ans-hint" />
            )}
            <p id="ans-hint" className="mt-1 text-meta text-ink-muted">{t.kind === "short_answer" ? "Answer in your own words (any language)." : "Type an expression, for example 3x + 5."} No minimum effort needed before asking for help.</p>
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
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="font-semibold">{a.feedback}</p>
            <SpeakButton
              text={`${a.feedback} ${a.misconception?.targeted_question ? `One question: ${a.misconception.targeted_question}` : ""}`}
              title="Feedback"
              hint={view.concept?.title}
              subjectId={subjectId}
              taskId={t.id}
              label="Speak feedback"
            />
          </div>
          {a.misconception?.targeted_question && <p className="mt-2"><strong>One question:</strong> <MathText text={a.misconception.targeted_question} /></p>}
          {!done && <p className="mt-2 text-meta">Revise your answer above and check again. Help steps never cost points.</p>}
          <div className="mt-3"><RubricFeedback assessment={a} subjectId={subjectId} compact /></div>
        </div>
      )}
      {suggest && !done && (
        <div className="rounded-detail bg-help-surface p-3 text-help" role="status">
          <p><strong>Suggested next:</strong> {suggest.label}. It helped students who made the same slip.</p>
          <button className="btn-help mt-2" onClick={onHelp}>Open the suggested help</button>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {(done || t.revealed) && <button className="btn-primary" onClick={t.revealed && !done ? onReload : onContinue}>{done ? "Continue to explain-back" : "Try the fresh check"}</button>}
        {a && <button className="btn-secondary" onClick={newQuestion} disabled={busy}>{done ? "One more question" : "Try a new question"}</button>}
      </div>
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
    if (view.pending_job?.status === "failed") return (
      <div className="card space-y-3" role="alert"><p>The new problem is not ready yet (its study pack is still being prepared).</p>
        <button className="btn-primary" onClick={async () => { await api(`/jobs/${view.pending_job.id}/retry`, { method: "POST" }); onReload(); }}>Retry</button></div>
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <OriginLabel origin={t.origin} detail={t.origin_detail} />
          <span className={`pill ${independent ? "text-ink" : "text-help bg-help-surface"}`}>{independent ? "Independent application: no in-app lesson or hint access" : "Guided practice (assisted)"}</span>
        </div>
        {(!independent || finished) && (
          <SpeakButton text={t.prompt} title="New application" hint={view.concept.title} subjectId={subjectId} taskId={t.id} label="Speak problem" />
        )}
      </div>
      <h2 id="st-h" tabIndex={-1} className="text-problem font-bold">{t.prompt}</h2>
      {!finished && (
        <>
          <div>
            <label htmlFor="tr-ans" className="label">{t.kind === "equivalent_forms" ? "Your answer (write both forms)" : "Your answer"}</label>
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
