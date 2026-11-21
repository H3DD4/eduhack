"use client";
import katex from "katex";
import Link from "next/link";
import { SpeakButton } from "./avatar/AvatarSpeakerContext";
import { Mark } from "./Logo";
import { ReactNode, useEffect, useRef } from "react";

/* ---------- honest labels (never colour-only) ---------- */

export function DemoLabel({ children = "Demo data" }: { children?: ReactNode }) {
  return <span className="pill text-ink bg-soft" style={{ borderColor: "var(--ink)" }}>◆ {children}</span>;
}

export function SimulatedLabel({ label }: { label?: string }) {
  return <span className="pill text-help bg-help-surface" title={label}>⚙ {label || "Simulated assessment"}</span>;
}

const ORIGIN: Record<string, string> = {
  "verified-source": "Verified source",
  "unverified-source": "Unverified source",
  "ai-generated": "AI-generated",
};
export function OriginLabel({ origin, detail }: { origin: string; detail?: string }) {
  return (
    <span className="pill text-ink-muted bg-surface" data-origin={origin}>
      {origin === "ai-generated" ? "✦" : origin === "verified-source" ? "✓" : "○"} {ORIGIN[origin] || origin}
      {detail ? <span className="sr-only">: {detail}</span> : null}
    </span>
  );
}

const STATE_STYLE: Record<string, { icon: string; cls: string }> = {
  introduced: { icon: "○", cls: "text-ink-muted bg-surface" },
  practised_with_support: { icon: "◐", cls: "text-help bg-help-surface" },
  explained: { icon: "❝", cls: "text-help bg-help-surface" },
  applied_independently: { icon: "●", cls: "text-success bg-success-surface" },
  recalled_later: { icon: "★", cls: "text-success bg-success-surface" },
  insufficient_evidence: { icon: "?", cls: "text-ink-muted bg-surface" },
};
export function EvidencePill({ label, text }: { label: string; text: string }) {
  const s = STATE_STYLE[label] || STATE_STYLE.introduced;
  return <span className={`pill ${s.cls}`}><span aria-hidden>{s.icon}</span> {text}</span>;
}

export type SaveState = "synced" | "device" | "unsaved" | "saving";
export function SaveBadge({ state, at }: { state: SaveState; at?: string | null }) {
  const map = {
    synced: ["Synced", "text-success"],
    device: ["On this device", "text-help"],
    unsaved: ["Not saved", "text-review"],
    saving: ["Saving…", "text-ink-muted"],
  } as const;
  const [text, cls] = map[state];
  return (
    <span className={`pill ${cls} bg-surface`} role="status" aria-live="polite" data-save-state={state}>
      {text}{at && state === "synced" ? <span className="text-ink-muted font-normal"> · {new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span> : null}
    </span>
  );
}

/* ---------- status, errors, loading ---------- */

export function LiveRegion({ message }: { message: string }) {
  return <div className="sr-only" role="status" aria-live="polite">{message}</div>;
}

export function ErrorBox({ title = "Something needs attention", message, onRetry, children }:
  { title?: string; message: string; onRetry?: () => void; children?: ReactNode }) {
  return (
    <div role="alert" className="fade-in rounded-card border-2 border-review bg-review-surface p-4 text-ink">
      <p className="text-review">{title}</p>
      <p className="mt-1">{message}</p>
      {(onRetry || children) && <div className="mt-3 flex flex-wrap gap-2">{onRetry && <button className="btn-secondary" onClick={onRetry}>Retry</button>}{children}</div>}
    </div>
  );
}

export function Skeleton({ lines = 3, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="space-y-3">
      {Array.from({ length: lines }).map((_, i) => <div key={i} className="h-5 animate-pulse rounded-detail bg-border" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

export function NotAvailable({ backHref = "/today" }: { backHref?: string }) {
  return (
    <div className="card max-w-prose">
      <h1 className="text-section">Not available</h1>
      <p className="mt-2 text-ink-muted">This item does not exist or is not yours to view.</p>
      <Link className="btn-secondary mt-4" href={backHref}>Go back</Link>
    </div>
  );
}

/* ---------- accessible modal dialog (Q01, conversions, confirmations) ---------- */

export function Dialog({ open, title, onClose, children, describedBy }:
  { open: boolean; title: string; onClose: () => void; children: ReactNode; describedBy?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);
  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement;
    const el = ref.current;
    const focusables = () => Array.from(el?.querySelectorAll<HTMLElement>("button, [href], input, textarea, select, [tabindex]:not([tabindex='-1'])") || []).filter((x) => !x.hasAttribute("disabled"));
    focusables()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "Tab") {
        const f = focusables();
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      (opener.current as HTMLElement | null)?.focus?.(); // restore focus to the initiating control
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-[rgba(15,23,42,0.45)] p-0 sm:items-center sm:p-4">
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="dlg-title" aria-describedby={describedBy}
        className="fade-in w-full max-w-modal rounded-t-card border-2 border-ink bg-surface p-6 shadow-hard-lg sm:rounded-card">
        <h2 id="dlg-title" className="text-section">{title}</h2>
        <div className="mt-3">{children}</div>
      </div>
    </div>
  );
}

/* ---------- math (KaTeX, with text equivalent) ---------- */

const MATH_RUN = /(\d*\s*\([a-z0-9+\-−·*× ]+\)(?:\s*[+\-−]\s*\d*[a-z]?)*|\b\d+[a-z](?:\s*[+\-−]\s*\d+[a-z]?)+)/gi;

export function MathText({ text, className = "" }: { text: string; className?: string }) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(MATH_RUN)) {
    const i = m.index ?? 0;
    if (i > last) parts.push(text.slice(last, i));
    const src = m[0].replace(/·|×/g, "\\cdot ").replace(/−/g, "-").replace(/\*/g, "\\cdot ");
    let html = "";
    try {
      html = katex.renderToString(src, { throwOnError: false, output: "htmlAndMathml" });
    } catch {
      html = "";
    }
    parts.push(html ? <span key={i} className="math-scroll inline-block align-middle" dangerouslySetInnerHTML={{ __html: html }} /> : m[0]);
    last = i + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <span className={className}>{parts}</span>;
}

/* ---------- companion (original faceted compass; peripheral, never during capture/transfer/exams) ---------- */

export function Companion({ message, hidden }: { message: string; hidden?: boolean }) {
  if (hidden) return null;
  return (
    <aside aria-label="Companion note" className="flex items-start justify-between gap-3 rounded-card border-2 border-dashed border-ink-muted p-3 text-ink">
      <div className="flex items-start gap-3">
        <Mark size={40} className="shrink-0" />
        <p className="pt-2">{message}</p>
      </div>
      <SpeakButton text={message} title="Companion" label="Speak" className="shrink-0" />
    </aside>
  );
}

export function ScopeNotice({ id, title, milestone, children }: { id: string; title: string; milestone: string; children?: ReactNode }) {
  return (
    <section className="card max-w-prose" data-screen={id} data-milestone={milestone}>
      <p className="badge">Coming soon</p>
      <h1 className="text-page-compact mt-3">{title}</h1>
      <p className="mt-3">Coming soon. This part of ThinkFirst is not built yet.</p>
      {children}
    </section>
  );
}
