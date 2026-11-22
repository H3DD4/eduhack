"use client";
// G01 Today — one adaptive hero with exactly one primary action, chosen by the student's state
// (resume > start next concept > review roadmap > add subject), then the learn-anything launcher and courses.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { CourseCards } from "@/components/CourseCards";
import { Mark } from "@/components/Logo";
import { TopicLauncher } from "@/components/TopicLauncher";
import { ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function Today() {
  const router = useRouter();
  const { me } = useMe();
  const today = useApi<any>("/today");
  const subjects = useApi<any>("/subjects");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const na = today.data?.next_action;

  const startConcept = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api(`/subjects/${na.subject_id}/sessions`, { method: "POST", json: { concept_id: na.concept_id, kind: "learn" } });
      router.push(`/subjects/${na.subject_id}/sessions/${r.session.id}/setup`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const tag = na?.kind === "resume" ? "Resume" : na?.kind === "start" ? "Next concept" : na?.kind === "setup" ? "Roadmap ready" : "Welcome";

  return (
    <AppShell crumbs={[{ label: "Today" }]}>
      <div className="space-y-10" data-screen="G01">
        <div className="flex flex-col gap-6 lg:flex-row">
          <section className={`hero flex-1 p-7 md:p-10 ${na?.kind === "setup" ? "hero-dark" : ""}`} aria-labelledby="hero-h" aria-busy={today.loading && !today.data}>
            <div className="relative z-10 max-w-2xl space-y-4">
              <p className="muted">{greeting()}, {me?.display_name || "explorer"}</p>
              <span className="badge">{tag}</span>
              {today.loading && !today.data && <h1 id="hero-h" className="text-page">Finding your next step…</h1>}
              {na?.kind === "resume" && (
                <>
                  <h1 id="hero-h" className="text-page md:text-hero">Pick up <span className="hl-dark">{na.concept_title}</span> where you left off</h1>
                  <p className="muted text-problem">{na.reason}</p>
                  <Link href={`/subjects/${na.subject_id}/sessions/${na.session_id}`} className="btn-primary">Resume session →</Link>
                </>
              )}
              {na?.kind === "start" && (
                <>
                  <h1 id="hero-h" className="text-page md:text-hero">Ready for <span className="hl-dark">{na.concept_title}</span>?</h1>
                  <p className="muted text-problem">{na.reason}</p>
                  <div className="flex flex-wrap gap-3">
                    <button className="btn-primary" onClick={startConcept} disabled={busy} aria-busy={busy}>{busy ? "Preparing…" : "Start session →"}</button>
                    <Link className="btn-secondary" href={`/subjects/${na.subject_id}/roadmap`}>Choose something else</Link>
                  </div>
                </>
              )}
              {na?.kind === "setup" && (
                <>
                  <h1 id="hero-h" className="text-page md:text-hero">Your roadmap is <span className="hl">ready</span></h1>
                  <p className="muted text-problem">Check the concepts we found, then start.</p>
                  <Link href={`/subjects/${na.subject_id}/setup`} className="btn-primary !border-white">Review roadmap →</Link>
                </>
              )}
              {na?.kind === "add_subject" && (
                <>
                  <h1 id="hero-h" className="text-page md:text-hero">What do you want to <span className="hl-dark">learn</span> first?</h1>
                  <p className="muted text-problem">Upload a course or type a topic. Your roadmap is ready in about a minute.</p>
                  <Link href="/subjects/new" className="btn-primary">Add a subject →</Link>
                </>
              )}
              {err && <ErrorBox message={err} />}
            </div>
          </section>
          <aside className="flex flex-col gap-4 lg:w-[320px]" aria-label="Coach">
            <div className="card space-y-3">
              <div className="flex items-start gap-3">
                <Mark size={44} className="shrink-0" />
                <p>{na?.kind === "resume" ? "Short and steady works. Ten minutes still counts." : na?.kind === "start" ? "Try first. Help comes one step at a time if you need it." : "Start with one subject. You can add more later."}</p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
                <SpeakButton
                  text={`${greeting()}, ${me?.display_name || "explorer"}. ${na?.reason || "Start with one subject. You can add more later."}`}
                  title="Today's coach"
                  hint={na?.concept_title || "algebra"}
                  subjectId={na?.subject_id}
                  label="Speak coach"
                />
                <Link href="/teachers" className="btn-link text-meta">Meet 3D Teachers →</Link>
              </div>
            </div>
            {today.data?.reviews?.length > 0 && (
              <div className="card">
                <p className="text-meta text-ink-muted">Booked reviews</p>
                <p className="text-section">{today.data.reviews.length}</p>
                <Link className="btn-link" href="/planner">See dates</Link>
              </div>
            )}
          </aside>
        </div>
        {today.error && <ErrorBox message="Today could not load." onRetry={today.reload} />}

        <section aria-labelledby="learn-h" className="game-card p-6 md:p-8">
          <h2 id="learn-h" className="text-section">Learn <span className="hl">anything</span></h2>
          <p className="mt-1 text-ink-muted">Type a topic. ThinkFirst builds a roadmap, lessons, practice and checks. No files needed.</p>
          <div className="mt-5"><TopicLauncher /></div>
        </section>

        <section aria-labelledby="courses-h">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 id="courses-h" className="text-section">Your subjects</h2>
            <Link href="/subjects/new" className="btn-secondary">+ Start learning something</Link>
          </div>
          {subjects.loading && !subjects.data && <Skeleton />}
          {subjects.data?.subjects?.length === 0 && <p className="text-ink-muted">No subjects yet. Start one above.</p>}
          {subjects.data && <CourseCards subjects={subjects.data.subjects} />}
        </section>

        {today.data?.reviews?.length > 0 && (
          <section aria-labelledby="rev-h" className="game-card p-6">
            <h2 id="rev-h" className="text-section">Booked reviews</h2>
            <ul className="mt-3 space-y-2">
              {today.data.reviews.map((r: any) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-control bg-soft px-4 py-3">
                  <span>Review on {new Date(r.due_on + "T00:00:00").toLocaleDateString()}</span>
                  <Link className="btn-link" href="/planner">Open planner</Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </AppShell>
  );
}
