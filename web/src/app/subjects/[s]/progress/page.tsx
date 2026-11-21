"use client";
// W05 Subject Progress (minimal) — UC34. Receipts per concept; no mastery percentage; loading is not zero.
import Link from "next/link";
import { useParams } from "next/navigation";
import { labelText } from "@/components/Roadmap";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, EvidencePill, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function SubjectProgress() {
  const { s } = useParams<{ s: string }>();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/evidence`);
  return (
    <SubjectShell subjectId={s} crumb="Progress">
      <div data-screen="W05" className="space-y-4">
        {!data && !error && <Skeleton lines={5} label="Loading evidence" />}
        {error && <ErrorBox message="Evidence could not load." onRetry={reload} />}
        {data && data.evidence.length === 0 && <p className="card">No evidence yet. Choose a concept in the Roadmap to start.</p>}
        {data && data.evidence.length > 0 && (
          <ul className="space-y-2">
            {data.evidence.map((e: any) => (
              <li key={e.id} className="card !p-4 flex flex-wrap items-center justify-between gap-2">
                <span className="space-y-1">
                  <span className="block font-semibold">{e.concept_title || (e.stage === "diagnostic" ? "Baseline" : "Concept")} · {e.stage}</span>
                  <span className="flex flex-wrap items-center gap-2">
                    <EvidencePill label={e.label} text={e.label_text || labelText(e.label)} />
                    <span className="text-meta text-ink-muted">{e.outcome.replace("_", " ")} · {new Date(e.created_at).toLocaleString()}</span>
                    {e.assistance?.help_level ? <span className="pill text-help">help step {e.assistance.help_level}</span> : null}
                    {e.assistance?.conversion ? <span className="pill text-help">switched to guided</span> : null}
                  </span>
                </span>
                <Link className="btn-link" href={`/subjects/${s}/progress/evidence/${e.id}`}>Open receipt</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SubjectShell>
  );
}
