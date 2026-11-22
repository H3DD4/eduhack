"use client";
import Link from "next/link";

export function CourseCards({ subjects }: { subjects: any[] }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {subjects.map((s) => {
        const pct = s.concept_count ? Math.round((100 * s.applied_count) / s.concept_count) : 0;
        const open = `/subjects/${s.id}/${s.status === "ready" ? "start" : "setup"}`; // the subject's page: path, roadmap, level, summary
        const resume = s.resume ? `/subjects/${s.id}/sessions/${s.resume.session_id}${s.resume.status === "draft" ? "/setup" : ""}` : null;
        return (
          <li key={s.id} className="game-card flex h-full flex-col gap-3 p-5">
            <Link href={open} className="flex items-start justify-between gap-3 hover:underline">
              <h3 className="text-section !text-[1.25rem]">{s.name}</h3>
              {s.status === "ready" && (
                <span className="ring shrink-0" style={{ ["--p" as any]: pct }} aria-label={`${s.applied_count} of ${s.concept_count} concepts applied independently`}>
                  <span>{s.applied_count}/{s.concept_count}</span>
                </span>
              )}
            </Link>
            <p className="text-meta text-ink-muted">
              {s.status === "ready" ? `${s.applied_count} of ${s.concept_count} concepts applied on your own` : s.status === "processing" ? "Building your roadmap…" : "Roadmap waiting for you"}
            </p>
            <div className="mt-auto flex flex-wrap gap-2">
              <Link href={open} className="btn-secondary !min-h-[40px]">{s.status === "ready" ? "Open subject" : "Review roadmap"}</Link>
              {resume && <Link href={resume} className="btn-primary !min-h-[40px]">▶ Resume “{s.resume.concept_title}”</Link>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
