"use client";
// G02 Subjects — cards with source status and Continue; removal previews impact.
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Dialog, ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const STATUS: Record<string, string> = {
  processing: "Processing", awaiting_confirmation: "Scope needs your confirmation", needs_attention: "Needs attention", ready: "Ready",
};

export default function Subjects() {
  const { data, error, loading, reload } = useApi<any>("/subjects");
  const [remove, setRemove] = useState<any>(null);
  return (
    <AppShell crumbs={[{ label: "Subjects" }]}>
      <div data-screen="G02">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-page-compact lg:text-page">Subjects</h1>
          <Link href="/subjects/new" className="btn-primary">Add subject</Link>
        </div>
        {loading && !data && <div className="card mt-6"><Skeleton /></div>}
        {error && <div className="mt-6"><ErrorBox message="Subjects could not load." onRetry={reload} /></div>}
        {data && data.subjects.length === 0 && (
          <div className="card mt-6 max-w-prose">
            <h2 className="text-section">No subjects yet</h2>
            <p className="mt-2">Upload a course file, paste notes, or choose a guided topic if you are unsure.</p>
          </div>
        )}
        <ul className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data?.subjects.map((s: any) => (
            <li key={s.id} className="card flex flex-col">
              <h2 className="text-section">{s.name}</h2>
              <p className="mt-2 text-meta"><span className="pill text-ink-muted">{STATUS[s.status] || s.status}</span>
                {s.needs_attention && <span className="pill ml-2 text-review">A file needs attention</span>}</p>
              <p className="mt-2 text-meta text-ink-muted">{s.source_count} source{s.source_count === 1 ? "" : "s"} · {s.exam_date ? `Exam ${s.exam_date}` : "No exam date"}</p>
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                <Link className="btn-primary" href={`/subjects/${s.id}/${s.status === "ready" ? "roadmap" : "setup"}`}>Continue</Link>
                <button className="btn-secondary" onClick={() => setRemove(s)}>Archive</button>
              </div>
            </li>
          ))}
        </ul>
        <Dialog open={!!remove} title="Archive this subject?" onClose={() => setRemove(null)}>
          <p>“{remove?.name}” will be hidden from your lists. Its sources and evidence are kept and are not deleted.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button className="btn-primary" onClick={async () => { await api(`/subjects/${remove.id}`, { method: "DELETE" }); setRemove(null); reload(); }}>Archive subject</button>
            <button className="btn-secondary" onClick={() => setRemove(null)}>Cancel</button>
          </div>
        </Dialog>
      </div>
    </AppShell>
  );
}
