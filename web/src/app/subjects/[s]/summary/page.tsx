"use client";
// R01 Course summary — written for the learner's level. Course mode: follows the uploaded files page by page and
// shows its page coverage (missing pages are listed, never hidden). Topic mode: one section per roadmap concept.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, MathText, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Illo } from "@/components/Illo";

const FOCUS: Record<string, { label: string; cls: string }> = {
  known: { label: "You know this · quick recap", cls: "bg-hl" },
  focus: { label: "Focus here", cls: "bg-review-surface text-review" },
  new: { label: "New for you", cls: "bg-soft text-soft-fg" },
};
const BLOCK_CLS: Record<string, string> = {
  definition: "border-l-4 border-strong bg-soft/60 p-3 rounded-detail",
  formula: "rounded-detail border-2 border-ink bg-surface-subtle px-4 py-3 text-center",
  example: "rounded-detail border-2 border-dashed border-ink p-3",
  tip: "rounded-detail bg-success-surface p-3",
  warning: "rounded-detail bg-review-surface p-3",
};
const BLOCK_PREFIX: Record<string, string> = { definition: "Definition", example: "Example", tip: "Exam tip", warning: "Watch out" };

function Block({ b }: { b: any }) {
  if (b.type === "heading") return <h4 className="mt-4 text-[1.15rem] font-bold"><MathText text={b.text} /></h4>;
  const body = (
    <>
      {BLOCK_PREFIX[b.type] && <p className="text-meta font-bold uppercase">{BLOCK_PREFIX[b.type]}</p>}
      {b.text && (b.type === "formula"
        ? <div className="overflow-x-auto"><MathText text={b.text} formula /></div>
        : <p className="whitespace-pre-line"><MathText text={b.text} /></p>)}
      {b.items?.length > 0 && <ul className="ml-5 list-disc space-y-1">{b.items.map((it: string, i: number) => <li key={i}><MathText text={it} /></li>)}</ul>}
      {b.pages?.length > 0 && <p className="text-meta text-ink-muted">p. {b.pages.join(", ")}</p>}
    </>
  );
  return <div className={`space-y-1 ${BLOCK_CLS[b.type] ?? ""}`}>{body}</div>;
}

export default function SummaryPage() {
  const { s } = useParams<{ s: string }>();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/summary`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const sm = data?.summary;
  useEffect(() => {
    if (sm?.status !== "building") return;
    const id = setInterval(reload, 2000);
    return () => clearInterval(id);
  }, [sm?.status, reload]);

  const create = async (regenerate: boolean) => {
    setBusy(true);
    setErr(null);
    try { await api(`/subjects/${s}/summary`, { method: "POST", json: { regenerate } }); reload(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const failed = sm ? sm.sections.filter((x: any) => ["failed", "incomplete"].includes(x.status)).length : 0;
  const retryAll = async () => {
    setBusy(true); setErr(null);
    try { await api(`/subjects/${s}/summary/retry-failed`, { method: "POST" }); reload(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const more = async () => {
    setBusy(true); setErr(null);
    try { await api(`/subjects/${s}/summary/more`, { method: "POST" }); reload(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const retry = async (id: string) => { await api(`/summary-sections/${id}/retry`, { method: "POST" }).catch((e) => setErr(e.message)); reload(); };

  return (
    <SubjectShell subjectId={s} crumb="Summary" action={sm && <button className="btn-secondary print:hidden" onClick={() => window.print()}>Print / save as PDF</button>}>
      <div data-screen="R01" className="space-y-6">
        {!data && !error && <div className="card"><Skeleton /></div>}
        {error && <ErrorBox message="The summary could not load." onRetry={reload} />}
        {err && <ErrorBox message={err}><Link className="btn-secondary" href={`/subjects/${s}/start`}>Back to my path</Link></ErrorBox>}
        {data && !sm && (
          <div className="hero p-6 md:p-8"><div className="relative z-10 space-y-3">
            <h2 className="text-page-compact">Your course summary</h2>
            <p className="muted">Written for your level: every page of your course (or every concept of your roadmap), with definitions, worked examples, common mistakes and check questions.</p>
            <button className="btn-primary" disabled={busy} onClick={() => create(false)}>{busy ? "Preparing…" : "Prepare my summary"}</button>
          </div></div>
        )}
        {sm && (
          <>
            <div className="game-card flex flex-wrap items-center gap-4 p-5">
              <span className="badge capitalize">Level: {sm.level}</span>
              <span className="badge"><Illo name={sm.goal === "exam" ? "exam" : "explore"} size={20} />{sm.goal === "exam" ? " Exam preparation" : " Learning"}</span>
              <span className="badge"><Illo name={sm.mode === "course" ? "course" : "sources"} size={20} />{sm.mode === "course" ? " From your course" : " From open sources"}</span>
              {sm.coverage && (
                <div className="min-w-[14rem] flex-1">
                  <p className="text-meta"><strong>Coverage:</strong> {sm.coverage.pages_covered}/{sm.coverage.pages_total} pages</p>
                  <div className="bar" role="progressbar" aria-label="Pages covered" aria-valuemin={0} aria-valuemax={sm.coverage.pages_total} aria-valuenow={sm.coverage.pages_covered}>
                    <span style={{ width: `${Math.round((100 * sm.coverage.pages_covered) / Math.max(1, sm.coverage.pages_total))}%` }} />
                  </div>
                </div>
              )}
              {sm.status === "building" && <p className="text-meta" aria-live="polite">Writing section {Math.min(sm.progress.done + 1, sm.progress.total)} of {sm.progress.total}…</p>}
              <button className="btn-link print:hidden" disabled={busy || sm.status === "building"} onClick={() => create(true)}>Rewrite</button>
            </div>
            {sm.label && <p className="text-meta text-ink-muted">{sm.label}</p>}
            {failed > 0 && sm.status !== "building" && (
              <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border-2 border-review bg-review-surface p-3">
                <p className="text-review">{failed} section(s) could not be written (the AI service was busy). They are retried one by one.</p>
                <button className="btn-primary" disabled={busy} onClick={retryAll}>Retry failed sections</button>
              </div>
            )}
            {sm.coverage?.missing?.length > 0 && (
              <p role="alert" className="rounded-control border-2 border-review bg-review-surface p-3 text-review">
                Not covered yet: {sm.coverage.missing.map((m: any) => `${m.filename} p.${m.page}`).join(", ")}. Use “Try again” on the section.
              </p>
            )}

            {sm.progress.later > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border-2 border-ink bg-soft p-3 print:hidden">
                <p>Long course: {sm.progress.later} more section(s) are written when you need them, so your AI quota is not used up at once.</p>
                <button className="btn-primary" disabled={busy || sm.status === "building"} onClick={more}>Write the next 5</button>
              </div>
            )}
            <nav aria-label="Summary contents" className="game-card max-h-64 overflow-y-auto p-4 print:hidden">
              <ol className="flex flex-wrap gap-2">
                {sm.sections.map((x: any) => (
                  <li key={x.id}><a href={`#sec-${x.no}`} className="chip text-meta">{x.no}. {x.title}{x.status === "pending" ? " …" : ""}</a></li>
                ))}
              </ol>
            </nav>

            {sm.sections.map((x: any) => (
              <article key={x.id} id={`sec-${x.no}`} className="game-card scroll-mt-44 space-y-3 p-5 md:p-7" data-section-status={x.status}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="unit-banner inline-block px-3 py-1 text-meta font-bold">{x.no}</span>
                  <h3 className="flex-1 text-section !text-[1.3rem]">{x.title}</h3>
                  <span className={`rounded-pill border-2 border-ink px-3 py-1 text-meta ${FOCUS[x.focus]?.cls ?? ""}`}>{FOCUS[x.focus]?.label}</span>
                </div>
                {x.pages.length > 0 && <p className="text-meta text-ink-muted">{x.filename} · pages {x.pages.join(", ")}
                  {x.content?.likeness != null && <span className="ml-2 pill" title="How much this section reads like your course: vocabulary, notation, style">Matches your course: {Math.round(100 * x.content.likeness)}%</span>}</p>}
                {x.status === "later" && <button className="btn-secondary" disabled={sm.status === "building"} onClick={() => retry(x.id)}>Write this section</button>}
                {x.status === "pending" && <Skeleton lines={4} label="Writing this section" />}
                {x.status === "failed" && (
                  <ErrorBox message="This section could not be written."><button className="btn-primary" onClick={() => retry(x.id)}>Try again</button></ErrorBox>
                )}
                {x.status === "incomplete" && (
                  <p role="alert" className="text-review">Pages {x.missing_pages.join(", ")} are not covered yet. <button className="btn-link" onClick={() => retry(x.id)}>Try again</button></p>
                )}
                {x.content && (
                  <>
                    <div className="space-y-3">{x.content.blocks.map((b: any, i: number) => <Block key={i} b={b} />)}</div>
                    {x.content.key_terms?.length > 0 && (
                      <div><p className="font-bold">Key terms</p>
                        <dl className="mt-1 grid gap-2 sm:grid-cols-2">{x.content.key_terms.map((k: any) => (
                          <div key={k.term} className="rounded-detail border border-border p-2"><dt className="font-bold"><MathText text={k.term} /></dt><dd className="text-meta"><MathText text={k.definition} /></dd></div>
                        ))}</dl></div>
                    )}
                    {x.content.common_mistakes?.length > 0 && (
                      <div className={BLOCK_CLS.warning}><p className="text-meta font-bold uppercase">Common mistakes</p>
                        <ul className="ml-5 list-disc">{x.content.common_mistakes.map((m: string, i: number) => <li key={i}><MathText text={m} /></li>)}</ul></div>
                    )}
                    {x.content.check_questions?.length > 0 && (
                      <div className="rounded-detail bg-soft/60 p-3"><p className="text-meta font-bold uppercase">Check yourself</p>
                        <ol className="ml-5 list-decimal">{x.content.check_questions.map((q: string, i: number) => <li key={i}><MathText text={q} /></li>)}</ol></div>
                    )}
                    {x.content.sources?.length > 0 && (
                      <p className="text-meta text-ink-muted">Sources: {x.content.sources.map((c: any, i: number) => (
                        <a key={i} className="btn-link" href={c.url} target="_blank" rel="noreferrer">{c.title || c.url}{c.license ? ` (${c.license})` : ""}</a>
                      ))}</p>
                    )}
                  </>
                )}
              </article>
            ))}
            <div className="flex flex-wrap gap-3 print:hidden">
              <Link className="btn-primary" href={`/subjects/${s}/start`}>Back to my path</Link>
              <Link className="btn-secondary" href={`/subjects/${s}/roadmap`}>Open roadmap</Link>
            </div>
          </>
        )}
      </div>
    </SubjectShell>
  );
}
