"use client";
// P01 Contextual Professor — UC13/UC14/UC22. Help ladder is enforced server-side; the worked solution needs an
// explicit "End this attempt and view worked solution" confirmation. Locked transfer offers conversion only.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, newKey } from "@/lib/api";
import { Dialog, SimulatedLabel } from "../ui";

export function ProfessorPanel({ task, subjectId, onClose, onChanged, onLocked }:
  { task: any; subjectId: string; onClose: () => void; onChanged: (r?: any) => void; onLocked: () => void }) {
  const [steps, setSteps] = useState<any[]>(task?.help_events || []);
  const [confirmReveal, setConfirmReveal] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => { setSteps(task?.help_events || []); }, [task?.id, task?.help_events]);

  const level = task?.help_level ?? 0;
  const max = task?.max_help_level ?? 3;
  const ended = task && ["ended_assisted", "committed", "abandoned"].includes(task.status);

  const ask = async (kind: "next" | "dont_know", confirm = false) => {
    if (!task) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api(`/tasks/${task.id}/help`, { method: "POST", json: { kind, confirm_reveal: confirm, idempotency_key: newKey() } });
      setSteps((s) => (s.some((x) => x.level === r.level) ? s : [...s, r]));
      onChanged(r);
    } catch (e) {
      const ae = e as ApiError;
      if (ae.code === "REVEAL_CONFIRMATION_REQUIRED") setConfirmReveal(true);
      else if (ae.code === "TRANSFER_LOCKED") onLocked();
      else setErr(ae);
    } finally {
      setBusy(false);
    }
  };
  const askProfessor = async () => {
    setBusy(true);
    setErr(null);
    try {
      setAnswer(await api("/professor/ask", { method: "POST", json: { subject_id: subjectId, task_id: task?.id, question, idempotency_key: newKey() } }));
    } catch (e) {
      const ae = e as ApiError;
      if (ae.code === "TRANSFER_LOCKED") onLocked();
      else setErr(ae);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside aria-labelledby="p01-h" data-screen="P01"
      className="fixed inset-x-0 bottom-0 z-40 max-h-[80vh] overflow-y-auto rounded-t-card border-t border-border bg-surface p-5 shadow-2xl xl:static xl:max-h-none xl:w-[320px] xl:rounded-card xl:border xl:shadow-none">
      <div className="flex items-start justify-between gap-2">
        <h2 id="p01-h" ref={heading} tabIndex={-1} className="text-section">Help</h2>
        <button className="btn-secondary !min-h-[44px] !px-3" onClick={onClose} aria-label="Close help and return to task">✕</button>
      </div>
      <p className="mt-1 text-meta text-ink-muted">Help never costs points. Asking early is fine.</p>
      {task && (
        <div className="mt-4 space-y-3">
          <ol className="space-y-2" aria-label="Help steps so far">
            {steps.map((h) => (
              <li key={h.level} className="hint-in rounded-detail bg-help-surface p-3 text-ink">
                <p className="text-meta font-semibold text-help">Step {h.level}: {h.label}</p>
                <p className="mt-1">{h.content}</p>
              </li>
            ))}
          </ol>
          {!ended && (
            <div className="flex flex-wrap gap-2">
              {level === 0 && <button className="btn-help" onClick={() => ask("dont_know")} disabled={busy}>I don&apos;t know where to start</button>}
              {level < max && level < 4 && <button className="btn-help" onClick={() => ask("next")} disabled={busy}>{level === 0 ? "Give me a first hint" : "Next help step"}</button>}
              {level >= 4 && max === 5 && <button className="btn-secondary" onClick={() => setConfirmReveal(true)} disabled={busy}>End this attempt and view worked solution</button>}
              {level >= max && max < 5 && <p className="text-meta text-ink-muted">No further steps for this task. Reread the cited section or ask below.</p>}
            </div>
          )}
          {task.revealed && <p className="text-meta">This attempt ended with the worked solution. A fresh check follows; it is recorded as assisted practice.</p>}
        </div>
      )}
      <div className="mt-6 border-t border-border pt-4">
        <label htmlFor="prof-q" className="label">Ask about this concept</label>
        <textarea id="prof-q" className="field !min-h-[80px]" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <button className="btn-secondary mt-2" onClick={askProfessor} disabled={busy || !question.trim()}>Ask</button>
        <p className="mt-1 text-meta text-ink-muted">Uses 1 unit of your allowance. The help steps above are free.</p>
        {answer && (
          <div className="mt-3 space-y-2" aria-live="polite">
            {answer.simulated && <SimulatedLabel label={answer.label} />}
            <p>{answer.message}</p>
            {answer.citations?.map((c: any) => <p key={c.chunk_id} className="text-meta text-ink-muted">Course page {c.page}: “{c.quote.slice(0, 140)}…”</p>)}
          </div>
        )}
      </div>
      {err && <p role="alert" className="mt-3 text-review">{err.code === "QUOTA_EXHAUSTED" ? "Not enough allowance for a Professor question. The help steps still work." : err.message}</p>}
      <button className="btn-link mt-4" onClick={onClose}>Return to task</button>
      <Dialog open={confirmReveal} title="End this attempt and view the worked solution?" onClose={() => setConfirmReveal(false)}>
        <p>You will see the full worked solution. This attempt then counts as assisted practice, and a fresh check with new numbers follows. Nothing is deducted.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={() => { setConfirmReveal(false); ask("next", true); }}>End attempt and view solution</button>
          <button className="btn-secondary" onClick={() => setConfirmReveal(false)}>Keep trying</button>
        </div>
      </Dialog>
    </aside>
  );
}
