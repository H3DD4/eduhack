"use client";
// Q01 Quota boundary dialog — UC38. Only at safe boundaries (never mid-recording/answer/exam).
// Shows actual usage/reset; free continuation first; no invented prices; closing never erases work.
import Link from "next/link";
import { Dialog } from "./ui";

export function QuotaDialog({ open, info, subjectId, onClose, onRetry }:
  { open: boolean; info: any; subjectId: string; onClose: () => void; onRetry: () => void }) {
  const q = info?.quota;
  return (
    <Dialog open={open} title="Not enough allowance to start this check" onClose={onClose} describedBy="q01-desc">
      <div id="q01-desc" data-screen="Q01">
        {q ? (
          <p>You have used <strong>{q.used_units}</strong> of <strong>{q.period_units}</strong> units this period
            {q.held_units ? <> ({q.held_units} reserved for checks already in progress)</> : null}. This step needs <strong>{info.needed_units}</strong>.
            Your allowance resets on <strong>{new Date(q.resets_at).toLocaleDateString()}</strong>.</p>
        ) : <p>Checking availability…</p>}
        <p className="mt-2 text-meta text-ink-muted">{q?.provider_label}. Your work and setup are unchanged.</p>
        <p className="mt-2 text-meta text-ink-muted">Paid plans are not available in this build.</p>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="btn-primary" href={`/subjects/${subjectId}/resources`}>Continue with resources</Link>
        <button className="btn-secondary" onClick={onRetry}>Retry</button>
        <button className="btn-secondary" onClick={onClose}>Wait</button>
      </div>
    </Dialog>
  );
}
