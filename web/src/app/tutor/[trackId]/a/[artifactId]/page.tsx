"use client";
// One piece of revision material: résumé, fiches, QCM, quiz, exercises or a mock exam.
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { ItemPlayer } from "@/components/tutor/ItemPlayer";
import { MockExam } from "@/components/tutor/MockExam";
import { FicheDeck, ResumeView } from "@/components/tutor/Study";
import { LikenessBadge } from "@/components/tutor/bits";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ARTIFACT_LABEL, tutor, type Artifact } from "@/lib/tutor";

export default function ArtifactPage() {
  const { trackId, artifactId } = useParams<{ trackId: string; artifactId: string }>();
  const router = useRouter();
  const a = useApi<Artifact>(`/tutor/artifacts/${artifactId}`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const art = a.data;

  const regenerate = async () => {
    setBusy(true); setErr(null);
    try { const n = await tutor.regenerate(artifactId); router.replace(`/tutor/${trackId}/a/${n.id}`); }
    catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };

  return (
    <AppShell crumbs={[{ label: "Tutor", href: "/tutor" }, { label: "Track", href: `/tutor/${trackId}` }, { label: art ? ARTIFACT_LABEL[art.type] : "…" }]}
      focused={art?.type === "mock_exam"}>
      {a.loading && !art && <Skeleton lines={6} />}
      {a.error && <ErrorBox message={a.error.message} onRetry={a.reload} />}
      {art && (
        <div className="mx-auto max-w-prose space-y-6">
          {art.type !== "mock_exam" && (
            <header className="flex flex-wrap items-end justify-between gap-3">
              <div className="space-y-1">
                <span className="badge">{ARTIFACT_LABEL[art.type]}</span>
                <h1 className="text-page-compact">{art.title}</h1>
              </div>
              <div className="flex items-center gap-2">
                <LikenessBadge value={art.likeness} detail={art.likeness_detail} />
                <button className="btn-secondary" disabled={busy} onClick={regenerate}>{busy ? "Writing…" : "New version"}</button>
              </div>
            </header>
          )}
          {err && <p className="rounded-control bg-review-surface p-3">{err}</p>}
          {art.type === "resume" && <ResumeView content={art.content} />}
          {art.type === "fiches" && <FicheDeck artifactId={art.id} fiches={art.content.items} />}
          {["qcm", "quiz", "exercises"].includes(art.type) && art.content.items.map((it: any, i: number) => (
            <ItemPlayer key={it.id} trackId={trackId} item={it} index={i} />
          ))}
          {art.type === "mock_exam" && <MockExam trackId={trackId} artifact={art} onNew={(n) => router.replace(`/tutor/${trackId}/a/${n.id}`)} />}
        </div>
      )}
    </AppShell>
  );
}
