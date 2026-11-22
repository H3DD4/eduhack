"use client";
// Concept graph for one subject: one column per unit, concepts in course order, prerequisite edges, nodes shaded by
// the learner engine's level (sequential, one hue: light = new, dark = mastered). Hover/focus shows the details;
// click opens the concept. Identity is never colour alone: the level number is printed in every node.
import Link from "next/link";
import { useState } from "react";

export const LEVEL_RAMP = ["#EEF2F0", "#D3F2DC", "#A3E2B6", "#5DC58A", "#1F9A61", "#0B6544"]; // 0..5
export const LEVEL_TEXT = ["#334155", "#0F3D2A", "#0F3D2A", "#06291B", "#FFFFFF", "#FFFFFF"];
export const LEVEL_NAMES = ["Not started", "Introduced", "Practising", "Developing", "Proficient", "Mastered"];

export function LevelLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-meta" aria-label="Level colours">
      {LEVEL_NAMES.map((n, i) => (
        <li key={n} className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3.5 w-3.5 rounded-full border border-ink/40" style={{ background: LEVEL_RAMP[i] }} />
          {i} {n}
        </li>
      ))}
    </ul>
  );
}

export function ConceptGraph({ nodes }: { nodes: any[] }) {
  const [hover, setHover] = useState<any>(null);
  const units = Array.from(new Set(nodes.map((n) => n.unit_no))).sort((a, b) => a - b);
  const colW = 150, rowH = 74, padX = 70, padY = 46;
  const pos: Record<string, { x: number; y: number }> = {};
  let maxRows = 1;
  units.forEach((u, ui) => {
    const col = nodes.filter((n) => n.unit_no === u);
    maxRows = Math.max(maxRows, col.length);
    col.forEach((n, i) => (pos[n.key] = { x: padX + ui * colW, y: padY + i * rowH }));
  });
  const width = padX * 2 + (units.length - 1) * colW;
  const height = padY * 2 + (maxRows - 1) * rowH;
  return (
    <div className="relative">
      <div className="overflow-x-auto rounded-detail border border-border bg-surface-subtle">
        <svg width={width} height={height} role="img" aria-label={`Concept graph: ${nodes.length} concepts`} className="block">
          {units.map((u, ui) => (
            <text key={u} x={padX + ui * colW} y={18} textAnchor="middle" fontSize="12" fill="var(--ink-muted)">Unit {u}</text>
          ))}
          {nodes.flatMap((n) => (n.prerequisites || []).filter((k: string) => pos[k] && pos[n.key]).map((k: string) => {
            const a = pos[k], b = pos[n.key];
            const mx = (a.x + b.x) / 2;
            return <path key={`${k}-${n.key}`} d={`M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`}
              fill="none" stroke="var(--border)" strokeWidth="2" />;
          }))}
          {nodes.map((n) => {
            const p = pos[n.key];
            return (
              <Link key={n.id} href={n.href} aria-label={`${n.key} ${n.title}: level ${n.level} ${n.level_label}${n.review_due ? ", review due" : ""}`}
                onMouseEnter={() => setHover({ ...n, ...p })} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover({ ...n, ...p })} onBlur={() => setHover(null)}>
                <circle cx={p.x} cy={p.y} r={n.is_foundation ? 15 : 20} fill={LEVEL_RAMP[n.level]}
                  stroke="var(--surface)" strokeWidth="2" strokeDasharray={n.is_foundation ? "3 3" : undefined} />
                <circle cx={p.x} cy={p.y} r={(n.is_foundation ? 15 : 20) + 2} fill="none" stroke="var(--tf-ink)" strokeWidth="1.5" />
                <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill={LEVEL_TEXT[n.level]}>{n.level}</text>
                <text x={p.x} y={p.y + 36} textAnchor="middle" fontSize="11" fill="var(--ink)">{n.key}</text>
                {n.review_due && <text x={p.x + 18} y={p.y - 14} fontSize="12" aria-hidden>↻</text>}
              </Link>
            );
          })}
        </svg>
      </div>
      {hover && (
        <div role="tooltip" className="pointer-events-none absolute z-10 max-w-[240px] rounded-control border-2 border-ink bg-surface p-2 text-meta shadow-hard"
          style={{ left: Math.min(hover.x + 28, width - 120), top: hover.y - 10 }}>
          <p className="font-bold">{hover.key} · {hover.title}</p>
          <p>Level {hover.level}: {hover.level_label}</p>
          {hover.review_due && <p>↻ Review due (recall is fading)</p>}
          {hover.is_foundation && <p className="text-ink-muted">Optional foundation</p>}
        </div>
      )}
    </div>
  );
}
