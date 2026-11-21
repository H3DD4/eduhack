"use client";
// Ctrl/Cmd + K "jump to" palette: every destination one keystroke away. Arrow keys move, Enter opens, Esc closes.
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";

type Item = { label: string; hint: string; href: string };

const STATIC: Item[] = [
  { label: "Today", hint: "Home", href: "/today" },
  { label: "Subjects", hint: "All courses", href: "/subjects" },
  { label: "Add a subject", hint: "Upload or type a topic", href: "/subjects/new" },
  { label: "Planner", hint: "Reviews and study blocks", href: "/planner" },
  { label: "Progress", hint: "Evidence by subject", href: "/progress" },
  { label: "Settings", hint: "Account", href: "/settings?section=account" },
  { label: "Privacy and data", hint: "Consent and export", href: "/settings?section=privacy" },
];

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [subjects, setSubjects] = useState<Item[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement;
    setQ("");
    setSel(0);
    setTimeout(() => input.current?.focus(), 10);
    api<any>("/subjects", { retries: 0 })
      .then((r) => setSubjects((r.subjects || []).flatMap((s: any) => [
        { label: s.name, hint: "Roadmap", href: `/subjects/${s.id}/roadmap` },
        { label: `${s.name}: diagnostic`, hint: "Find where to start", href: `/subjects/${s.id}/diagnostic` },
        { label: `${s.name}: practice`, hint: "Practice", href: `/subjects/${s.id}/practice` },
      ])))
      .catch(() => {});
    return () => { (opener.current as HTMLElement | null)?.focus?.(); };
  }, [open]);

  const items = useMemo(() => {
    const all = [...STATIC, ...subjects];
    const t = q.trim().toLowerCase();
    return t ? all.filter((i) => `${i.label} ${i.hint}`.toLowerCase().includes(t)) : all;
  }, [q, subjects]);

  useEffect(() => { setSel(0); }, [q]);
  if (!open) return null;

  const go = (i: Item | undefined) => {
    if (!i) return;
    onClose();
    router.push(i.href);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); go(items[sel]); }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-[rgba(15,23,42,0.45)] p-4 pt-[12vh]" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Jump to" onMouseDown={(e) => e.stopPropagation()} onKeyDown={onKey}
        className="fade-in w-full max-w-modal rounded-card border-2 border-ink bg-surface p-3 shadow-hard-lg">
        <label htmlFor="palette-q" className="sr-only">Search pages and subjects</label>
        <input id="palette-q" ref={input} className="field" placeholder="Jump to a page or subject…" value={q}
          onChange={(e) => setQ(e.target.value)} role="combobox" aria-expanded="true" aria-controls="palette-list"
          aria-activedescendant={items[sel] ? `pal-${sel}` : undefined} autoComplete="off" />
        <ul id="palette-list" role="listbox" className="mt-2 max-h-[50vh] overflow-y-auto">
          {items.map((i, n) => (
            <li key={i.href} id={`pal-${n}`} role="option" aria-selected={n === sel}>
              <button type="button" className="palette-item" aria-selected={n === sel} onMouseEnter={() => setSel(n)} onClick={() => go(i)}>
                <span>{i.label}</span><span className="text-meta text-ink-muted">{i.hint}</span>
              </button>
            </li>
          ))}
          {items.length === 0 && <li className="p-3 text-ink-muted">Nothing matches “{q}”.</li>}
        </ul>
        <p className="mt-2 flex gap-3 px-2 text-meta text-ink-muted"><span><span className="kbd">↑</span> <span className="kbd">↓</span> move</span><span><span className="kbd">Enter</span> open</span><span><span className="kbd">Esc</span> close</span></p>
      </div>
    </div>
  );
}
