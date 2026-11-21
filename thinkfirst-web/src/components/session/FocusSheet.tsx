"use client";
// F01 Focus and pause sheet — UC16/UC23. Timer optional, in-app quiet only; no OS blocking; no time credit.
import { useEffect, useState } from "react";
import { Dialog } from "../ui";

export function FocusSheet({ open, onClose, onPause, quiet, setQuiet, timerMinutes, saving }:
  { open: boolean; onClose: () => void; onPause: () => void; quiet: boolean; setQuiet: (v: boolean) => void;
    timerMinutes: number | null; saving: boolean }) {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!open || !timerMinutes) return;
    const id = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(id);
  }, [open, timerMinutes]);
  const left = timerMinutes ? Math.max(0, timerMinutes - Math.floor((now - startedAt) / 60000)) : null;
  return (
    <Dialog open={open} title="Focus" onClose={onClose}>
      <div className="space-y-4" data-screen="F01">
        <p>{left === null ? "Timer off." : `About ${left} min left on your optional timer.`} Pausing never affects your evidence.</p>
        <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" checked={quiet} onChange={(e) => setQuiet(e.target.checked)} />
          Quiet mode (hides in-app decoration)</label>
        <p className="text-meta text-ink-muted">ThinkFirst cannot block other apps or notifications on your device.</p>
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" onClick={onPause} disabled={saving} aria-busy={saving}>{saving ? "Saving…" : "Save and pause"}</button>
          <button className="btn-secondary" onClick={onClose}>Stay</button>
        </div>
      </div>
    </Dialog>
  );
}
