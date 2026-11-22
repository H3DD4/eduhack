"use client";
// Roadmap journey: one winding road from Start to the Finish line through every unit.
// Milestones light up strictly in order: a milestone is "done" only when it AND every milestone before it is
// achieved (applied on your own, no in-app help, or proven known on the level test). The first one not done is
// "current" (you are here); all later ones stay locked and dim, even if you already practised them (that progress
// is kept and shows once unlocked).
// The SVG road is decorative; the milestones are a real ordered list of links (keyboard / screen-reader order).
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

export type MilestoneStatus = "done" | "current" | "locked";
export interface Milestone {
  c: any;                     // concept from /subjects/{id}/roadmap
  unit: any;
  index: number;
  status: MilestoneStatus;
  achieved: boolean;          // achieved on its own, regardless of order
  previous?: any;             // the milestone that unlocks this one
}

export const ACHIEVED_STATES = ["applied_independently", "recalled_later"];
export const isAchieved = (c: any) =>
  !!c?.evidence?.states?.some((s: string) => ACHIEVED_STATES.includes(s)) || c?.placement_status === "known";

/** Sequential gating over all units, in teaching order. */
export function buildJourney(units: any[]): Milestone[] {
  const out: Milestone[] = [];
  let open = true;
  units.forEach((u) => {
    (u.concepts.length ? u.concepts : u.foundations).forEach((c: any) => {
      const achieved = isAchieved(c);
      let status: MilestoneStatus;
      if (open && achieved) status = "done";
      else if (open) { status = "current"; open = false; }
      else status = "locked";
      out.push({ c, unit: u, index: out.length, status, achieved, previous: out[out.length - 1]?.c });
    });
  });
  return out;
}

function stars(c: any) {
  const s = new Set(c?.evidence?.states || []);
  return [s.has("practised_with_support") || s.has("introduced"), s.has("explained"), s.has("applied_independently")];
}

const reduceMotion = () =>
  typeof window !== "undefined" &&
  (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.motion === "reduce");

// ------------------------------------------------------------------------------------------- geometry
interface Pt { x: number; y: number }
function curve(pts: Pt[]) {
  return pts.map((p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const q = pts[i - 1];
    const my = (q.y + p.y) / 2;
    return `C ${q.x} ${my}, ${p.x} ${my}, ${p.x} ${p.y}`;
  }).join(" ");
}

function layout(ms: Milestone[], w: number) {
  const narrow = w < 640;
  // narrow screens: the road zigzags between the left and right thirds, labels sit in the free half
  const amp = narrow ? w * 0.25 : Math.min(w * 0.27, 250);
  const step = narrow ? 140 : 168;
  const unitGap = narrow ? 130 : 150;
  let y = narrow ? 230 : 170;
  const nodes: (Pt & { m: Milestone })[] = [];
  const zones: { unit: any; y: number; first: number; last: number; crossX: number }[] = [];
  const xAt = (i: number) => narrow ? w / 2 + (i % 2 ? amp : -amp) : w / 2 + Math.sin(i * 0.92 + 0.5) * amp;
  const start: Pt = { x: narrow ? xAt(0) : w / 2, y: 56 };
  ms.forEach((m, i) => {
    if (i > 0 && m.unit !== ms[i - 1].unit) y += unitGap;
    if (i === 0 || m.unit !== ms[i - 1].unit) {
      // the zone line sits halfway between units; the sign goes on the side the road is not crossing
      const lineY = i === 0 ? (narrow ? 132 : y - 92) : y - (step + unitGap) / 2;
      zones.push({ unit: m.unit, y: lineY, first: i, last: i, crossX: i === 0 || narrow ? xAt(i) : (xAt(i - 1) + xAt(i)) / 2 });
    }
    zones[zones.length - 1].last = i;
    nodes.push({ m, x: xAt(i), y });
    y += step;
  });
  const finish: Pt = { x: w / 2, y: y + 20 };
  return { narrow, start, nodes, zones, finish, height: finish.y + 170 };
}

// ------------------------------------------------------------------------------------------- component
export function RoadmapJourney({ units, subjectId, conceptId, foundations = [] }:
  { units: any[]; subjectId: string; conceptId?: string; foundations?: any[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(760);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => { if (el.clientWidth > 0) setW(el.clientWidth); });
    ro.observe(el);
    if (el.clientWidth > 0) setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const journey = useMemo(() => buildJourney(units), [units]);
  const L = useMemo(() => layout(journey, w), [journey, w]);
  const doneCount = journey.filter((m) => m.status === "done").length;
  const total = journey.length;
  const current = journey.find((m) => m.status === "current");
  const finished = total > 0 && doneCount === total;

  // ---- celebration: compare with what this device saw last time
  const storeKey = `tf_journey_${subjectId}`;
  const [seen, setSeen] = useState<number | null>(null);      // done count at last visit (null = loading)
  const [toast, setToast] = useState<string | null>(null);
  const [burstAt, setBurstAt] = useState<number | null>(null);
  useEffect(() => {
    let prev = -1;
    try { const v = localStorage.getItem(storeKey); if (v !== null) prev = parseInt(v, 10); } catch { /* noop */ }
    setSeen(prev < 0 ? 0 : Math.min(prev, doneCount));
    if (prev >= 0 && doneCount > prev) {
      const latest = journey[doneCount - 1];
      setToast(finished ? "Finish line reached — every milestone is yours!"
        : `Milestone unlocked: ${latest.c.title}. Next up: ${current?.c.title}`);
      if (!reduceMotion()) setBurstAt(doneCount - 1);
    }
    try { localStorage.setItem(storeKey, String(doneCount)); } catch { /* noop */ }
  }, [doneCount]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 5000); return () => clearTimeout(t); }, [toast]);
  useEffect(() => { if (burstAt == null) return; const t = setTimeout(() => setBurstAt(null), 1600); return () => clearTimeout(t); }, [burstAt]);

  // ---- road and progress paths
  const roadPts = [L.start, ...L.nodes, L.finish];
  const reach = finished ? roadPts.length : (current ? current.index + 2 : 1);   // start + done + current
  const prevReach = seen == null || seen >= doneCount ? reach : seen + 2;   // where the road ended last visit
  const road = curve(roadPts);
  const progress = curve(roadPts.slice(0, reach));
  const progressPrev = curve(roadPts.slice(0, Math.max(1, prevReach)));
  const progRef = useRef<SVGPathElement>(null);
  const prevRef = useRef<SVGPathElement>(null);
  const [dash, setDash] = useState<{ len: number; offset: number; animate: boolean }>({ len: 0, offset: 0, animate: false });
  useLayoutEffect(() => {
    if (seen == null || !progRef.current) return;
    const len = progRef.current.getTotalLength();
    const firstVisit = (() => { try { return localStorage.getItem(`${storeKey}_drawn`) == null; } catch { return false; } })();
    const from = firstVisit ? 0 : prevRef.current ? prevRef.current.getTotalLength() : len;
    if (reduceMotion() || from >= len) { setDash({ len, offset: 0, animate: false }); return; }
    setDash({ len, offset: len - from, animate: false });                  // show the old progress…
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setDash({ len, offset: 0, animate: true }))); // …then grow
    try { localStorage.setItem(`${storeKey}_drawn`, "1"); } catch { /* noop */ }
    return () => cancelAnimationFrame(id);
  }, [progress, seen, w]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- "you are here" marker glides from the previous milestone
  const target = finished ? L.finish : current ? L.nodes[current.index] : L.start;
  const [pin, setPin] = useState<Pt | null>(null);
  useEffect(() => {
    if (seen == null) return;
    const from = seen < doneCount && !reduceMotion() ? (L.nodes[seen] || L.start) : target;
    setPin(from);
    const t = setTimeout(() => setPin(target), 450);
    return () => clearTimeout(t);
  }, [seen, target.x, target.y]); // eslint-disable-line react-hooks/exhaustive-deps

  const jump = useCallback(() => {
    const id = finished ? "rj-finish" : current ? `rj-m-${current.c.id}` : null;
    if (id) document.getElementById(id)?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
  }, [finished, current]);

  // ---- optional side quests (never gate)
  const quests = !L.narrow ? foundations.flatMap((f) => {
    const n = L.nodes.find((p) => p.m.c.prerequisites?.includes(f.key) && p.m.unit.concepts.length);
    if (!n) return [];
    const side = n.x > w / 2 ? 1 : -1;   // opposite the milestone's label
    return [{ f, x: Math.max(48, Math.min(w - 48, n.x + side * Math.min(150, w * 0.2))), y: n.y + 46, n }];
  }).filter((q, i, a) => a.findIndex((x) => x.f.id === q.f.id) === i) : [];

  const pct = total ? Math.round((100 * doneCount) / total) : 0;

  return (
    <div className="rj">
      {/* ---------------- HUD ---------------- */}
      <div className="rj-hud" role="group" aria-label="Journey progress">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-bold">{finished ? "Finish line reached 🏁" : `${doneCount} of ${total} milestones`}</p>
            <p className="text-meta text-ink-muted">{finished ? "Keep it fresh with reviews." : current ? <>Next: <strong className="text-ink">{current.c.title}</strong></> : null}</p>
          </div>
          <div className="rj-segments" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={doneCount}
            aria-valuetext={`${doneCount} of ${total} milestones, ${pct} percent`}>
            {journey.map((m) => <span key={m.c.id} className={`rj-seg rj-seg-${m.status}`} title={`${m.index + 1}. ${m.c.title}`} />)}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="rj-pct" aria-hidden>{pct}%</span>
          <button type="button" className="btn-secondary !min-h-[44px] !px-4" onClick={jump}>📍 My position</button>
        </div>
      </div>

      {/* ---------------- map ---------------- */}
      <div ref={box} className="rj-map map-bg" style={{ height: L.height }}>
        <svg className="absolute inset-0" width={w} height={L.height} aria-hidden="true">
          <defs>
            <linearGradient id="rj-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--discovery)" />
              <stop offset="1" stopColor="var(--rj-done)" />
            </linearGradient>
            <pattern id="rj-check" width="16" height="16" patternUnits="userSpaceOnUse">
              <rect width="16" height="16" fill="var(--surface)" /><rect width="8" height="8" fill="var(--ink)" /><rect x="8" y="8" width="8" height="8" fill="var(--ink)" />
            </pattern>
          </defs>
          {L.zones.map((z, i) => i > 0 && <line key={i} x1="16" x2={w - 16} y1={z.y} y2={z.y} className="rj-zone-line" />)}
          <path d={road} className="rj-road" />
          <path d={road} className="rj-road-dash" />
          <path ref={prevRef} d={progressPrev} fill="none" stroke="none" />
          <path ref={progRef} d={progress} className="rj-progress"
            style={{ strokeDasharray: dash.len || undefined, strokeDashoffset: dash.offset, transition: dash.animate ? "stroke-dashoffset 1.4s var(--ease)" : "none" }} />
          {quests.map((q) => <path key={q.f.id} d={`M ${q.x} ${q.y} L ${q.n.x} ${q.n.y}`} className="rj-quest-line" />)}
          <rect x={L.finish.x - 90} y={L.finish.y - 14} width="180" height="28" rx="6" fill="url(#rj-check)" stroke="var(--ink)" strokeWidth="2" opacity={finished ? 1 : 0.35} />
        </svg>

        {/* start */}
        <div className="rj-sign" style={{ left: L.start.x, top: L.start.y }}><span aria-hidden>🚩</span> Start</div>

        {/* unit zones */}
        {L.zones.map((z) => {
          const ms = journey.slice(z.first, z.last + 1);
          const done = ms.filter((m) => m.status === "done").length;
          const state = done === ms.length ? "done" : ms.some((m) => m.status === "current") ? "current" : "locked";
          const left = z.crossX > w / 2;
          return (
            <div key={z.unit.unit_no} className={`rj-zone rj-zone-${state}`} style={left ? { left: 16, top: z.y - 28 } : { right: 16, top: z.y - 28 }}>
              <span aria-hidden>{state === "done" ? "🏆" : state === "current" ? "⛳" : "🔒"}</span>
              <span className="min-w-0"><span className="block truncate font-bold">Unit {z.unit.unit_no}: {z.unit.title}</span>
                <span className="text-meta">{done}/{ms.length} milestones{state === "locked" ? " · locked" : ""}</span></span>
            </div>
          );
        })}

        {/* milestones */}
        <ol className="contents" aria-label="Milestones from start to finish">
          {L.nodes.map((n) => {
            const { m } = n;
            const st = stars(m.c);
            const labelLeft = n.x > w / 2;
            const status = m.status === "done" ? "Completed" : m.status === "current" ? "You are here" : `Locked. Complete “${m.previous?.title}” first`;
            return (
              <li key={m.c.id} id={`rj-m-${m.c.id}`} className={`rj-ms rj-${m.status} ${burstAt === m.index ? "rj-pop" : ""}`}
                style={{ left: n.x, top: n.y, animationDelay: `${Math.min(m.index, 12) * 45}ms` }}>
                <Link href={`/subjects/${subjectId}/roadmap/concepts/${m.c.id}`}
                  aria-label={`Milestone ${m.index + 1}: ${m.c.title}. ${status}.`}
                  aria-current={conceptId === m.c.id ? "true" : m.status === "current" ? "step" : undefined}
                  className={`rj-node ${conceptId === m.c.id ? "rj-selected" : ""}`}>
                  {m.status === "done" ? <span aria-hidden>{st[2] ? "★" : "✓"}</span>
                    : m.status === "locked" ? <svg aria-hidden width="26" height="26" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2" fill="currentColor" /><path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" strokeWidth="2.4" /></svg>
                    : <span aria-hidden>{m.index + 1}</span>}
                </Link>
                <div className={`rj-label ${labelLeft ? "rj-label-left" : "rj-label-right"}`} aria-hidden>
                  <span className="rj-step">Milestone {m.index + 1}</span>
                  <span className="rj-title">{m.c.title}</span>
                  {m.status !== "locked" && <span className="rj-stars">{st.map((on) => (on ? "★" : "☆")).join("")}</span>}
                  {m.status === "locked" && m.achieved && <span className="rj-saved">progress saved</span>}
                </div>
                <div className="rj-tip" role="tooltip" aria-hidden>
                  <p className="font-bold">{m.c.title}</p>
                  <p className="text-meta">
                    {m.status === "done"
                      ? (m.c.placement_status === "known" && !st[2] ? "Done — known from your level test." : "Done — applied on your own.")
                      : m.status === "current"
                      ? "Your next milestone. Apply it once without help to unlock the next one."
                      : `Unlocks after “${m.previous?.title}”.`}
                  </p>
                  {m.c.evidence?.attempts > 0 && <p className="text-meta text-ink-muted">{m.c.evidence.attempts} attempt{m.c.evidence.attempts === 1 ? "" : "s"}</p>}
                </div>
                {burstAt === m.index && <Burst />}
              </li>
            );
          })}
        </ol>

        {quests.map((q) => (
          <Link key={q.f.id} href={`/subjects/${subjectId}/roadmap/concepts/${q.f.id}`} aria-label={`Optional side quest: ${q.f.title}`}
            className="rj-quest" style={{ left: q.x, top: q.y }} title={`Optional refresher: ${q.f.title}`}><span>{q.f.key}</span></Link>
        ))}

        {/* you are here */}
        {pin && !finished && current && (
          <div className="rj-pin" style={{ left: pin.x, top: pin.y }} aria-hidden>
            <span className="rj-pin-flag">You are here</span>
            <svg width="34" height="44" viewBox="0 0 34 44"><path d="M17 43C17 43 3 26 3 16a14 14 0 0 1 28 0c0 10-14 27-14 27Z" fill="var(--ink)" /><circle cx="17" cy="16" r="6.5" fill="var(--discovery)" /></svg>
          </div>
        )}

        {/* finish */}
        <div id="rj-finish" className={`rj-finish ${finished ? "rj-finish-on" : ""}`} style={{ left: L.finish.x, top: L.finish.y + 34 }}>
          <span aria-hidden className="text-2xl">{finished ? "🏆" : "🏁"}</span>
          <span className="font-bold">{finished ? "Finish line — subject complete!" : "Finish line"}</span>
          {!finished && <span className="text-meta">{total - doneCount} milestone{total - doneCount === 1 ? "" : "s"} to go</span>}
        </div>
      </div>

      {toast && <div className="rj-toast" role="status">🎉 {toast}</div>}
    </div>
  );
}

function Burst() {
  const parts = useMemo(() => Array.from({ length: 22 }, (_, i) => {
    const a = (i / 22) * Math.PI * 2;
    const d = 60 + (i % 5) * 16;
    return { dx: Math.cos(a) * d, dy: Math.sin(a) * d, r: (i * 47) % 360, c: i % 3 };
  }), []);
  return (
    <span className="rj-burst" aria-hidden>
      {parts.map((p, i) => <i key={i} className={`rj-bit rj-bit-${p.c}`} style={{ ["--dx" as any]: `${p.dx}px`, ["--dy" as any]: `${p.dy}px`, ["--r" as any]: `${p.r}deg` }} />)}
    </span>
  );
}
