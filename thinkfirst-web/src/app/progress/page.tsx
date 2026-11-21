"use client";
// G04 Overall Progress (basic) — per-subject counts of evidence states; no percentages, no traits/styles.
import Link from "next/link";
import { labelText } from "@/components/Roadmap";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, EvidencePill, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function Progress() {
  const { data, error, reload } = useApi<any>("/progress");
  return (
    <AppShell crumbs={[{ label: "Progress" }]}>
      <div data-screen="G04" className="space-y-4">
        <h1 className="text-page-compact lg:text-page">Progress</h1>
        {!data && !error && <Skeleton />}
        {error && <ErrorBox message="Progress could not load." onRetry={reload} />}
        {data?.subjects.length === 0 && <p className="card">No evidence yet. Choose a subject to start.</p>}
        <ul className="grid gap-4 md:grid-cols-2">
          {data?.subjects.map((x: any) => (
            <li key={x.subject.id} className="card">
              <h2 className="text-section">{x.subject.name}</h2>
              <p className="mt-1 text-meta text-ink-muted">{x.concepts_with_evidence} concept(s) with evidence</p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {Object.entries(x.state_counts).map(([k, n]: any) => <li key={k}><EvidencePill label={k} text={`${labelText(k)}: ${n}`} /></li>)}
              </ul>
              <Link className="btn-link mt-3" href={`/subjects/${x.subject.id}/progress`}>Open subject evidence</Link>
            </li>
          ))}
        </ul>
        <p className="text-meta text-ink-muted">{data?.profile_note}</p>
      </div>
    </AppShell>
  );
}
