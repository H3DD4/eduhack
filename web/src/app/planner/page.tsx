"use client";
// G03 Planner — this run: persisted review dates only (manual blocks + auto-plan proposals are M4).
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function Planner() {
  const { data, error, reload } = useApi<any>("/reviews");
  return (
    <AppShell crumbs={[{ label: "Planner" }]}>
      <div data-screen="G03" className="max-w-prose space-y-4">
        <h1 className="text-page-compact lg:text-page">Planner</h1>
        <p className="text-ink-muted">Study blocks, exam dates and plan proposals arrive in M4. Booked reviews are saved now.</p>
        {!data && !error && <Skeleton />}
        {error && <ErrorBox message="Reviews could not load." onRetry={reload} />}
        {data && data.reviews.length === 0 && <p className="card">No reviews booked. Finish a session to book one.</p>}
        <ul className="space-y-2">
          {data?.reviews.map((r: any) => (
            <li key={r.id} className="card !p-4">
              <p className="font-semibold">Review on {new Date(r.due_on + "T00:00:00").toLocaleDateString()}</p>
              <p className="text-meta text-ink-muted">{r.basis}</p>
              <Link className="btn-link" href={`/subjects/${r.subject_id}/roadmap/concepts/${r.concept_id}`}>Open concept</Link>
            </li>
          ))}
        </ul>
      </div>
    </AppShell>
  );
}
