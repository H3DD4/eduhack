"use client";
// G02 Subjects — course cards with progress and Resume; learn-anything launcher.
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CourseCards } from "@/components/CourseCards";
import { TopicLauncher } from "@/components/TopicLauncher";
import { ErrorBox, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function Subjects() {
  const { data, error, loading, reload } = useApi<any>("/subjects");
  return (
    <AppShell crumbs={[{ label: "Subjects" }]}>
      <div data-screen="G02" className="space-y-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-page-compact lg:text-page">Subjects</h1>
          <Link href="/subjects/new" className="btn-primary">Add subject</Link>
        </div>
        <section className="hero p-6 md:p-8" aria-labelledby="la-h">
          <div className="relative z-10">
            <h2 id="la-h" className="text-section">Start a new adventure</h2>
            <p className="muted mt-1">Type any topic. Your roadmap, lessons and checks are built for you.</p>
            <div className="mt-4"><TopicLauncher dark /></div>
          </div>
        </section>
        {loading && !data && <Skeleton />}
        {error && <ErrorBox message="Subjects could not load." onRetry={reload} />}
        {data && data.subjects.length > 0 && (
          <section aria-labelledby="c-h">
            <h2 id="c-h" className="mb-3 text-section">Your courses</h2>
            <CourseCards subjects={data.subjects} />
          </section>
        )}
      </div>
    </AppShell>
  );
}
