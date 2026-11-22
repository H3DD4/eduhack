"use client";
// J01 My learning path — the start-wizard choices, then 4 steps (roadmap → level → summary → learn) with ONE next
// action. Polls while something is being built; asks for the summary automatically once the level is known.
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LevelReport } from "@/components/LevelReport";
import { SubjectShell } from "@/components/SubjectShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const ICON: Record<string, string> = { roadmap: "🗺️", level: "🧪", summary: "📘", learn: "🚀" };

export default function LearningPath() {
  const { s } = useParams<{ s: string }>();
  const router = useRouter();
  const { data, error, reload } = useApi<any>(`/subjects/${s}/journey`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const asked = useRef(false);

  const steps: any[] = data?.steps ?? [];
  const waiting = data && (data.subject.status === "processing" || data.placement?.state === "preparing"
    || data.summary?.status === "building");
  useEffect(() => {
    if (!waiting) return;
    const id = setInterval(reload, 2000);
    return () => clearInterval(id);
  }, [waiting, reload]);

  const createSummary = async (go: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      await api(`/subjects/${s}/summary`, { method: "POST", json: {} });
      if (go) router.push(`/subjects/${s}/summary`);
      else reload();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  // The level is known and no summary exists yet: start writing it right away (the student keeps going meanwhile).
  useEffect(() => {
    if (!data || asked.current) return;
    const sum = steps.find((x) => x.key === "summary");
    if (sum?.state === "current" && sum.action?.create && data.intent.prior_knowledge) {
      asked.current = true;
      createSummary(false);
    }
  });

  // Older subjects have no questions yet: ask the server to write them (idempotent).
  const prepared = useRef(0);
  useEffect(() => {
    if (data?.placement?.state !== "preparing" || Date.now() - prepared.current < 10_000) return;
    prepared.current = Date.now();
    api(`/subjects/${s}/placement/prepare`, { method: "POST" }).then(reload).catch(() => undefined);
  }, [data, s, reload]);

  const changePrior = async (prior: "some" | "none") => {
    setBusy(true);
    await api(`/subjects/${s}/intent`, { method: "PATCH", json: { prior_knowledge: prior } }).catch((e) => setErr(e.message));
    setBusy(false);
    reload();
  };

  const go = (a: any) => (a.create ? createSummary(true) : router.push(a.href));
  const levelStep = steps.find((x) => x.key === "level");
  return (
    <SubjectShell subjectId={s} crumb="My path">
      <div data-screen="J01" className="space-y-6">
        {!data && !error && <div className="card"><Skeleton /></div>}
        {error && <ErrorBox message="Your learning path could not load." onRetry={reload} />}
        {err && <ErrorBox message={err} />}
        {data && (
          <>
            <div className="flex flex-wrap gap-2" aria-label="Your choices">
              <span className="badge">{data.intent.goal === "exam" ? "🎯" : "🧭"} {data.intent.goal_label}
                {data.intent.days_to_exam != null && data.intent.days_to_exam >= 0 ? ` · exam in ${data.intent.days_to_exam} day(s)` : ""}</span>
              <span className="badge">{data.intent.has_material ? `📄 ${data.intent.material.files} file(s) · ${data.intent.material.pages} page(s)` : "✨ Open sources"}</span>
              {data.intent.prior_knowledge && (
                <span className="badge">{data.intent.prior_knowledge === "some" ? "🧪 Level test" : "🌱 From scratch"}</span>
              )}
            </div>

            {data.next && (
              <div className="hero p-6 md:p-8">
                <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-meta font-bold uppercase tracking-wide">Next step</p>
                    <h2 className="text-page-compact">{steps.find((x) => x.key === data.next.step)?.title}</h2>
                    <p className="muted">{steps.find((x) => x.key === data.next.step)?.detail}</p>
                  </div>
                  <button className="btn-primary" disabled={busy} onClick={() => go(data.next)}>{data.next.label}</button>
                </div>
              </div>
            )}

            <ol className="space-y-3" aria-label="Learning path steps">
              {steps.map((st: any, i: number) => (
                <li key={st.key} className={`game-card flex flex-wrap items-center gap-4 p-5 ${st.state === "todo" ? "opacity-70" : ""}`}
                  data-step={st.key} data-state={st.state}>
                  <span aria-hidden className={`flex h-12 w-12 items-center justify-center rounded-pill border-2 border-ink text-[1.4rem] ${st.state === "done" ? "bg-hl" : st.state === "current" ? "bg-soft" : "bg-surface"}`}>
                    {st.state === "done" ? "✓" : ICON[st.key]}
                  </span>
                  <div className="min-w-[12rem] flex-1">
                    <p className="text-meta text-ink-muted">Step {i + 1} · {st.state === "done" ? "Done" : st.state === "current" ? "Now" : "Later"}</p>
                    <p className="text-[1.2rem] font-bold">{st.title}</p>
                    <p className="text-ink-muted">{st.detail}</p>
                  </div>
                  {st.action && st.state !== "todo" && (
                    st.action.href.endsWith("#level")
                      ? <a className="btn-secondary" href="#level">{st.action.label}</a>
                      : <button className="btn-secondary" disabled={busy} onClick={() => go(st.action)}>{st.action.label}</button>
                  )}
                </li>
              ))}
            </ol>

            {levelStep?.state === "current" && (
              <p className="text-meta">
                {data.intent.prior_knowledge === "some"
                  ? <button className="btn-link" disabled={busy} onClick={() => changePrior("none")}>Skip the test and start from scratch</button>
                  : null}
              </p>
            )}
            {data.level?.available && data.level.basis !== "placement_test" && (
              <p className="text-meta">Know some of it already? <button className="btn-link" disabled={busy} onClick={() => changePrior("some")}>Take the level test instead</button></p>
            )}

            {data.level?.available && (
              <section id="level" aria-labelledby="level-h" className="scroll-mt-44 space-y-3">
                <h2 id="level-h" className="text-section">Your level on {data.subject.name}</h2>
                <LevelReport report={data.level} />
                {data.level.basis === "placement_test" && (
                  <Link href={`/subjects/${s}/diagnostic`} className="btn-link">Retake the level test</Link>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </SubjectShell>
  );
}
