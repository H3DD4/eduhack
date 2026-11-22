// ThinkFirst spot illustrations — one hand-built SVG set that replaces the emojis.
// Style rules (keep new icons consistent): 48×48 grid · 2px ink outline, round joins · flat fills from the theme
// (primary = --tf-strong/--action, accent = --discovery, paper = --surface, tint = primary mixed into paper) · the main object
// casts the same hard 2px ink shadow as the app's cards. Colours follow the theme, so the set fits green and orange.
import type { ReactNode } from "react";

const INK = "var(--ink)";
const P = "var(--tf-strong, var(--action))";
const A = "var(--discovery)";
const W = "var(--surface)";
const T = "color-mix(in srgb, var(--tf-strong, var(--action)) 22%, var(--surface))";
const line = { stroke: INK, strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

/** Draws `children` twice: a hard ink shadow offset by (2,2), then the shape itself. */
function Lift({ children }: { children: ReactNode }) {
  return (<><g transform="translate(2 2)" fill={INK} stroke={INK} strokeWidth={2} strokeLinejoin="round">{children}</g>{children}</>);
}

const Sparkle = ({ x, y, s = 1 }: { x: number; y: number; s?: number }) => (
  <path transform={`translate(${x} ${y}) scale(${s})`} d="M0 -5 Q1 -1 5 0 Q1 1 0 5 Q-1 1 -5 0 Q-1 -1 0 -5 Z" fill={A} {...line} strokeWidth={1.5} />
);

const ICONS = {
  /** I'm preparing for an exam: a test sheet with ticked answers and a stopwatch. */
  exam: (
    <>
      <Lift><rect x="9" y="5" width="25" height="33" rx="3" fill={W} {...line} /></Lift>
      {[12, 20, 28].map((y, i) => (
        <g key={y}>
          <rect x="13" y={y} width="6" height="6" rx="1.5" fill={i < 2 ? P : W} {...line} strokeWidth={1.6} />
          {i < 2 && <path d={`M14.6 ${y + 3.1} l1.5 1.5 l2.6 -3`} fill="none" stroke={W} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />}
          <path d={`M22 ${y + 3} H${i === 2 ? 26 : 30}`} {...line} opacity={i === 2 ? 0.45 : 1} />
        </g>
      ))}
      <Lift><circle cx="35" cy="35" r="8.5" fill={A} {...line} /></Lift>
      <rect x="33" y="23.5" width="4" height="3.5" rx="1" fill={P} {...line} strokeWidth={1.6} />
      <path d="M35 35 V30 M35 35 L38 36.5" {...line} strokeWidth={2.2} />
    </>
  ),
  /** I want to learn something new: a trail climbing to a flag — the start of a journey. */
  explore: (
    <>
      <Lift><path d="M3 41 C10 31 15 27 21 29 C26 22 29 13 32 13 C36 13 40 27 45 41 Z" fill={P} {...line} /></Lift>
      <path d="M10 41 C15 36 22 37 22 32 C22 27 29 25 31.5 17" fill="none" stroke={W} strokeWidth={2.2} strokeDasharray="2.5 3.2" strokeLinecap="round" />
      <path d="M32 13 V3.5" {...line} />
      <path d="M32 4 L41.5 7 L32 10 Z" fill={A} {...line} strokeWidth={1.8} />
      <path d="M2 41 H46" {...line} />
      <Sparkle x={9} y={11} s={0.8} />
    </>
  ),
  /** Yes — use my course: your own pages, with a highlighted line and a bookmark. */
  course: (
    <>
      <rect x="15" y="4" width="22" height="29" rx="3" fill={T} {...line} transform="rotate(9 26 18)" />
      <Lift><path d="M13 8 H24 L32 16 V38 A3 3 0 0 1 29 41 H13 A3 3 0 0 1 10 38 V11 A3 3 0 0 1 13 8 Z" fill={W} {...line} /></Lift>
      <path d="M24 8 V16 H32" fill={T} {...line} />
      <rect x="13" y="24" width="13" height="5.5" rx="1.8" fill={A} />
      <path d="M14.5 21 H22 M14.5 26.8 H28 M14.5 32.6 H26 M14.5 37 H20" {...line} strokeWidth={1.8} />
      <path d="M36.5 5 V19 L39.8 16.4 L43 19 V5 Z" fill={P} {...line} strokeWidth={1.8} />
    </>
  ),
  /** No — find the material for me: the open world of knowledge rising from a book. */
  sources: (
    <>
      <Lift><circle cx="24" cy="18" r="12" fill={P} {...line} /></Lift>
      <ellipse cx="24" cy="18" rx="5" ry="12" fill="none" stroke={W} strokeWidth={1.6} />
      <path d="M12 18 H36 M14 12 Q24 15 34 12 M14 24 Q24 21 34 24" fill="none" stroke={W} strokeWidth={1.5} strokeLinecap="round" />
      <circle cx="24" cy="18" r="12" fill="none" {...line} />
      <Lift><path d="M4 33 Q14 29.5 24 33 V43 Q14 39.5 4 43 Z" fill={W} {...line} /></Lift>
      <path d="M24 33 Q34 29.5 44 33 V43 Q34 39.5 24 43 Z" fill={W} {...line} />
      <path d="M8 36.5 Q13 35 19 36 M29 36 Q35 35 40 36.5" {...line} strokeWidth={1.5} opacity={0.5} />
      <Sparkle x={41} y={8} />
      <Sparkle x={6} y={9} s={0.7} />
    </>
  ),
  /** Yes — test my level: a level meter finding where you are. */
  levelTest: (
    <>
      <Lift><path d="M3 34 A21 21 0 0 1 45 34 Z" fill={W} {...line} /></Lift>
      <path d="M9.5 34 A14.5 14.5 0 0 1 16.75 21.44" fill="none" stroke={T} strokeWidth={7} />
      <path d="M16.75 21.44 A14.5 14.5 0 0 1 31.25 21.44" fill="none" stroke={A} strokeWidth={7} />
      <path d="M31.25 21.44 A14.5 14.5 0 0 1 38.5 34" fill="none" stroke={P} strokeWidth={7} />
      <path d="M3 34 A21 21 0 0 1 45 34 Z" fill="none" {...line} />
      <path d="M24 34 L31 22" {...line} strokeWidth={3} />
      <circle cx="24" cy="34" r="3.6" fill={INK} />
      <Lift><rect x="9" y="37" width="30" height="6" rx="3" fill={P} {...line} /></Lift>
      <path d="M15 40 H22" stroke={W} strokeWidth={1.8} strokeLinecap="round" />
    </>
  ),
  /** No — start from scratch: the first block on the ground, the next one on its way. */
  scratch: (
    <>
      <path d="M3 42 H45" {...line} />
      <Lift><rect x="7" y="28" width="15" height="14" rx="2.5" fill={P} {...line} /></Lift>
      <path d="M12.8 32.2 L15.5 30.6 V38.8" fill="none" stroke={W} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      <rect x="25" y="28.5" width="14" height="13.5" rx="2.5" fill="none" {...line} strokeDasharray="2.5 2.6" opacity={0.55} />
      <g transform="rotate(-12 31.5 15.5)">
        <Lift><rect x="25" y="9" width="13" height="13" rx="2.5" fill={A} {...line} /></Lift>
        <path d="M31.5 12.5 V18.5 M28.5 15.5 H34.5" stroke={INK} strokeWidth={2} strokeLinecap="round" />
      </g>
      <path d="M29 26 V28 M33.5 25 V27.5" {...line} strokeWidth={1.6} opacity={0.5} />
      <Sparkle x={42} y={8} s={0.8} />
    </>
  ),
  /** The topic you typed: a book of its own with a ribbon marker. */
  topic: (
    <>
      <rect x="11" y="38" width="27" height="5" rx="1.5" fill={W} {...line} strokeWidth={1.6} />
      <Lift><rect x="9" y="5" width="29" height="35" rx="3" fill={P} {...line} /></Lift>
      <path d="M15 5 V40" {...line} opacity={0.6} />
      <rect x="19" y="21" width="14" height="8" rx="1.6" fill={W} {...line} strokeWidth={1.6} />
      <path d="M22 25 H30" {...line} strokeWidth={1.5} />
      <path d="M27 5 V16 L30 13.6 L33 16 V5" fill={A} {...line} strokeWidth={1.8} />
    </>
  ),
  /** The roadmap: a folded map with the route and where you are heading. */
  roadmap: (
    <>
      <Lift><path d="M4 10 L16 6 L31 10 L44 6 V38 L31 42 L16 38 L4 42 Z" fill={W} {...line} /></Lift>
      <path d="M16 6 L31 10 V42 L16 38 Z" fill={T} {...line} />
      <path d="M9 34 C14 26 21 31 24 23 S32 18 36 15.5" fill="none" stroke={P} strokeWidth={2.6} strokeDasharray="3 3" strokeLinecap="round" />
      <circle cx="9" cy="34" r="2.6" fill={P} {...line} strokeWidth={1.6} />
      <path d="M37 21 C37 21 31.5 15 31.5 11.5 A5.5 5.5 0 0 1 42.5 11.5 C42.5 15 37 21 37 21 Z" fill={A} {...line} strokeWidth={1.8} />
      <circle cx="37" cy="11.5" r="2" fill={INK} />
    </>
  ),
  /** The course summary: a revision sheet and a pen. */
  summary: (
    <>
      <Lift><rect x="7" y="5" width="26" height="35" rx="3" fill={W} {...line} /></Lift>
      <rect x="11" y="10" width="18" height="5.5" rx="1.6" fill={P} />
      {[22, 28, 34].map((y) => (
        <g key={y}><circle cx="13" cy={y} r="1.9" fill={A} {...line} strokeWidth={1.2} /><path d={`M17 ${y} H${y === 34 ? 24 : 29}`} {...line} strokeWidth={1.8} /></g>
      ))}
      <g transform="rotate(35 37 26)">
        <Lift><rect x="34" y="11" width="6.5" height="23" rx="1.6" fill={A} {...line} /></Lift>
        <rect x="34" y="11" width="6.5" height="5.5" rx="1.6" fill={P} {...line} />
        <path d="M34 34 L37.25 40 L40.5 34 Z" fill={W} {...line} />
      </g>
    </>
  ),
  /** Start learning: a light bulb with a play button — thinking first, then doing. */
  learn: (
    <>
      <path d="M24 1.5 V4.5 M8.5 7.5 L10.8 9.8 M39.5 7.5 L37.2 9.8 M3.5 19.5 H6.5 M44.5 19.5 H41.5" {...line} />
      <Lift><path d="M24 7 A12 12 0 0 1 31 28.7 V33 H17 V28.7 A12 12 0 0 1 24 7 Z" fill={A} {...line} /></Lift>
      <path d="M21.4 13.6 L30.2 19.4 L21.4 25.2 Z" fill={W} {...line} strokeWidth={1.8} />
      <Lift><rect x="16.5" y="33" width="15" height="4.5" rx="1.4" fill={P} {...line} /></Lift>
      <rect x="19" y="37.5" width="10" height="4.5" rx="2.2" fill={P} {...line} />
    </>
  ),
} satisfies Record<string, ReactNode>;

/** Level tiers: steps, filled up to your level; the flag shows where you stand, expert reaches the star. */
function Steps({ n }: { n: 1 | 2 | 3 | 4 }) {
  const steps = [{ x: 5, y: 32, h: 10 }, { x: 17, y: 24, h: 18 }, { x: 29, y: 16, h: 26 }];
  const top = steps[Math.min(n, 3) - 1];
  return (
    <>
      {steps.map((s, i) => (
        <Lift key={i}><rect x={s.x} y={s.y} width="13" height={s.h} rx="2" fill={i < n ? P : W} {...line} /></Lift>
      ))}
      <path d="M3 42 H45" {...line} />
      {n < 4 ? (
        <>
          <path d={`M${top.x + 6.5} ${top.y} V${top.y - 11}`} {...line} />
          <path d={`M${top.x + 6.5} ${top.y - 11} L${top.x + 14} ${top.y - 8.5} L${top.x + 6.5} ${top.y - 6} Z`} fill={A} {...line} strokeWidth={1.6} />
        </>
      ) : (
        <path d="M35.5 2.5 L37.6 7.4 L42.8 7.8 L38.8 11.2 L40 16.3 L35.5 13.6 L31 16.3 L32.2 11.2 L28.2 7.8 L33.4 7.4 Z" fill={A} {...line} strokeWidth={1.7} />
      )}
    </>
  );
}
const LEVELS = {
  beginner: <Steps n={1} />, intermediate: <Steps n={2} />, advanced: <Steps n={3} />, expert: <Steps n={4} />,
};

export type IlloName = keyof typeof ICONS | keyof typeof LEVELS;
export const ILLO_NAMES = [...Object.keys(ICONS), ...Object.keys(LEVELS)] as IlloName[];

/** Decorative by default (aria-hidden). Pass `title` when the picture carries meaning on its own. */
export function Illo({ name, size = 40, title, className = "" }: { name: IlloName; size?: number; title?: string; className?: string }) {
  const art = (ICONS as Record<string, ReactNode>)[name] ?? (LEVELS as Record<string, ReactNode>)[name];
  return (
    <svg viewBox="0 0 48 48" width={size} height={size} className={`illo inline-block shrink-0 align-middle ${className}`}
      role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title} focusable="false">
      {art}
    </svg>
  );
}
