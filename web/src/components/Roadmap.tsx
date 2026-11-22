"use client";
// W01 Roadmap + W06 Concept inspector — UC08/UC09. Journey map from Start to the Finish line (RoadmapJourney):
// milestones unlock strictly in order — one lights up only when the previous one is achieved (applied on your
// own, or proven known on the level test). Optional foundation side quests never gate. A List view with the
// same states is always available.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ACHIEVED_STATES, buildJourney, RoadmapJourney } from "./RoadmapJourney";
import { SubjectShell } from "./SubjectShell";
import { Companion, ErrorBox, EvidencePill, Skeleton } from "./ui";
import { Illo } from "./Illo";

export function labelText(st: string) {
  return ({ introduced: "Introduced", practised_with_support: "Practised with support", explained: "Explained back",
    applied_independently: "Applied independently (no in-app help)", recalled_later: "Recalled later",
    insufficient_evidence: "Insufficient evidence" } as Record<string, string>)[st] || st;
}

function Evidence({ e }: { e: any }) {
  if (!e || !e.states?.length) return <span className="pill text-ink-muted">Not checked yet</span>;
  return (
    <span className="flex flex-wrap items-center gap-1">
      {e.states.map((st: string) => <EvidencePill key={st} label={st} text={labelText(st)} />)}
      <span className="text-meta text-ink-muted">based on {e.attempts} attempt{e.attempts === 1 ? "" : "s"}</span>
      {e.review_due_on && <span className="pill text-ink">Review {new Date(e.review_due_on + "T00:00:00").toLocaleDateString()}</span>}
    </span>
  );
}

/** Strict: a locked milestone can be previewed but not started. Set to false to only dim locked milestones. */
export const ROADMAP_STRICT_GATING = true;

function nodeClass(status: string) {
  return status === "done" ? "node-applied" : status === "current" ? "node-progress node-current" : "node-new opacity-60 grayscale";
}

export function RoadmapView({ subjectId, conceptId }: { subjectId: string; conceptId?: string }) {
  const router = useRouter();
  const { data, error, loading, reload } = useApi<any>(`/subjects/${subjectId}/roadmap`);
  const detail = useApi<any>(conceptId ? `/subjects/${subjectId}/concepts/${conceptId}` : null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<"map" | "list">("map");
  useEffect(() => {
    try { const v = localStorage.getItem("tf_roadmap_view"); if (v === "list" || v === "map") setView(v); } catch { /* noop */ }
  }, []);
  const choose = (v: "map" | "list") => { setView(v); try { localStorage.setItem("tf_roadmap_view", v); } catch { /* noop */ } };

  const start = async (cid: string, kind = "learn") => {
    setBusy(true);
    try {
      const r = await api(`/subjects/${subjectId}/sessions`, { method: "POST", json: { concept_id: cid, kind } });
      router.push(`/subjects/${subjectId}/sessions/${r.session.id}/setup`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const journey = useMemo(() => (data?.units ? buildJourney(data.units) : []), [data]);
  const byId = useMemo(() => Object.fromEntries(journey.map((m) => [m.c.id, m])), [journey]);
  const currentMs = journey.find((m) => m.status === "current");
  const suggested = currentMs?.c.id;   // the next milestone in order (the server suggestion may point further ahead)
  const selected = conceptId ? byId[conceptId] : undefined;
  const locked = ROADMAP_STRICT_GATING && selected?.status === "locked";
  const resume = data?.resume;
  const primary = conceptId || data?.placement?.required ? null : resume ? (
    <Link className="btn-primary" href={`/subjects/${subjectId}/sessions/${resume.session_id}${resume.status === "draft" ? "/setup" : ""}`}>▶ Resume “{resume.concept_title}”</Link>
  ) : suggested ? (
    <button className="btn-primary" onClick={() => start(suggested)} disabled={busy}>▶ Continue: {currentMs?.c.title}</button>
  ) : null;
  const allFoundations = data ? data.units.flatMap((u: any) => u.foundations) : [];
  const counts = data?.counts;
  const selectedAchievedByEvidence = !!selected?.c?.evidence?.states?.some((s: string) => ACHIEVED_STATES.includes(s));

  return (
    <SubjectShell subjectId={subjectId} action={primary} crumb={conceptId ? "Concept" : "Roadmap"} parent={conceptId ? "roadmap" : undefined}>
      {loading && !data && <div className="card"><Skeleton lines={5} label="Loading roadmap" /></div>}
      {error && <ErrorBox message="The roadmap could not load." onRetry={reload} />}
      {err && <ErrorBox message={err} />}
      {data && data.subject.status !== "ready" && (
        <div className="card"><p>Confirm this subject&apos;s roadmap to see the map.</p>
          <Link className="btn-primary mt-4" href={`/subjects/${subjectId}/setup`}>Review roadmap</Link></div>
      )}
      {data && data.subject.status === "ready" && data.placement?.required && !conceptId && (
        <div className="hero p-6 md:p-10" data-screen="W01-locked">
          <div className="relative z-10 max-w-2xl space-y-3">
            <span className="badge"><Illo name="levelTest" size={20} /> Level test first</span>
            <h2 className="text-page-compact">Your roadmap is built on your level</h2>
            <p className="muted">Take the short level test first. Then this map shows what you already know (✓), where you start (▶) and what is left to learn.</p>
            <div className="flex flex-wrap gap-3">
              <Link className="btn-primary" href={`/subjects/${subjectId}/diagnostic`}>
                {data.placement.state === "preparing" ? "Open the level test (questions almost ready)" : data.placement.state === "in_progress" ? "Continue the level test" : "Take the level test"}
              </Link>
              <button className="btn-secondary" disabled={busy} onClick={async () => {
                setBusy(true);
                await api(`/subjects/${subjectId}/intent`, { method: "PATCH", json: { prior_knowledge: "none" } }).catch((e) => setErr(e.message));
                setBusy(false);
                reload();
              }}>Skip the test — start from scratch</button>
            </div>
          </div>
        </div>
      )}
      {data && data.subject.status === "ready" && (!data.placement?.required || conceptId) && (
        <div className="grid gap-6 xl:grid-cols-[1fr_340px]" data-screen={conceptId ? "W06" : "W01"}>
          <div className="min-w-0">
            {data.level && !conceptId && (
              <div className="game-card mb-5 flex flex-wrap items-center gap-3 p-4" data-testid="roadmap-level">
                <span className="badge"><Illo name={data.level.basis === "placement_test" ? "levelTest" : "scratch"} size={20} /> Built on your level: <strong>{data.level.label}</strong>
                  {data.level.basis === "placement_test" ? ` · ${data.level.score}/100` : ""}</span>
                <span className="text-meta text-ink-muted">
                  {data.level.basis === "placement_test"
                    ? `${data.level.known} concept(s) already known (✓), ${data.level.to_learn} to learn. Practice difficulty starts at your level.`
                    : "Starting from scratch: every level is new and explained step by step."}
                </span>
                <Link className="btn-link ml-auto" href={`/subjects/${subjectId}/start#level`}>Level details</Link>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-4">
                <div>
                  <p className="font-bold">Your journey · {journey.length} milestones</p>
                  <p className="text-meta text-ink-muted">{counts?.started ?? 0} started · ★ practised · ★★ explained · ★★★ applied without help · the next milestone unlocks at ★★★</p>
                </div>
              </div>
              <div role="group" aria-label="Roadmap view" className="flex gap-1">
                <button className={view === "map" ? "chip !border-action" : "chip"} aria-pressed={view === "map"} onClick={() => choose("map")}><Illo name="roadmap" size={20} /> Map</button>
                <button className={view === "list" ? "chip !border-action" : "chip"} aria-pressed={view === "list"} onClick={() => choose("list")}>☰ List</button>
              </div>
            </div>
            {view === "map" ? (
              <RoadmapJourney units={data.units} subjectId={subjectId} conceptId={conceptId} foundations={allFoundations} />
            ) : data.units.map((u: any) => (
              <section key={u.unit_no} aria-labelledby={`u-${u.unit_no}`} className="mt-8">
                <div className="unit-banner flex items-center justify-between gap-3 px-5 py-4">
                  <h2 id={`u-${u.unit_no}`} className="text-section !text-[1.25rem]">Unit {u.unit_no}: {u.title}</h2>
                  <span className="text-meta font-bold">{u.concepts.filter((c: any) => byId[c.id]?.status === "done").length}/{u.concepts.length} ✓</span>
                </div>
                <ol className="relative mt-4 space-y-4 border-l-4 border-border pl-6" aria-label={`Unit ${u.unit_no} path`}>
                  {(u.concepts.length ? u.concepts : u.foundations).map((c: any) => {
                    const m = byId[c.id];
                    const st = m?.status || "locked";
                    return (
                      <li key={c.id}>
                        <Link href={`/subjects/${subjectId}/roadmap/concepts/${c.id}`}
                          className={`game-card flex min-h-[64px] items-center gap-4 p-3 ${st === "locked" ? "opacity-70" : ""}`}
                          aria-label={`Milestone ${(m?.index ?? 0) + 1}: ${c.title}. ${st === "done" ? "Completed" : st === "current" ? "Current" : "Locked"}`}>
                          <span className={`node !h-12 !w-12 !text-base ${nodeClass(st)}`} aria-hidden>{st === "done" ? "✓" : st === "locked" ? "🔒" : (m?.index ?? 0) + 1}</span>
                          <span className="min-w-0"><span className="block font-bold">{c.title}{st === "current" ? <span className="ml-2 pill text-action-base">You are here</span> : null}</span>
                            <span className="mt-1 block">{st === "locked"
                              ? <span className="text-meta text-ink-muted">Unlocks after “{m?.previous?.title}”</span>
                              : st === "done" && !c.evidence?.states?.length && c.placement_status === "known"
                                ? <span className="pill text-success bg-success-surface">✓ Known from level test</span>
                                : <Evidence e={c.evidence} />}</span></span>
                        </Link>
                      </li>
                    );
                  })}
                  {u.concepts.length > 0 && u.foundations.map((f: any) => (
                    <li key={f.id}><Link className="btn-link text-meta" href={`/subjects/${subjectId}/roadmap/concepts/${f.id}`}>Optional side quest: {f.title}</Link></li>
                  ))}
                </ol>
              </section>
            ))}
          </div>
          <aside aria-labelledby="insp-h" className="h-fit xl:sticky xl:top-28">
            {!conceptId ? (
              <div className="game-card space-y-3 p-5">
                <Companion message="Follow the road: each milestone lights up once you apply the previous one on your own. Diamond side quests are optional refreshers." />
                {data.suggestion && (
                  <div className="rounded-detail bg-help-surface p-3">
                    <p className="text-meta font-bold text-help">{data.suggestion.kind === "side_quest" ? "Suggested side quest" : "Suggested next level"}</p>
                    <p className="mt-1">{data.suggestion.reason}</p>
                    <Link className="btn-link" href={`/subjects/${subjectId}/roadmap/concepts/${data.suggestion.id}`}>Open it</Link>
                  </div>
                )}
                <div className="space-y-2 border-t border-border pt-3">
                  <Link className="btn-secondary w-full" href={`/subjects/${subjectId}/diagnostic`}>
                    Find where to start (Adaptive check)
                  </Link>
                  <Link className="btn-secondary w-full" href={`/subjects/${subjectId}/summary`}>
                    Course summary for my level
                  </Link>
                </div>
              </div>
            ) : (
              <div className="game-card p-5">
                {detail.loading && <Skeleton />}
                {detail.error && <ErrorBox message="This concept could not load." onRetry={detail.reload} />}
                {detail.data && (
                  <>
                    <div className="flex items-start justify-between gap-2">
                      <h2 id="insp-h" className="text-section">{detail.data.concept.title}</h2>
                      <Link className="btn-secondary !min-h-[44px] !px-3" href={`/subjects/${subjectId}/roadmap`} aria-label="Close inspector">✕</Link>
                    </div>
                    <p className="mt-2"><strong>Objective:</strong> {detail.data.concept.objective || "Not stated in the source."}</p>
                    {selected && (
                      <p className={`mt-3 rounded-detail p-3 text-meta font-bold ${selected.status === "locked" ? "bg-review-surface" : selected.status === "current" ? "bg-help-surface" : "bg-success-surface"}`}>
                        {selected.status === "done"
                          ? (selected.c.placement_status === "known" && !selectedAchievedByEvidence
                              ? `✓ Milestone ${selected.index + 1} completed (known from level test)`
                              : `✓ Milestone ${selected.index + 1} completed`)
                          : selected.status === "current" ? `📍 Milestone ${selected.index + 1} — you are here. Apply it once without help to unlock the next one.`
                          : `🔒 Milestone ${selected.index + 1} unlocks after “${selected.previous?.title}”.`}
                      </p>
                    )}
                    <div className="mt-3"><Evidence e={detail.data.evidence} /></div>
                    {detail.data.prerequisites.length > 0 && (
                      <div className="mt-4">
                        <p className="font-semibold">Prerequisites (optional)</p>
                        <ul className="mt-1 space-y-1">
                          {detail.data.prerequisites.map((p: any) => (
                            <li key={p.id} className="text-meta">{p.title}{" "}
                              <button className="btn-link" onClick={() => start(p.id)}>Learn this first</button></li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {detail.data.concept.citations.map((ci: any, i: number) => (
                      <p key={i} className="mt-3 text-meta">Source: <Link className="underline" href={`/subjects/${subjectId}/resources/${ci.source_id}?page=${ci.page}&return=${encodeURIComponent(`/subjects/${subjectId}/roadmap/concepts/${conceptId}`)}`}>{ci.filename}, page {ci.page}</Link></p>
                    ))}
                    {!detail.data.concept.citations.length && <p className="mt-3 text-meta"><span className="pill text-ink-muted">✦ AI-generated level — lesson grounded in open sources</span></p>}
                    <div className="mt-6 flex flex-col gap-2">
                      {locked && currentMs && (
                        <button className="btn-primary" onClick={() => start(currentMs.c.id)} disabled={busy}>Go to my current milestone</button>
                      )}
                      <button className={locked ? "btn-secondary" : "btn-primary"} onClick={() => start(conceptId)} disabled={busy || locked}>Learn this concept</button>
                      <button className="btn-secondary" onClick={() => start(conceptId, "practice")} disabled={busy || locked}>Practice</button>
                    </div>
                  </>
                )}
              </div>
            )}
          </aside>
        </div>
      )}
    </SubjectShell>
  );
}
