"use client";
// W07 Cited document viewer — UC33. Opens the exact cited page; Return restores the origin; tombstones for removed
// sources; denied while an independent transfer is active (no answer-revealing previews).
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, MathText, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

function Viewer() {
  const { s, d } = useParams<{ s: string; d: string }>();
  const q = useSearchParams();
  const router = useRouter();
  const page = Number(q.get("page") || "1");
  const ret = q.get("return");
  const safeRet = ret && ret.startsWith("/") && !ret.startsWith("//") ? ret : `/subjects/${s}/resources`;
  const { data, error, reload } = useApi<any>(`/documents/${d}/pages/${page}`);
  const go = (p: number) => router.replace(`/subjects/${s}/resources/${d}?page=${p}${ret ? `&return=${encodeURIComponent(ret)}` : ""}`);
  return (
    <SubjectShell subjectId={s} crumb="Document">
      <div data-screen="W07" className="max-w-prose space-y-4">
        {!data && !error && <Skeleton lines={8} />}
        {error?.code === "TRANSFER_LOCKED" && <ErrorBox title="Hidden during independent application" message={error.message}><Link className="btn-secondary" href={safeRet}>Return</Link></ErrorBox>}
        {error && error.code !== "TRANSFER_LOCKED" && <ErrorBox message={error.message} onRetry={reload} />}
        {data?.tombstone && (
          <div className="card"><p className="font-semibold">This source was removed</p>
            <p className="mt-1 text-meta">“{data.filename}” was removed{data.removed_at ? ` on ${new Date(data.removed_at).toLocaleDateString()}` : ""}. Earlier evidence keeps its record.</p>
            <Link className="btn-secondary mt-3" href={`/subjects/${s}/setup`}>Replace source</Link></div>
        )}
        {data && !data.tombstone && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">{data.filename} · v{data.revision_no} · page {data.page} of {data.page_count}</p>
              <div className="flex gap-2">
                <button className="btn-secondary" onClick={() => go(page - 1)} disabled={page <= 1}>Previous page</button>
                <button className="btn-secondary" onClick={() => go(page + 1)} disabled={page >= data.page_count}>Next page</button>
              </div>
            </div>
            <article className="card whitespace-pre-line text-problem" aria-label={`Page ${page} text`}><MathText text={data.text} /></article>
            <p className="text-meta text-ink-muted">Extracted text. Annotations and bookmarks arrive later.</p>
          </>
        )}
        <Link className="btn-primary" href={safeRet}>Return</Link>
      </div>
    </SubjectShell>
  );
}

export default function Page() {
  return <Suspense><Viewer /></Suspense>;
}
