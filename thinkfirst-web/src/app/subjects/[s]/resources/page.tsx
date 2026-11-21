"use client";
// W04 Resources — UC32. All private; removal previews impact and creates citation tombstones (history kept).
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { SubjectShell } from "@/components/SubjectShell";
import { Dialog, ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function Resources() {
  const { s } = useParams<{ s: string }>();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/resources`);
  const [impact, setImpact] = useState<any>(null);
  return (
    <SubjectShell subjectId={s} crumb="Resources" action={<Link className="btn-primary" href={`/subjects/${s}/setup`}>Add source</Link>}>
      <div data-screen="W04" className="space-y-4">
        {!data && !error && <Skeleton />}
        {error && <ErrorBox message="Resources could not load." onRetry={reload} />}
        {data?.locked && <p className="card">Course pages are hidden while an independent application is in progress in this subject.</p>}
        {data && data.sources.length > 0 && (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[520px] text-left">
              <caption className="sr-only">Your private sources</caption>
              <thead><tr className="text-meta text-ink-muted"><th className="py-2">Name</th><th>Type</th><th>Status</th><th>Version</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {data.sources.map((src: any) => (
                  <tr key={src.id} className="border-t border-border">
                    <td className="py-3 pr-2">{src.status === "removed" ? <span className="text-ink-muted">{src.filename} (removed)</span> :
                      <Link className="underline" href={`/subjects/${s}/resources/${src.id}?page=1`}>{src.filename}</Link>}</td>
                    <td>{src.role.replace("_", " ")}</td>
                    <td>{src.status.replace("_", " ")}</td>
                    <td>{src.revision_no ? `v${src.revision_no}` : "—"}</td>
                    <td>{src.status !== "removed" && <button className="btn-link" onClick={async () => setImpact(await api(`/sources/${src.id}/impact`))}>Remove<span className="sr-only"> {src.filename}</span></button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data?.open_resources?.length > 0 && (
          <section className="space-y-3" aria-labelledby="open-h">
            <h2 id="open-h" className="text-section">Open resources found for this subject</h2>
            <ul className="grid gap-4 md:grid-cols-2">{data.open_resources.map((r: any) => (
              <li key={r.id} className="game-card p-5">
                <p className="text-meta font-semibold text-ink-muted">{r.provider} · {r.license} · unverified source</p>
                <h3 className="mt-1 font-bold"><a className="underline" href={r.url} target="_blank" rel="noreferrer">{r.title} ↗</a></h3>
                <p className="mt-2 text-meta">{r.summary}</p>
                <p className="mt-2 text-meta text-ink-muted">{r.attribution} <a className="underline" href={r.license_url} target="_blank" rel="noreferrer">License</a></p>
              </li>
            ))}</ul>
          </section>
        )}
        <p className="text-meta text-ink-muted">{data?.generated_aids_note}</p>
      </div>
      <Dialog open={!!impact} title="Remove this source?" onClose={() => setImpact(null)}>
        <p>“{impact?.filename}” is cited by {impact?.cited_concepts} concept(s). {impact?.evidence_effect}</p>
        <p className="mt-2 text-meta text-ink-muted">The file content is deleted from storage. Backups are not covered in this build.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button className="btn-primary" onClick={async () => { await api(`/sources/${impact.source_id}`, { method: "DELETE" }); setImpact(null); reload(); }}>Remove source</button>
          <button className="btn-secondary" onClick={() => setImpact(null)}>Cancel</button>
        </div>
      </Dialog>
    </SubjectShell>
  );
}
