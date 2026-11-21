"use client";
// W02 Practice selection (basic): pick any level to practise; due reviews shown first. Full pool/filters = M3.
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { labelText } from "@/components/Roadmap";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, EvidencePill, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function Practice() {
  const { s } = useParams<{ s: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/roadmap`);
  const [busy, setBusy] = useState<string | null>(null);
  const start = async (cid: string) => {
    setBusy(cid);
    const r = await api(`/subjects/${s}/sessions`, { method: "POST", json: { concept_id: cid, kind: "practice" } });
    router.push(`/subjects/${s}/sessions/${r.session.id}/setup`);
  };
  const concepts = data ? data.units.flatMap((u: any) => u.concepts.map((c: any) => ({ ...c, unit: u.title }))) : [];
  const due = concepts.filter((c: any) => c.evidence.review_due_on);
  return (
    <SubjectShell subjectId={s} crumb="Practice">
      <div data-screen="W02" className="space-y-6">
        {!data && !error && <Skeleton />}
        {error && <ErrorBox message="Practice could not load." onRetry={reload} />}
        {due.length > 0 && (
          <section className="game-card p-5">
            <h2 className="text-section">Booked reviews</h2>
            <ul className="mt-2 space-y-1">{due.map((c: any) => <li key={c.id}>{c.title} — {new Date(c.evidence.review_due_on + "T00:00:00").toLocaleDateString()}</li>)}</ul>
          </section>
        )}
        <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {concepts.map((c: any) => (
            <li key={c.id} className="game-card flex flex-col gap-3 p-5">
              <p className="text-meta font-semibold text-ink-muted">{c.unit}</p>
              <h2 className="text-section !text-[1.2rem]">{c.title}</h2>
              <div className="flex flex-wrap gap-1">{c.evidence.states.length ? c.evidence.states.map((st: string) => <EvidencePill key={st} label={st} text={labelText(st)} />)
                : <span className="pill text-ink-muted">Not checked yet</span>}</div>
              <button className="btn-primary mt-auto" onClick={() => start(c.id)} disabled={busy !== null}>{busy === c.id ? "Preparing…" : "Practise"}</button>
            </li>
          ))}
        </ul>
      </div>
    </SubjectShell>
  );
}
