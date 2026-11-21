"use client";
// C02 Processing and scope confirmation — UC03/UC04/UC06. Actual phases only; partial success retained;
// only confirmed sources feed tasks.
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, LiveRegion, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const PHASE: Record<string, string> = {
  queued: "Queued", extracting: "Extracting text", extracted: "Extracted", awaiting_confirmation: "Awaiting your confirmation",
  needs_attention: "Needs attention", cancelled: "Cancelled", ready: "Ready", excluded: "Excluded", removed: "Removed",
};
const CAUSE: Record<string, string> = {
  UNSUPPORTED_TYPE: "This file type is not supported. Use PDF (with text), PPTX, TXT or MD — or paste the text.",
  TOO_LARGE: "This file is larger than the limit. Split it or paste the relevant part.",
  ENCRYPTED_FILE: "This PDF is password-protected. Export an unprotected copy.",
  NO_TEXT: "No text found — it may be scanned. OCR arrives later; paste the text or use a guided topic.",
  UNREADABLE_FILE: "The file could not be read. Replace it or paste its text.",
  TOO_MANY_PAGES: "This file has more pages than the limit.",
  NO_STRUCTURE_FOUND: "No numbered headings were found to build a roadmap. Without an AI service, the heuristic needs headings like “1.2 Topic”.",
  EMPTY_FILE: "The file is empty.",
};

export default function Setup() {
  const { s } = useParams<{ s: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/setup`);
  const [edits, setEdits] = useState<Record<string, { title?: string; excluded?: boolean }>>({});
  const [selected, setSelected] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const processing = data?.sources?.some((x: any) => ["queued", "extracting"].includes(x.status));

  useEffect(() => {
    if (!processing) return;
    const id = setInterval(reload, 1500);
    return () => clearInterval(id);
  }, [processing, reload]);
  useEffect(() => { if (data?.proposal) setMsg("Proposed scope ready for review."); }, [data?.proposal]);

  const act = async (id: string, action: string) => {
    await api(`/sources/${id}/${action}`, { method: "POST" }).catch((e) => setErr(e.message));
    reload();
  };
  const replace = async (id: string, file: File) => {
    const fd = new FormData();
    fd.set("file", file);
    await api(`/sources/${id}/replace`, { method: "POST", body: fd, retries: 0 }).catch((e) => setErr(e.message));
    reload();
  };
  const confirm = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/subjects/${s}/scope/confirm`, { method: "POST", json: {
        graph_revision_id: data.proposal.id,
        edits: Object.entries(edits).map(([concept_id, e]) => ({ concept_id, ...e })) } });
      router.push(`/subjects/${s}/roadmap`);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
      reload();
    }
  };

  const concepts = data?.proposal?.concepts ?? [];
  return (
    <AppShell crumbs={[{ href: "/subjects", label: "Subjects" }, { label: data?.subject?.name ?? "Setup" }, { label: "Setup" }]}>
      <LiveRegion message={msg} />
      <div data-screen="C02">
        <h1 className="text-page-compact lg:text-page">Set up {data?.subject?.name ?? "your subject"}</h1>
        {!data && !error && <div className="card mt-6"><Skeleton /></div>}
        {error && <div className="mt-6"><ErrorBox message="Setup could not load." onRetry={reload} /></div>}
        {err && <div className="mt-4"><ErrorBox message={err} /></div>}
        {data && (
          <div className="mt-6 grid gap-6 xl:grid-cols-[300px_1fr_320px]">
            <section aria-labelledby="files-h" className="space-y-3">
              <h2 id="files-h" className="text-section">Files</h2>
              {data.sources.length === 0 && <p className="text-ink-muted">Guided topic — no files.</p>}
              {data.sources.map((src: any) => (
                <div key={src.id} className="card !p-4">
                  <p className="font-semibold break-all">{src.filename}</p>
                  <p className="mt-1 text-meta"><span className={`pill ${src.status === "needs_attention" ? "text-review" : "text-ink-muted"}`}>{PHASE[src.status] || src.status}</span>
                    {src.page_count ? <span className="ml-2 text-ink-muted">{src.page_count} pages</span> : null}</p>
                  {src.error_code && <p className="mt-2 text-meta">{CAUSE[src.error_code] || src.error_code}</p>}
                  {src.status === "needs_attention" && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="btn-secondary" onClick={() => act(src.id, "retry")}>Retry</button>
                      <label className="btn-secondary cursor-pointer">Replace<input type="file" className="sr-only" accept=".pdf,.pptx,.txt,.md"
                        onChange={(e) => e.target.files?.[0] && replace(src.id, e.target.files[0])} /></label>
                      <button className="btn-secondary" onClick={() => act(src.id, "exclude")}>Exclude</button>
                    </div>
                  )}
                  {["queued", "extracting"].includes(src.status) && <button className="btn-secondary mt-3" onClick={() => act(src.id, "cancel")}>Cancel</button>}
                </div>
              ))}
            </section>

            <section aria-labelledby="scope-h">
              <h2 id="scope-h" className="text-section">Proposed scope</h2>
              {processing && <p className="mt-2" aria-busy="true">Extracting text from your files… (no percentages are shown because extraction progress is not measurable)</p>}
              {!processing && !data.proposal && <p className="mt-2 text-ink-muted">No usable scope yet. Fix or replace a file, paste text, or choose a guided topic.</p>}
              {data.proposal && (
                <>
                  <p className="mt-2 text-meta"><span className="pill text-help bg-help-surface">{data.proposal.label}</span></p>
                  <ol className="mt-4 space-y-2">
                    {concepts.map((c: any) => {
                      const e = edits[c.id] || {};
                      const excluded = e.excluded ?? c.excluded;
                      return (
                        <li key={c.id} className={`rounded-detail border px-3 py-2 ${excluded ? "border-border opacity-60" : "border-stroke"}`}>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-meta text-ink-muted">Unit {c.unit_no} · {c.key}{c.is_foundation ? " · foundation" : ""}</span>
                            {c.uncertain && <span className="pill text-review">Uncertain — check</span>}
                          </div>
                          <label className="sr-only" htmlFor={`t-${c.id}`}>Concept title</label>
                          <input id={`t-${c.id}`} className="field mt-1" value={e.title ?? c.title}
                            onChange={(ev) => setEdits({ ...edits, [c.id]: { ...e, title: ev.target.value } })} />
                          {c.objective && <p className="mt-1 text-meta">Objective: {c.objective}</p>}
                          <div className="mt-2 flex flex-wrap gap-3">
                            <label className="flex min-h-[44px] items-center gap-2"><input type="checkbox" checked={!excluded}
                              onChange={(ev) => setEdits({ ...edits, [c.id]: { ...e, excluded: !ev.target.checked } })} /> Include</label>
                            {c.citations?.[0] && <button className="btn-link" onClick={() => setSelected(c)}>See cited page {c.citations[0].page}</button>}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                  <button className="btn-primary mt-6" onClick={confirm} disabled={busy || processing}>{busy ? "Confirming…" : "Confirm scope"}</button>
                </>
              )}
            </section>

            <aside aria-labelledby="cite-h" className="card h-fit">
              <h2 id="cite-h" className="text-section">Cited page</h2>
              {!selected ? <p className="mt-2 text-meta text-ink-muted">Choose “See cited page” to check where a concept came from.</p> : (
                <>
                  <p className="mt-2 font-semibold">{selected.title}</p>
                  <p className="text-meta text-ink-muted">{selected.citations[0].filename} · page {selected.citations[0].page}</p>
                  <blockquote className="mt-3 border-l-4 border-action pl-3">{selected.citations[0].quote || "(no quotable line on this page)"}</blockquote>
                </>
              )}
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}
