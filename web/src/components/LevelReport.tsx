"use client";
import { Illo, type IlloName } from "./Illo";
// Starting level on a subject (placement test or "start from scratch") + the metrics behind it. Every number is
// explained; the level formula is shown, never hidden.

const LEVEL_STYLE: Record<string, { icon: IlloName; ring: string }> = {
  beginner: { icon: "beginner", ring: "bg-soft" },
  intermediate: { icon: "intermediate", ring: "bg-success-surface" },
  advanced: { icon: "advanced", ring: "bg-hl" },
  expert: { icon: "expert", ring: "bg-hl" },
};
const ORDER = ["beginner", "intermediate", "advanced", "expert"];
const STATUS = {
  known: { label: "Known", cls: "bg-hl text-ink" },
  partly: { label: "Partly", cls: "bg-soft text-soft-fg" },
  to_learn: { label: "To learn", cls: "bg-surface text-ink" },
} as const;

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="game-card p-4">
      <p className="text-meta text-ink-muted">{label}</p>
      <p className="text-section">{value}</p>
      {hint && <p className="text-meta text-ink-muted">{hint}</p>}
    </div>
  );
}

export function LevelReport({ report, compact = false }: { report: any; compact?: boolean }) {
  if (!report?.available) return null;
  const st = LEVEL_STYLE[report.level] ?? LEVEL_STYLE.beginner;
  const m = report.metrics;
  return (
    <div className="space-y-5" data-testid="level-report">
      <div className="hero p-6 md:p-8">
        <div className="relative z-10 flex flex-wrap items-center gap-5">
          <span aria-hidden className={`flex h-20 w-20 items-center justify-center rounded-pill border-2 border-ink ${st.ring}`}><Illo name={st.icon} size={52} /></span>
          <div className="flex-1">
            <p className="text-meta font-bold uppercase tracking-wide">Your starting level</p>
            <h2 className="text-page-compact" data-testid="level-label">{report.level_label}</h2>
            <p className="muted">{report.description}</p>
          </div>
          {report.basis === "placement_test" && (
            <div className="text-right"><p className="text-hero font-bold leading-none">{report.score}</p><p className="text-meta">/ 100</p></div>
          )}
        </div>
        <ol className="relative z-10 mt-5 grid grid-cols-4 gap-2" aria-label="Level scale">
          {ORDER.map((l) => (
            <li key={l} className={`rounded-pill border-2 border-ink px-2 py-1 text-center text-meta font-bold capitalize ${l === report.level ? "bg-ink text-white" : "bg-surface"}`}>{l}</li>
          ))}
        </ol>
      </div>
      <p className="text-meta text-ink-muted">{report.explanation}</p>

      {m && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Answers" value={`${m.correct}/${m.answered}`} hint={`${m.accuracy}% correct · ${m.dont_know} “I don't know”`} />
          <Stat label="Estimated mastery" value={`${m.estimated_mastery}%`} hint="across the roadmap concepts" />
          <Stat label="Weighted accuracy" value={`${m.weighted_accuracy}%`} hint="hard questions count ×2" />
          <Stat label="Time per answer" value={m.avg_seconds != null ? `${m.avg_seconds}s` : "—"} hint={m.rapid_guesses ? `${m.rapid_guesses} very fast answer(s)` : "no rushed answers"} />
        </div>
      )}

      {m && !compact && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="game-card p-5">
            <h3 className="text-section !text-[1.2rem]">By difficulty</h3>
            <ul className="mt-3 space-y-3">
              {Object.entries(m.by_difficulty).map(([d, v]: [string, any]) => (
                <li key={d}>
                  <div className="flex justify-between text-meta"><span className="capitalize">{d}</span><span>{v.asked ? `${v.correct}/${v.asked}` : "not asked"}</span></div>
                  <div className="bar" role="progressbar" aria-label={`${d} questions correct`} aria-valuemin={0} aria-valuemax={Math.max(1, v.asked)} aria-valuenow={v.correct}>
                    <span style={{ width: `${v.asked ? Math.round((100 * v.correct) / v.asked) : 0}%` }} />
                  </div>
                </li>
              ))}
            </ul>
            {m.calibration_line && <p className="mt-4 text-meta"><strong>Confidence:</strong> {m.calibration_line}</p>}
          </div>
          <div className="game-card p-5">
            <h3 className="text-section !text-[1.2rem]">What we noticed</h3>
            {m.strengths.length > 0 && <p className="mt-3"><strong>Strengths:</strong> {m.strengths.join(", ")}</p>}
            {m.gaps.length > 0 && <p className="mt-2"><strong>To work on:</strong> {m.gaps.join(", ")}</p>}
            {m.misconceptions.length > 0 && (
              <div className="mt-2"><strong>Possible mistakes detected:</strong>
                <ul className="ml-5 list-disc">{m.misconceptions.map((x: any) => <li key={x.code}>{x.label}{x.concept ? ` (${x.concept})` : ""}</li>)}</ul>
              </div>
            )}
            {(m.low_confidence || m.needs_retest) && <p className="mt-3 text-meta text-review">Few answers so far — this level is a first estimate and will be refined while you practise.</p>}
            {m.evidence_note && <p className="mt-3 text-meta text-ink-muted">{m.evidence_note}</p>}
          </div>
        </div>
      )}

      {!compact && (
        <div className="game-card p-5">
          <h3 className="text-section !text-[1.2rem]">Concept by concept</h3>
          <div className="mt-3 space-y-4">
            {report.by_unit.map((u: any) => (
              <div key={u.unit_no}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-bold">Unit {u.unit_no}{u.title ? ` · ${u.title}` : ""}</p>
                  <p className="text-meta text-ink-muted">{u.known} known · {u.partly} partly · {u.to_learn} to learn</p>
                </div>
                <div className="mt-1 flex h-3 overflow-hidden rounded-pill border-2 border-ink" aria-hidden>
                  <span className="bg-strong" style={{ width: `${(100 * u.known) / u.total}%` }} />
                  <span className="bg-soft" style={{ width: `${(100 * u.partly) / u.total}%` }} />
                </div>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {report.concepts.filter((c: any) => c.unit_no === u.unit_no).map((c: any) => (
                    <li key={c.concept_id} className={`rounded-pill border-2 border-ink px-3 py-1 text-meta ${STATUS[c.status as keyof typeof STATUS].cls}`}
                      title={c.evidence}>
                      <span className="font-bold">{c.key}</span> {c.title} · {STATUS[c.status as keyof typeof STATUS].label}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
