"use client";
// W01 Roadmap + W06 Concept inspector — UC08/UC09. Semantic, accessible vertical path; every node inspectable
// and startable (suggestions are never hard gates; no lock imagery for unseen concepts).
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { SubjectShell } from "./SubjectShell";
import { Companion, ErrorBox, EvidencePill, Skeleton } from "./ui";

function NodeGlyph({ highest }: { highest: string | null }) {
  const shape = highest === "applied_independently" || highest === "recalled_later" ? "●" : highest ? "◐" : "○";
  return <span aria-hidden className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 border-stroke bg-surface text-section">{shape}</span>;
}

function Evidence({ e }: { e: any }) {
  if (!e || !e.states?.length) return <span className="pill text-ink-muted">Not checked yet</span>;
  return (
    <span className="flex flex-wrap items-center gap-1">
      {e.states.map((st: string) => <EvidencePill key={st} label={st} text={labelText(st)} />)}
      <span className="text-meta text-ink-muted">based on {e.attempts} attempt{e.attempts === 1 ? "" : "s"}</span>
      {e.review_due_on && <span className="pill text-ink">Review {new Date(e.review_due_on + "T00:00:00").toLocaleDateString()}</span>}
      {e.mixed && <span className="pill text-review">Mixed evidence</span>}
    </span>
  );
}
export function labelText(st: string) {
  return ({ introduced: "Introduced", practised_with_support: "Practised with support", explained: "Explained back",
    applied_independently: "Applied independently (no in-app help)", recalled_later: "Recalled later",
    insufficient_evidence: "Insufficient evidence" } as Record<string, string>)[st] || st;
}

export function RoadmapView({ subjectId, conceptId }: { subjectId: string; conceptId?: string }) {
  const router = useRouter();
  const { data, error, loading, reload } = useApi<any>(`/subjects/${subjectId}/roadmap`);
  const detail = useApi<any>(conceptId ? `/subjects/${subjectId}/concepts/${conceptId}` : null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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

  const suggested = data?.suggested_concept_id;
  const primary = conceptId ? null : suggested ? (
    <button className="btn-primary" onClick={() => start(suggested)} disabled={busy}>Continue suggested concept</button>
  ) : null;

  return (
    <SubjectShell subjectId={subjectId} action={primary} crumb={conceptId ? "Concept" : undefined}>
      {loading && !data && <div className="card"><Skeleton lines={5} label="Loading roadmap" /></div>}
      {error && <ErrorBox message="The roadmap could not load." onRetry={reload} />}
      {err && <ErrorBox message={err} />}
      {data && data.subject.status !== "ready" && (
        <div className="card"><p>Confirm this subject&apos;s scope to see the roadmap.</p>
          <Link className="btn-primary mt-4" href={`/subjects/${subjectId}/setup`}>Review scope</Link></div>
      )}
      {data && data.subject.status === "ready" && (
        <div className="grid gap-6 xl:grid-cols-[1fr_320px]" data-screen={conceptId ? "W06" : "W01"}>
          <div>
            <Companion message="Pick any concept. Suggestions are just suggestions." />
            <p className="mt-4 text-meta text-ink-muted">Legend: ○ not checked yet · ◐ some evidence · ● applied independently. Each node also states its evidence in words.</p>
            {data.units.map((u: any) => (
              <section key={u.unit_no} aria-labelledby={`u-${u.unit_no}`} className="mt-8">
                <h2 id={`u-${u.unit_no}`} className="text-section">Unit {u.unit_no}: {u.title}</h2>
                <ol className="relative mt-4 space-y-6 border-l-4 border-border pl-6" aria-label={`Unit ${u.unit_no} path`}>
                  {u.concepts.map((c: any) => {
                    const foundations = u.foundations.concat(...data.units.map((x: any) => x.foundations))
                      .filter((f: any, i: number, arr: any[]) => c.prerequisites.includes(f.key) && arr.findIndex((y) => y.id === f.id) === i);
                    return (
                      <li key={c.id} className="relative">
                        <Link href={`/subjects/${subjectId}/roadmap/concepts/${c.id}`} aria-current={conceptId === c.id ? "true" : undefined}
                          className={`-ml-[46px] flex min-h-[64px] items-center gap-4 rounded-card p-1 pr-3 hover:bg-surface ${conceptId === c.id ? "bg-surface ring-2 ring-action" : ""}`}>
                          <NodeGlyph highest={c.evidence.highest} />
                          <span className="min-w-0">
                            <span className="block font-bold">{c.key} {c.title}{suggested === c.id ? <span className="ml-2 pill text-action-base">Suggested</span> : null}</span>
                            <span className="mt-1 block"><Evidence e={c.evidence} /></span>
                          </span>
                        </Link>
                        {foundations.length > 0 && (
                          <ul className="ml-12 mt-2 space-y-1" aria-label={`Optional foundations for ${c.title}`}>
                            {foundations.map((f: any) => (
                              <li key={f.id}>
                                <Link className="btn-link text-meta" href={`/subjects/${subjectId}/roadmap/concepts/${f.id}`}>Optional foundation: {f.title}</Link>
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}
          </div>
          {conceptId && (
            <aside aria-labelledby="insp-h" className="card h-fit xl:sticky xl:top-20">
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
                          <li key={p.id} className="text-meta">{p.title} — {p.reason}{" "}
                            <button className="btn-link" onClick={() => start(p.id)}>Learn this foundation first</button></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {detail.data.concept.citations.map((ci: any, i: number) => (
                    <p key={i} className="mt-3 text-meta">Source: <Link className="underline" href={`/subjects/${subjectId}/resources/${ci.source_id}?page=${ci.page}&return=${encodeURIComponent(`/subjects/${subjectId}/roadmap/concepts/${conceptId}`)}`}>{ci.filename}, page {ci.page}</Link></p>
                  ))}
                  {!detail.data.concept.citations.length && <p className="mt-3 text-meta"><span className="pill text-ink-muted">✦ AI-generated scope — no course citation</span></p>}
                  <div className="mt-6 flex flex-col gap-2">
                    <button className="btn-primary" onClick={() => start(conceptId)} disabled={busy}>Learn this concept</button>
                    <button className="btn-secondary" onClick={() => start(conceptId, "practice")} disabled={busy}>Practice</button>
                  </div>
                </>
              )}
            </aside>
          )}
        </div>
      )}
    </SubjectShell>
  );
}
