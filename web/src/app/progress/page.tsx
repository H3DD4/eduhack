"use client";
// G04 Progress — metrics, not a second subject list: overall numbers, 12-week activity, level distribution, and per
// subject the concept graph (shaded by the learner engine's level), strengths, gaps, detected mistakes, reviews due.
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ConceptGraph, LEVEL_NAMES, LEVEL_RAMP, LevelLegend } from "@/components/ConceptGraph";
import { ErrorBox, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="game-card p-4">
      <p className="text-meta text-ink-muted">{label}</p>
      <p className="text-section">{value}</p>
      {hint && <p className="text-meta text-ink-muted">{hint}</p>}
    </div>
  );
}

const HEAT = ["#EEF2F0", "#C9EED5", "#8ED9A6", "#3FB874", "#147F51"];

function Activity({ days }: { days: { date: string; events: number }[] }) {
  const [tip, setTip] = useState<string | null>(null);
  const max = Math.max(1, ...days.map((d) => d.events));
  const step = (n: number) => (n === 0 ? 0 : Math.min(4, Math.ceil((4 * n) / max)));
  const weeks: { date: string; events: number }[][] = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
  return (
    <div>
      <div className="flex gap-1 overflow-x-auto" role="img" aria-label={`Activity over the last ${days.length} days`}>
        {weeks.map((w, i) => (
          <div key={i} className="flex flex-col gap-1">
            {w.map((d) => (
              <span key={d.date} className="h-4 w-4 rounded-[4px] border border-ink/10"
                style={{ background: HEAT[step(d.events)] }}
                onMouseEnter={() => setTip(`${d.date}: ${d.events} learning event(s)`)} onMouseLeave={() => setTip(null)}
                title={`${d.date}: ${d.events} learning event(s)`} />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-2 text-meta text-ink-muted">
        <span>Less</span>{HEAT.map((c) => <span key={c} className="h-3 w-3 rounded-[3px]" style={{ background: c }} aria-hidden />)}<span>More</span>
        <span className="ml-3" aria-live="polite">{tip}</span>
      </div>
    </div>
  );
}

export default function Progress() {
  const { data, error, reload } = useApi<any>("/me/progress-metrics");
  const o = data?.overview;
  const totalLv = data ? data.level_distribution.reduce((a: number, x: any) => a + x.count, 0) : 0;
  return (
    <AppShell crumbs={[{ label: "Progress" }]}>
      <div className="space-y-8" data-screen="G04">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-page-compact lg:text-page">Your progress</h1>
            <p className="text-ink-muted">Your levels, what you master, what is left, and how you learn — from your own answers.</p>
          </div>
          <Link href="/subjects" className="btn-secondary">My subjects</Link>
        </div>
        {!data && !error && <div className="card"><Skeleton lines={6} /></div>}
        {error && <ErrorBox message="Progress could not load." onRetry={reload} />}
        {data && (
          <>
            <section aria-labelledby="ov-h" className="space-y-3">
              <h2 id="ov-h" className="sr-only">Overview</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Tile label="Concepts at Proficient or above" value={`${o.concepts_proficient}/${o.concepts_total}`} hint={`${o.subjects} subject(s)`} />
                <Tile label="Answers" value={o.answers} hint={o.accuracy != null ? `${o.accuracy}% correct` : "none yet"} />
                <Tile label="Solved without help" value={o.independent_pct != null ? `${o.independent_pct}%` : "—"} hint="of your answers" />
                <Tile label="Streak" value={`${o.streak_days} day(s)`} hint={`${o.active_days_30} active day(s) in 30`} />
                <Tile label="Explain-backs" value={o.explain_backs} hint="explained in your own words" />
                <Tile label="Sessions completed" value={o.sessions_completed} />
                <Tile label="Mistakes detected" value={o.misconceptions_seen} hint={`${o.misconceptions_resolved} fixed`} />
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
              <div className="game-card p-5">
                <h2 className="text-section !text-[1.2rem]">Activity · last 12 weeks</h2>
                <div className="mt-3"><Activity days={data.activity} /></div>
              </div>
              <div className="game-card p-5">
                <h2 className="text-section !text-[1.2rem]">Concepts by level</h2>
                {totalLv === 0 ? <p className="mt-2 text-ink-muted">No concepts yet.</p> : (
                  <>
                    <div className="mt-3 flex h-6 overflow-hidden rounded-pill border-2 border-ink" role="img"
                      aria-label={data.level_distribution.map((x: any) => `${x.label}: ${x.count}`).join(", ")}>
                      {data.level_distribution.filter((x: any) => x.count).map((x: any) => (
                        <span key={x.level} title={`${x.label}: ${x.count}`} style={{ width: `${(100 * x.count) / totalLv}%`, background: LEVEL_RAMP[x.level] }}
                          className="border-r-2 border-surface last:border-r-0" />
                      ))}
                    </div>
                    <ul className="mt-3 grid grid-cols-2 gap-1 text-meta sm:grid-cols-3">
                      {data.level_distribution.map((x: any) => (
                        <li key={x.level} className="flex items-center gap-2">
                          <span aria-hidden className="h-3 w-3 rounded-full border border-ink/40" style={{ background: LEVEL_RAMP[x.level] }} />
                          {LEVEL_NAMES[x.level]} <strong>{x.count}</strong>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </section>

            <section aria-labelledby="subj-h" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 id="subj-h" className="text-section">By subject</h2>
                <LevelLegend />
              </div>
              {data.subjects.length === 0 && (
                <div className="game-card p-6"><p>No subjects yet.</p><Link className="btn-primary mt-3" href="/subjects/new">Start learning</Link></div>
              )}
              {data.subjects.map((s: any) => (
                <article key={s.id} className="game-card space-y-4 p-5" data-testid="progress-subject">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="flex-1 text-section !text-[1.3rem]">{s.name}</h3>
                    {s.level && <span className="badge">Level: {s.level}{s.score != null ? ` · ${s.score}/100` : ""}</span>}
                    {s.exam_date && <span className="badge">🎯 Exam {s.exam_date}</span>}
                    <Link className="btn-secondary" href={s.href}>Open</Link>
                  </div>
                  {!s.ready ? <p className="text-ink-muted">Roadmap not confirmed yet.</p> : (
                    <>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        <Tile label="Proficient" value={`${s.proficient}/${s.total}`} />
                        <Tile label="Estimated mastery" value={`${s.mastery_pct}%`} />
                        <Tile label="Accuracy" value={s.accuracy != null ? `${s.accuracy}%` : "—"} hint={`${s.answers} answer(s)`} />
                        <Tile label="Without help" value={s.independent_pct != null ? `${s.independent_pct}%` : "—"} />
                        <Tile label="Reviews due" value={s.reviews_due} hint={`${s.explain_backs} explain-back(s)`} />
                      </div>
                      <ConceptGraph nodes={s.nodes} />
                      <div className="grid gap-3 md:grid-cols-3 text-meta">
                        <p><strong>You master:</strong> {s.strengths.length ? s.strengths.join(", ") : "nothing at Proficient yet"}</p>
                        <p><strong>Still to learn:</strong> {s.gaps.length ? s.gaps.join(", ") : "—"}</p>
                        <p><strong>Mistakes noticed:</strong> {s.misconceptions.length ? s.misconceptions.map((m: any) => `${m.id.replace(/_/g, " ")} (${m.status})`).join(", ") : "none"}</p>
                      </div>
                      {s.next && (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-detail bg-soft p-3">
                          <p><strong>Next:</strong> {s.next.title} — <span className="text-ink-muted">{s.next.reason}</span></p>
                          <Link className="btn-primary" href={s.next.href}>Continue</Link>
                        </div>
                      )}
                    </>
                  )}
                </article>
              ))}
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}
