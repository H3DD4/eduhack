"use client";
// G01 Today — one obvious next action with its reason (UC02, UC10). No invented urgency.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Companion, ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function Today() {
  const router = useRouter();
  const { data, error, loading, reload } = useApi<any>("/today");
  const [busy, setBusy] = useState(false);
  const na = data?.next_action;

  const startConcept = async () => {
    setBusy(true);
    const r = await api(`/subjects/${na.subject_id}/sessions`, { method: "POST", json: { concept_id: na.concept_id, kind: "learn" } });
    router.push(`/subjects/${na.subject_id}/sessions/${r.session.id}/setup`);
  };

  return (
    <AppShell crumbs={[{ label: "Today" }]}>
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]" data-screen="G01">
        <section aria-labelledby="next-h" className="space-y-6">
          <h1 id="next-h" className="text-page-compact lg:text-page">Today</h1>
          {loading && !data && <div className="card"><Skeleton /></div>}
          {error && <ErrorBox message="Today could not load." onRetry={reload}><Link className="btn-secondary" href="/subjects">Open Subjects</Link></ErrorBox>}
          {na && (
            <div className="card">
              <p className="text-meta font-semibold text-ink-muted">Next action</p>
              {na.kind === "add_subject" && (
                <>
                  <h2 className="mt-1 text-section">Start with a course</h2>
                  <p className="mt-2">{na.reason}</p>
                  <Link href="/subjects/new" className="btn-primary mt-6">Add subject</Link>
                </>
              )}
              {na.kind === "resume" && (
                <>
                  <h2 className="mt-1 text-section">Resume “{na.concept_title}”</h2>
                  <p className="mt-2">{na.reason}</p>
                  <Link href={`/subjects/${na.subject_id}/sessions/${na.session_id}`} className="btn-primary mt-6">Resume</Link>
                </>
              )}
              {na.kind === "start" && (
                <>
                  <h2 className="mt-1 text-section">{na.concept_title}</h2>
                  <p className="mt-2">{na.reason}</p>
                  <div className="mt-6 flex flex-wrap gap-3">
                    <button className="btn-primary" onClick={startConcept} disabled={busy}>Start</button>
                    <Link className="btn-secondary" href={`/subjects/${na.subject_id}/roadmap`}>Change action</Link>
                  </div>
                </>
              )}
              {na.kind === "setup" && (
                <>
                  <h2 className="mt-1 text-section">Confirm your course scope</h2>
                  <p className="mt-2">{na.reason}</p>
                  <Link href={`/subjects/${na.subject_id}/setup`} className="btn-primary mt-6">Review scope</Link>
                </>
              )}
            </div>
          )}
          {data && (
            <section aria-labelledby="rev-h" className="card">
              <h2 id="rev-h" className="text-section">Booked reviews</h2>
              {data.reviews.length === 0 ? <p className="mt-2 text-ink-muted">No reviews booked yet.</p> : (
                <ul className="mt-3 space-y-2">
                  {data.reviews.map((r: any) => (
                    <li key={r.id} className="flex flex-wrap items-center justify-between gap-2">
                      <span>Review on <strong>{new Date(r.due_on + "T00:00:00").toLocaleDateString()}</strong></span>
                      <span className="text-meta text-ink-muted">Delayed review sessions arrive in M3</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          {data?.subjects?.length > 0 && (
            <section aria-labelledby="sub-h">
              <h2 id="sub-h" className="text-section">Your subjects</h2>
              <ul className="mt-3 flex flex-wrap gap-2">
                {data.subjects.map((s: any) => (
                  <li key={s.id}><Link className="btn-secondary" href={`/subjects/${s.id}/${s.status === "ready" ? "roadmap" : "setup"}`}>{s.name}</Link></li>
                ))}
              </ul>
            </section>
          )}
        </section>
        <aside className="space-y-4">
          <Companion message="One step at a time. Help is always available and never costs you anything." />
          <div className="card">
            <p className="font-semibold">Nearest exam</p>
            <p className="mt-1 text-meta text-ink-muted">No exam date added. Exams and the planner arrive in later milestones.</p>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
