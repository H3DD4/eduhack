"use client";
// G01 Today — hero with one next action (resume first), learn-anything launcher, courses with progress.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { CourseCards } from "@/components/CourseCards";
import { TopicLauncher } from "@/components/TopicLauncher";
import { ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function Compass({ size = 96 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="18" fill="rgba(255,255,255,.08)" stroke="rgba(255,255,255,.35)" />
      <polygon points="20,3 26,20 20,37 14,20" fill="#00A08D" stroke="#fff" strokeWidth="1" />
      <polygon points="20,3 26,20 20,20" fill="#F1BB58" />
      <polygon points="3,20 20,14 37,20 20,26" fill="none" stroke="#fff" strokeWidth="1" />
      <circle cx="20" cy="20" r="2.5" fill="#fff" />
    </svg>
  );
}

export default function Today() {
  const router = useRouter();
  const { me } = useMe();
  const today = useApi<any>("/today");
  const subjects = useApi<any>("/subjects");
  const [busy, setBusy] = useState(false);
  const na = today.data?.next_action;

  const startConcept = async () => {
    setBusy(true);
    const r = await api(`/subjects/${na.subject_id}/sessions`, { method: "POST", json: { concept_id: na.concept_id, kind: "learn" } });
    router.push(`/subjects/${na.subject_id}/sessions/${r.session.id}/setup`);
  };

  return (
    <AppShell crumbs={[{ label: "Today" }]}>
      <div className="space-y-8" data-screen="G01">
        <section className="hero p-6 md:p-10" aria-labelledby="hero-h">
          <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center">
            <div className="flex-1 space-y-3">
              <p className="muted font-semibold">Hi {me?.display_name || "explorer"} 👋</p>
              <h1 id="hero-h" className="text-page-compact md:text-page">Today</h1>
              {today.loading && !today.data && <p className="muted">Loading your next step…</p>}
              {na?.kind === "resume" && (
                <>
                  <p className="text-problem">Continue where you left off: <strong>{na.concept_title}</strong></p>
                  <p className="muted text-meta">{na.reason}</p>
                  <Link href={`/subjects/${na.subject_id}/sessions/${na.session_id}`} className="btn-primary">▶ Resume</Link>
                </>
              )}
              {na?.kind === "start" && (
                <>
                  <p className="text-problem">Next level: <strong>{na.concept_title}</strong></p>
                  <p className="muted text-meta">{na.reason}</p>
                  <div className="flex flex-wrap gap-3">
                    <button className="btn-primary" onClick={startConcept} disabled={busy}>Start</button>
                    <Link className="btn-secondary !border-white/60 !bg-transparent !text-white" href={`/subjects/${na.subject_id}/roadmap`}>Change action</Link>
                  </div>
                </>
              )}
              {na?.kind === "setup" && (
                <>
                  <p className="text-problem">Your roadmap is ready to review.</p>
                  <Link href={`/subjects/${na.subject_id}/setup`} className="btn-primary">Review roadmap</Link>
                </>
              )}
              {na?.kind === "add_subject" && (
                <>
                  <p className="text-problem">What do you want to learn today?</p>
                  <Link href="/subjects/new" className="btn-primary">Add subject</Link>
                </>
              )}
            </div>
            <div className="hidden shrink-0 lg:block"><Compass size={140} /></div>
          </div>
        </section>
        {today.error && <ErrorBox message="Today could not load." onRetry={today.reload} />}

        <section aria-labelledby="learn-h" className="game-card p-6">
          <h2 id="learn-h" className="text-section">Learn anything</h2>
          <p className="mt-1 text-ink-muted">Type a topic — ThinkFirst builds a roadmap, lessons, practice and checks. No files needed.</p>
          <div className="mt-4"><TopicLauncher /></div>
        </section>

        <section aria-labelledby="courses-h">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="courses-h" className="text-section">Your courses</h2>
            <Link href="/subjects/new" className="btn-link">+ Upload course files</Link>
          </div>
          {subjects.loading && !subjects.data && <Skeleton />}
          {subjects.data?.subjects?.length === 0 && <p className="text-ink-muted">No courses yet — start one above.</p>}
          {subjects.data && <CourseCards subjects={subjects.data.subjects} />}
        </section>

        {today.data?.reviews?.length > 0 && (
          <section aria-labelledby="rev-h" className="game-card p-6">
            <h2 id="rev-h" className="text-section">Booked reviews</h2>
            <ul className="mt-3 space-y-2">
              {today.data.reviews.map((r: any) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span>Review on <strong>{new Date(r.due_on + "T00:00:00").toLocaleDateString()}</strong></span>
                  <span className="text-meta text-ink-muted">Delayed review sessions arrive in M3</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </AppShell>
  );
}
