"use client";
// Valley 2 · tutorial layout: sidebar of chapters and pages (left), the current page (centre), ask box (below).
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { LessonPage, TutorialSidebar } from "@/components/tutor/Lesson";
import { AskBox } from "@/components/tutor/Study";
import { useApi } from "@/lib/hooks";
import type { Artifact, Track, TutorialNode } from "@/lib/tutor";

export default function Learn() {
  const { trackId, slug } = useParams<{ trackId: string; slug?: string[] }>();
  const router = useRouter();
  const track = useApi<Track>(`/tutor/tracks/${trackId}`);
  const tree = useApi<{ nodes: TutorialNode[] }>(`/tutor/tracks/${trackId}/tutorial`);
  const nodes = tree.data?.nodes || [];
  const current = slug?.[0] || nodes.find((n) => n.kind !== "chapter" && n.status === "open")?.slug
    || nodes.find((n) => n.kind === "page")?.slug;
  const page = useApi<{ node: TutorialNode; artifact: Artifact }>(current ? `/tutor/tracks/${trackId}/lessons/${current}` : null);
  const [menu, setMenu] = useState(false);

  useEffect(() => { if (!slug?.[0] && current) router.replace(`/tutor/${trackId}/learn/${current}`); }, [slug, current, trackId, router]);
  const done = nodes.filter((n) => n.kind === "page" && n.status === "done").length;
  const pages = nodes.filter((n) => n.kind === "page").length;

  return (
    <AppShell crumbs={[{ label: "Tutor", href: "/tutor" }, { label: track.data?.title || "Tutorial" }]}>
      <div className="grid gap-8 lg:grid-cols-[280px_1fr]" data-screen="TUTOR-LEARN">
        <aside className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <div className="card space-y-3 p-4">
            <div className="flex items-center justify-between">
              <p className="font-semibold">{track.data?.title}</p>
              <button className="btn-link lg:hidden" aria-expanded={menu} onClick={() => setMenu((m) => !m)}>{menu ? "Hide" : "Menu"}</button>
            </div>
            <div className="flex items-center gap-2 text-meta">
              <div className="bar flex-1"><span style={{ width: `${pages ? (done / pages) * 100 : 0}%` }} /></div>
              <span>{done}/{pages}</span>
            </div>
            <div className={`${menu ? "block" : "hidden"} lg:block`}>
              {tree.loading && !tree.data ? <Skeleton lines={6} /> : <TutorialSidebar trackId={trackId} nodes={nodes} current={current} />}
            </div>
          </div>
        </aside>
        <main className="min-w-0 max-w-prose space-y-8">
          {page.loading && !page.data && <Skeleton lines={8} label="Writing this page from your course" />}
          {page.error && <ErrorBox message={page.error.message} onRetry={page.reload} />}
          {page.data && <LessonPage trackId={trackId} node={page.data.node} artifact={page.data.artifact} onChanged={tree.reload} />}
          <AskBox trackId={trackId} />
        </main>
      </div>
    </AppShell>
  );
}
