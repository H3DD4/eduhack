"use client";
// Tutor home: the two valleys and the student's tracks.
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { LEVEL_LABEL, type Track } from "@/lib/tutor";

const STATUS: Record<string, string> = {
  created: "Ready to prepare (docs optional)", ingesting: "Reading your course…", awaiting_level: "Level check", probing: "Level check",
  levelled: "Ready to build", building: "Building…", ready: "Ready", failed: "Needs attention",
};

export default function TutorHome() {
  const tracks = useApi<{ tracks: Track[] }>("/tutor/tracks");
  return (
    <AppShell crumbs={[{ label: "Tutor" }]}>
      <div className="space-y-10" data-screen="TUTOR-HOME">
        <section className="hero p-7 md:p-10">
          <div className="relative z-10 max-w-2xl space-y-3">
            <span className="badge">Tutor</span>
            <h1 className="text-page md:text-hero">Your course, <span className="hl-dark">turned into practice</span></h1>
            <p className="text-problem">Upload your teacher&apos;s documents. The tutor checks your level, then builds material that looks like your own course.</p>
          </div>
        </section>

        <div className="grid gap-5 md:grid-cols-2">
          <Link href="/tutor/new?valley=revision" className="game-card group block space-y-3 p-6 transition hover:-translate-y-1">
            <span className="badge">Valley 1</span>
            <h2 className="text-section">Revise for a test or exam</h2>
            <p>Résumés, fiches, quizzes, QCM, exercises and a timed mock exam shaped like your past exams, planned up to the exam date.</p>
            <span className="btn-primary inline-flex">Start revising</span>
          </Link>
          <Link href="/tutor/new?valley=skills" className="game-card group block space-y-3 p-6 transition hover:-translate-y-1">
            <span className="badge">Valley 2</span>
            <h2 className="text-section">Learn a new skill</h2>
            <p>A step-by-step tutorial from your documents: short pages, examples, “try it yourself”, a quiz per chapter and a final project.</p>
            <span className="btn-primary inline-flex">Start learning</span>
          </Link>
        </div>

        <section className="space-y-3">
          <h2 className="text-section">Your tracks</h2>
          {tracks.loading && !tracks.data && <Skeleton lines={3} />}
          {tracks.error && <ErrorBox message={tracks.error.message} onRetry={tracks.reload} />}
          {tracks.data?.tracks.length === 0 && <p className="text-ink-muted">No track yet. Pick a valley above.</p>}
          <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {tracks.data?.tracks.map((t) => (
              <li key={t.id}>
                <Link href={`/tutor/${t.id}`} className="card block space-y-2 p-5 transition hover:-translate-y-1 hover:shadow-hard">
                  <div className="flex items-center justify-between gap-2">
                    <span className="pill">{t.valley === "revision" ? "Exam revision" : "New skill"}</span>
                    <span className="text-meta">{STATUS[t.status] || t.status}</span>
                  </div>
                  <h3 className="text-problem font-semibold">{t.title}</h3>
                  <p className="text-meta text-ink-muted">
                    {t.measured_level ? `${LEVEL_LABEL[t.measured_level]} · ` : ""}{t.exam_date ? `Exam ${new Date(t.exam_date).toLocaleDateString()}` : t.subject}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </AppShell>
  );
}
