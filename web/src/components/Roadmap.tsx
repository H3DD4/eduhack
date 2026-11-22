"use client";
// W01 Roadmap + W06 Concept inspector — UC08/UC09. Game map: a winding trail of level nodes with prerequisite
// edges and optional foundation "side quests". Every node is a real link (keyboard/screen-reader order = teaching
// order); the SVG trail is decorative. No locks: suggestions never gate. A List view is always available.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { tutor } from "@/lib/tutor";
import { SubjectShell } from "./SubjectShell";
import { Companion, ErrorBox, EvidencePill, Skeleton } from "./ui";

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

function stars(e: any) {
  const s = new Set(e?.states || []);
  return [s.has("practised_with_support") || s.has("introduced"), s.has("explained"), s.has("applied_independently")];
}
function nodeClass(e: any) {
  if (e?.states?.includes("applied_independently")) return "node-applied";
  if (e?.states?.length) return "node-progress";
  return "node-new";
}

function GameMap({ unit, subjectId, conceptId, suggested, allFoundations }:
  { unit: any; subjectId: string; conceptId?: string; suggested?: string; allFoundations: any[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(720);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const amp = Math.min(w * 0.26, 220);
  const step = 175;
  const levels = unit.concepts.length ? unit.concepts : unit.foundations; // foundation-only units become their own trail
  const pts = levels.map((c: any, i: number) => ({ c, x: w / 2 + Math.sin(i * 1.15) * amp, y: 80 + i * step }));
  const byKey: Record<string, { x: number; y: number }> = {};
  pts.forEach((p: any) => (byKey[p.c.key] = p));
  const sideQuests: any[] = [];
  pts.forEach((p: any) => {
    if (!unit.concepts.length) return;
    allFoundations.filter((f) => p.c.prerequisites.includes(f.key)).forEach((f, k) => {
      if (sideQuests.some((q) => q.f.id === f.id)) return;
      const side = p.x > w / 2 ? -1 : 1;
      sideQuests.push({ f, x: Math.max(50, Math.min(w - 50, p.x + side * Math.min(170, w * 0.3))), y: p.y - 40 + k * 70, target: p });
    });
  });
  const height = Math.max(200, 80 + (levels.length - 1) * step + 130);
  const trail = pts.map((p: any, i: number) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const q = pts[i - 1];
    const my = (q.y + p.y) / 2;
    return `C ${q.x} ${my}, ${p.x} ${my}, ${p.x} ${p.y}`;
  }).join(" ");

  return (
    <div ref={box} className="map-bg relative mt-4 w-full overflow-hidden" style={{ height }}>
      <svg className="absolute inset-0" width={w} height={height} aria-hidden="true">
        <path d={trail} fill="none" stroke="var(--border)" strokeWidth="14" strokeLinecap="round" />
        <path d={trail} fill="none" stroke="var(--surface)" strokeWidth="4" strokeDasharray="2 14" strokeLinecap="round" />
        {pts.flatMap((p: any) => p.c.prerequisites.filter((k: string) => byKey[k] && byKey[k] !== pts[pts.indexOf(p) - 1]).map((k: string) => {
          const q = byKey[k];
          return <path key={`${p.c.id}-${k}`} d={`M ${q.x} ${q.y} Q ${(q.x + p.x) / 2 + 80} ${(q.y + p.y) / 2}, ${p.x} ${p.y}`} fill="none" stroke="var(--help)" strokeOpacity=".35" strokeWidth="2" strokeDasharray="6 6" />;
        }))}
        {sideQuests.map((q) => (
          <path key={q.f.id} d={`M ${q.x} ${q.y} L ${q.target.x} ${q.target.y}`} stroke="var(--discovery)" strokeWidth="3" strokeDasharray="4 6" />
        ))}
      </svg>
      <ol className="contents" aria-label={`Unit ${unit.unit_no} levels`}>
        {pts.map((p: any, i: number) => {
          const st = stars(p.c.evidence);
          const isCurrent = suggested === p.c.id;
          return (
            <li key={p.c.id} className="absolute flex w-[180px] -translate-x-1/2 -translate-y-[42px] flex-col items-center text-center" style={{ left: p.x, top: p.y }}>
              <Link href={`/subjects/${subjectId}/roadmap/concepts/${p.c.id}`}
                aria-label={`${p.c.key} ${p.c.title}. ${p.c.evidence.highest_text}${isCurrent ? ". Suggested next" : ""}`}
                aria-current={conceptId === p.c.id ? "true" : undefined}
                className={`node ${nodeClass(p.c.evidence)} ${isCurrent ? "node-current" : ""} ${conceptId === p.c.id ? "ring-4 ring-focus" : ""}`}>
                {p.c.evidence?.states?.includes("applied_independently") ? "★" : i + 1}
              </Link>
              <span className="mt-3 rounded-detail border-2 border-ink bg-surface px-2 text-meta leading-tight" aria-hidden>{p.c.title}</span>
              <span className="text-[0.95rem] tracking-widest text-discovery" aria-hidden>{st.map((on) => (on ? "★" : "☆")).join("")}</span>
            </li>
          );
        })}
      </ol>
      {sideQuests.map((q) => (
        <Link key={q.f.id} href={`/subjects/${subjectId}/roadmap/concepts/${q.f.id}`} aria-label={`Optional foundation: ${q.f.title}`}
          className="node node-foundation absolute -translate-x-1/2 -translate-y-1/2" style={{ left: q.x, top: q.y }} title={`Optional refresher: ${q.f.title}`}>
          {q.f.key}
        </Link>
      ))}
    </div>
  );
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

  const launchTutorTrack = async (valley: "revision" | "skills") => {
    setBusy(true);
    setErr(null);
    try {
      const t = await tutor.fromSubject(subjectId, { valley });
      router.push(`/tutor/${t.id}`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const suggested = data?.suggested_concept_id;
  const resume = data?.resume;
  const primary = conceptId ? null : resume ? (
    <Link className="btn-primary" href={`/subjects/${subjectId}/sessions/${resume.session_id}${resume.status === "draft" ? "/setup" : ""}`}>▶ Resume “{resume.concept_title}”</Link>
  ) : suggested ? (
    <button className="btn-primary" onClick={() => start(suggested)} disabled={busy}>Continue suggested concept</button>
  ) : null;
  const allFoundations = data ? data.units.flatMap((u: any) => u.foundations) : [];
  const counts = data?.counts;

  return (
    <SubjectShell subjectId={subjectId} action={primary} crumb={conceptId ? "Concept" : undefined}>
      {loading && !data && <div className="card"><Skeleton lines={5} label="Loading roadmap" /></div>}
      {error && <ErrorBox message="The roadmap could not load." onRetry={reload} />}
      {err && <ErrorBox message={err} />}
      {data && data.subject.status !== "ready" && (
        <div className="card"><p>Confirm this subject&apos;s roadmap to see the map.</p>
          <Link className="btn-primary mt-4" href={`/subjects/${subjectId}/setup`}>Review roadmap</Link></div>
      )}
      {data && data.subject.status === "ready" && (
        <div className="grid gap-6 xl:grid-cols-[1fr_340px]" data-screen={conceptId ? "W06" : "W01"}>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-4">
                <span className="ring" style={{ ["--p" as any]: counts?.concepts ? Math.round((100 * counts.applied) / counts.concepts) : 0 }}
                  aria-label={`${counts?.applied} of ${counts?.concepts} levels applied independently`}><span>{counts?.applied}/{counts?.concepts}</span></span>
                <div>
                  <p className="font-bold">{counts?.applied} of {counts?.concepts} levels applied on your own</p>
                  <p className="text-meta text-ink-muted">{counts?.started} started · ★ practised · ★★ explained · ★★★ applied without help</p>
                </div>
              </div>
              <div role="group" aria-label="Roadmap view" className="flex gap-1">
                <button className={view === "map" ? "chip !border-action" : "chip"} aria-pressed={view === "map"} onClick={() => choose("map")}>🗺 Map</button>
                <button className={view === "list" ? "chip !border-action" : "chip"} aria-pressed={view === "list"} onClick={() => choose("list")}>☰ List</button>
              </div>
            </div>
            {data.units.map((u: any) => (
              <section key={u.unit_no} aria-labelledby={`u-${u.unit_no}`} className="mt-8">
                <div className="unit-banner flex items-center justify-between gap-3 px-5 py-4">
                  <h2 id={`u-${u.unit_no}`} className="text-section !text-[1.25rem]">Unit {u.unit_no}: {u.title}</h2>
                  <span className="text-meta font-bold">{u.concepts.filter((c: any) => c.evidence.states.includes("applied_independently")).length}/{u.concepts.length} ★</span>
                </div>
                {view === "map" ? (
                  <GameMap unit={u} subjectId={subjectId} conceptId={conceptId} suggested={suggested} allFoundations={allFoundations} />
                ) : (
                  <ol className="relative mt-4 space-y-4 border-l-4 border-border pl-6" aria-label={`Unit ${u.unit_no} path`}>
                    {u.concepts.map((c: any) => (
                      <li key={c.id}>
                        <Link href={`/subjects/${subjectId}/roadmap/concepts/${c.id}`} className="game-card flex min-h-[64px] items-center gap-4 p-3">
                          <span className={`node !h-12 !w-12 !text-base ${nodeClass(c.evidence)}`} aria-hidden>{c.key}</span>
                          <span className="min-w-0"><span className="block font-bold">{c.key} {c.title}{suggested === c.id ? <span className="ml-2 pill text-action-base">Suggested</span> : null}</span>
                            <span className="mt-1 block"><Evidence e={c.evidence} /></span></span>
                        </Link>
                      </li>
                    ))}
                    {u.foundations.map((f: any) => (
                      <li key={f.id}><Link className="btn-link text-meta" href={`/subjects/${subjectId}/roadmap/concepts/${f.id}`}>Optional foundation: {f.title}</Link></li>
                    ))}
                  </ol>
                )}
              </section>
            ))}
          </div>
          <aside aria-labelledby="insp-h" className="h-fit xl:sticky xl:top-20">
            {!conceptId ? (
              <div className="game-card space-y-3 p-5">
                <Companion message="Tap any level to see what it is about. Nothing is locked — side quests (mint) are optional refreshers." />
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
                  <div className="rounded-detail border-2 border-ink bg-soft p-3 space-y-2">
                    <p className="text-meta font-bold">Agentic Tutor Studio</p>
                    <p className="text-meta text-ink-muted">
                      Turn this subject&apos;s documents and mastery profile into a course-fingerprinted revision pack or progressive tutorial.
                    </p>
                    <div className="grid gap-2">
                      <button type="button" className="btn-primary !min-h-[38px] text-meta" disabled={busy} onClick={() => launchTutorTrack("revision")}>
                        Valley 1 · Exam Revision Pack
                      </button>
                      <button type="button" className="btn-secondary !min-h-[38px] text-meta" disabled={busy} onClick={() => launchTutorTrack("skills")}>
                        Valley 2 · Skill Tutorial
                      </button>
                    </div>
                  </div>
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
                      <button className="btn-primary" onClick={() => start(conceptId)} disabled={busy}>Learn this concept</button>
                      <button className="btn-secondary" onClick={() => start(conceptId, "practice")} disabled={busy}>Practice</button>
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
