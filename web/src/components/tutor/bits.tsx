"use client";
/* Small shared pieces: citations, likeness badge, run progress, upload drop zone. */
import { useCallback, useRef, useState, type ReactNode } from "react";
import type { Citation, Run } from "@/lib/tutor";

export function Citations({ items }: { items?: Citation[] }) {
  if (!items?.length) return null;
  return (
    <details className="mt-2 text-meta text-ink-muted">
      <summary className="cursor-pointer select-none">From your {items.some((c) => c.origin === "web") ? "course and the web" : "course"} ({items.length})</summary>
      <ul className="mt-1 space-y-1">
        {items.map((c, i) => (
          <li key={i} className="border-l-4 border-hl pl-2">
            <span className="font-semibold">{c.origin === "web" ? "Web" : "Course"}</span>
            {c.source ? ` · ${c.source}` : ""}{c.page ? ` · p. ${c.page}` : ""}
            {c.quote ? <> — “{c.quote.slice(0, 140)}{c.quote.length > 140 ? "…" : ""}”</> : null}
            {c.url ? <> · <a className="underline" href={c.url} target="_blank" rel="noreferrer noopener">source</a></> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function LikenessBadge({ value, detail }: { value: number | null | undefined; detail?: Record<string, number> }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const tip = detail ? Object.entries(detail).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(" · ") : "";
  return (
    <span className="pill text-soft-fg" title={`Looks like your course: ${tip}`} aria-label={`Course likeness ${pct} percent`}>
      <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5M12 11a1 1 0 1 0 1 1" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" /></svg>
      {pct}% like your course
    </span>
  );
}

export function RunProgress({ run, onResume }: { run: Run | null; onResume?: () => void }) {
  if (!run) return null;
  const done = run.steps.filter((s) => s.status === "done").map((s) => s.node);
  const active = run.status === "running" ? run.node : null;
  return (
    <div className="game-card space-y-3 p-5" aria-live="polite">
      <ol className="space-y-2">
        {run.steps.filter((s, i, a) => a.findIndex((x) => x.node === s.node) === i || s.status === "failed").map((s, i) => (
          <li key={i} className="flex items-center gap-3">
            <span className={`grid h-7 w-7 place-items-center rounded-full border-2 border-ink text-meta ${s.status === "done" ? "bg-strong" : s.status === "failed" ? "bg-review-surface" : "bg-surface"}`}>
              {s.status === "done" ? "✓" : s.status === "failed" ? "!" : i + 1}
            </span>
            <span className="flex-1">{s.label}</span>
            <span className="text-meta text-ink-muted">{s.status === "done" ? `${(s.ms / 1000).toFixed(1)} s` : s.error}</span>
          </li>
        ))}
        {active && !done.includes(active) && (
          <li className="flex items-center gap-3">
            <span className="grid h-7 w-7 animate-pulse place-items-center rounded-full border-2 border-ink bg-hl">…</span>
            <span className="flex-1">Working: {active.replace("_", " ")}</span>
          </li>
        )}
      </ol>
      {run.status === "failed" && (
        <div className="flex items-center justify-between gap-3 rounded-control bg-review-surface p-3">
          <span>Stopped at “{run.node}”: {run.error}. Finished steps are kept.</span>
          {onResume && <button className="btn-secondary" onClick={onResume}>Resume</button>}
        </div>
      )}
    </div>
  );
}

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md,.html,.png,.jpg,.jpeg";

export function UploadDrop({ onFiles, busy, children }: { onFiles: (f: File[]) => void; busy?: boolean; children?: ReactNode }) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const take = useCallback((list: FileList | null) => { if (list?.length) onFiles(Array.from(list)); }, [onFiles]);
  return (
    <div
      role="button" tabIndex={0} aria-busy={busy}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}
      className={`game-card cursor-pointer border-dashed p-8 text-center transition ${over ? "bg-hl" : "hover:bg-soft"}`}
    >
      <input ref={input} type="file" multiple accept={ACCEPT} className="sr-only" onChange={(e) => take(e.target.files)} />
      <p className="text-problem">{busy ? "Uploading…" : "Drop your course files here, or click to choose"}</p>
      <p className="mt-1 text-meta text-ink-muted">PDF, Word, PowerPoint, text, images (scans are read with OCR). 25 MB per file.</p>
      {children}
    </div>
  );
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-section">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
