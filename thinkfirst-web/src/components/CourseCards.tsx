"use client";
import Link from "next/link";

export function CourseCards({ subjects }: { subjects: any[] }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {subjects.map((s) => {
        const pct = s.concept_count ? Math.round((100 * s.applied_count) / s.concept_count) : 0;
        const href = s.resume ? `/subjects/${s.id}/sessions/${s.resume.session_id}${s.resume.status === "draft" ? "/setup" : ""}`
          : `/subjects/${s.id}/${s.status === "ready" ? "roadmap" : "setup"}`;
        return (
          <li key={s.id}>
            <Link href={href} className="game-card flex h-full flex-col gap-3 p-5">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-section !text-[1.25rem]">{s.name}</h3>
                {s.status === "ready" && (
                  <span className="ring shrink-0" style={{ ["--p" as any]: pct }} aria-label={`${s.applied_count} of ${s.concept_count} concepts applied independently`}>
                    <span>{s.applied_count}/{s.concept_count}</span>
                  </span>
                )}
              </div>
              <p className="text-meta text-ink-muted">
                {s.status === "ready" ? `${s.applied_count} of ${s.concept_count} concepts applied on your own` : s.status === "processing" ? "Building your roadmap…" : "Roadmap waiting for you"}
              </p>
              <span className={`mt-auto inline-flex font-bold ${s.resume ? "text-action-base" : "text-ink"}`}>
                {s.resume ? `▶ Resume “${s.resume.concept_title}”` : s.status === "ready" ? "Open map →" : "Review roadmap →"}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
