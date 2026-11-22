"use client";
/* Valley 2 · W3Schools-style tutorial: chapter sidebar, page with Previous/Next, Example boxes,
   "Try it yourself" items, common mistakes, summary. Pages unlock in order; mastered pages can be skipped. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { TeacherAvatar } from "@/components/avatar/TeacherAvatar";
import { ApiError } from "@/lib/api";
import { tutor, type Artifact, type TutorialNode } from "@/lib/tutor";
import { Citations, LikenessBadge } from "./bits";
import { ItemPlayer } from "./ItemPlayer";
import { CodeBlock, Md } from "./Tex";

const ICON: Record<TutorialNode["status"], string> = { done: "✓", open: "•", skippable: "↷", locked: "🔒" };

export function TutorialSidebar({ trackId, nodes, current }: { trackId: string; nodes: TutorialNode[]; current?: string }) {
  return (
    <nav aria-label="Tutorial" className="space-y-1">
      {nodes.map((n) => {
        if (n.kind === "chapter") return <p key={n.id} className="mt-4 px-3 text-meta font-semibold uppercase tracking-wide text-ink-muted first:mt-0">{n.title}</p>;
        const active = n.slug === current;
        const locked = n.status === "locked";
        const cls = `flex items-center gap-2 rounded-control px-3 py-1.5 transition ${active ? "bg-strong font-semibold" : locked ? "text-ink-muted" : "hover:bg-soft"}`;
        const body = (
          <>
            <span aria-hidden className="w-4 text-center">{ICON[n.status]}</span>
            <span className="flex-1">{n.kind === "page" ? n.title : n.kind === "quiz" ? "Chapter quiz" : n.title}</span>
            {n.kind === "page" && n.mastery > 0 && <span className="text-meta">{Math.round(n.mastery * 100)}%</span>}
          </>
        );
        return locked
          ? <span key={n.id} className={cls} aria-disabled="true" title="Finish the previous page first">{body}</span>
          : <Link key={n.id} href={`/tutor/${trackId}/learn/${n.slug}`} className={cls} aria-current={active ? "page" : undefined}>{body}</Link>;
      })}
    </nav>
  );
}

function PrevNext({ trackId, prev, next, onComplete, busy }: { trackId: string; prev?: string | null; next?: string | null; onComplete: () => void; busy: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      {prev ? <Link className="btn-secondary" href={`/tutor/${trackId}/learn/${prev}`}>« Previous</Link> : <span />}
      <button className="btn-primary" disabled={busy} onClick={onComplete}>{next ? "Done · Next »" : "Done"}</button>
    </div>
  );
}

export function LessonPage({ trackId, node, artifact, onChanged }: { trackId: string; node: TutorialNode; artifact: Artifact; onChanged: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showAvatar, setShowAvatar] = useState(true);
  const c = artifact.content;

  const fullLessonScript = (c.sections || [])
    .filter((s: any) => s.type !== "try" && s.body)
    .map((s: any) => `${s.title ? `${s.title}. ` : ""}${s.body}`)
    .join(" ");

  const askTutorAvatar = async (question: string) => {
    try {
      const r = await tutor.ask(trackId, question, "study");
      if (r?.answer) return r.answer;
    } catch {
      // Fallback handled by TeacherAvatar
    }
  };

  const complete = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await tutor.complete(trackId, node.slug);
      onChanged();
      if (r.skill) router.push(`/tutor/${trackId}/report`);
      else if (r.next) router.push(`/tutor/${trackId}/learn/${r.next.slug}`);
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };

  if (artifact.type !== "lesson") {   // chapter quiz, project, checkpoint
    const items = c.items || [];
    return (
      <article className="space-y-5">
        <header className="space-y-2">
          <span className="badge">{node.kind === "quiz" ? "Chapter quiz" : node.kind === "project" ? "Project" : "Skill checkpoint"}</span>
          <h1 className="text-page">{node.title}</h1>
          <p className="text-ink-muted">{node.kind === "checkpoint" ? "No help on this one: show what you can do on your own. 80 % to earn the skill."
            : "Score at least 70 % to finish this step."}</p>
        </header>
        {items.map((it: any, i: number) => <ItemPlayer key={it.id} trackId={trackId} item={it} index={i} mode="lesson" />)}
        {err && <p role="status" className="rounded-control bg-review-surface p-3">{err}</p>}
        <PrevNext trackId={trackId} next="x" onComplete={complete} busy={busy} />
      </article>
    );
  }

  return (
    <article className="space-y-6">
      <PrevNext trackId={trackId} prev={c.prev_slug} next={c.next_slug} onComplete={complete} busy={busy} />
      <header className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="badge">{c.chapter}</span>
            {node.status === "skippable" && <span className="pill">You already know this — skim or skip</span>}
            <LikenessBadge value={artifact.likeness} detail={artifact.likeness_detail} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setShowAvatar((v) => !v)}
              className="btn-secondary !min-h-[36px] !px-3 text-meta"
            >
              🎓 {showAvatar ? "Hide 3D Teacher" : "Learn with 3D Teacher"}
            </button>
            {fullLessonScript && <SpeakButton text={fullLessonScript} title={c.title} hint={c.chapter || c.title} label="Dock Avatar" />}
          </div>
        </div>
        <h1 className="text-page">{c.title}</h1>
      </header>

      {showAvatar && fullLessonScript && (
        <TeacherAvatar
          text={fullLessonScript}
          hint={`${c.chapter || ""} ${c.title || ""}`}
          title={c.title}
          compact
          stageHeight={260}
          onAsk={askTutorAvatar}
        />
      )}

      {c.sections.map((s: any, i: number) => {
        if (s.type === "intro") return <div key={i} className="text-problem"><Md text={s.body} /></div>;
        if (s.type === "explain") return (
          <section key={i} className="space-y-2">
            {s.title && s.title !== c.title && <h2 className="text-section">{s.title}</h2>}
            <Md text={s.body} />
            {s.code && <CodeBlock code={s.code} language={s.language} />}
            <Citations items={s.citations} />
          </section>
        );
        if (s.type === "example") return (
          <section key={i} className="rounded-card border-2 border-ink bg-soft p-5 shadow-hard">
            <h3 className="mb-2 text-problem font-semibold">{s.title || "Example"}</h3>
            <Md text={s.body} />
            {s.code && <CodeBlock code={s.code} language={s.language} />}
            <a href={`#try-${node.slug}`} className="btn-primary mt-3 inline-flex">Try it yourself »</a>
          </section>
        );
        if (s.type === "try") return (
          <section key={i} id={`try-${node.slug}`} className="space-y-3 scroll-mt-24">
            <h2 className="text-section">{s.title || "Try it yourself"}</h2>
            {s.body && <Md text={s.body} />}
            {s.items.map((it: any, j: number) => <ItemPlayer key={it.id} trackId={trackId} item={it} index={j} mode="lesson" />)}
          </section>
        );
        if (s.type === "mistakes") return (
          <section key={i} className="rounded-card border-2 border-ink bg-review-surface p-5">
            <h3 className="mb-1 text-problem font-semibold">{s.title || "Common mistakes"}</h3>
            <Md text={s.body} />
          </section>
        );
        if (s.type === "summary") return (
          <section key={i} className="rounded-card border-2 border-ink bg-hl p-5">
            <h3 className="mb-1 text-problem font-semibold">{s.title || "Remember"}</h3>
            <Md text={s.body} />
          </section>
        );
        return <section key={i}><h2 className="text-section">{s.title}</h2><Md text={s.body} /></section>;
      })}

      {err && <p role="status" className="rounded-control bg-review-surface p-3">{err}</p>}
      <PrevNext trackId={trackId} prev={c.prev_slug} next={c.next_slug} onComplete={complete} busy={busy} />
    </article>
  );
}
