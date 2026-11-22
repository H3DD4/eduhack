"use client";
// Track page. Before the material exists it walks the setup (upload → read the course → level check → build);
// afterwards Valley 1 shows the revision dashboard and Valley 2 jumps into the tutorial.
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ErrorBox, Skeleton } from "@/components/ui";
import { LikenessBadge, RunProgress, Section, UploadDrop } from "@/components/tutor/bits";
import { LevelCheck } from "@/components/tutor/LevelCheck";
import { AskBox } from "@/components/tutor/Study";
import { ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ARTIFACT_LABEL, LEVEL_LABEL, tutor, waitRun, type ArtifactSummary, type Run, type Track } from "@/lib/tutor";

const DOC_TYPE: Record<string, string> = { course: "Course", exercises: "Exercise sheet", past_exam: "Past exam", solutions: "Solutions", slides: "Slides", notes: "Notes", other: "Other" };
const STEPS = ["Documents", "Read the course", "Level check", "Build"];

function stepOf(t: Track): number {
  if (["created", "ingesting"].includes(t.status)) return t.status === "ingesting" ? 1 : 0;
  if (["awaiting_level", "probing"].includes(t.status)) return 2;
  if (["levelled", "building"].includes(t.status)) return 3;
  if (t.status === "failed") return t.measured_level ? 3 : t.stats?.probe ? 2 : 1;
  return 4;
}

function Setup({ track, reload }: { track: Track; reload: () => void }) {
  const [run, setRun] = useState<Run | null>(track.last_run && track.last_run.status !== "succeeded" ? track.last_run : null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const step = stepOf(track);

  const follow = useCallback(async (r: Run) => {
    setRun(r);
    const end = await waitRun(r.id, setRun);
    if (end.status === "succeeded") reload();
  }, [reload]);
  useEffect(() => { if (run && (run.status === "running" || run.status === "queued")) follow(run); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (files: File[]) => {
    setBusy(true); setErr(null);
    try { await tutor.upload(track.id, files); reload(); } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };
  const start = async (kind: "prepare" | "build") => {
    setErr(null);
    try { await follow(kind === "prepare" ? await tutor.prepare(track.id) : await tutor.build(track.id)); } catch (e) { setErr((e as ApiError).message); }
  };
  const resume = async () => { if (run) await follow(await tutor.resume(run.id)); };

  return (
    <div className="space-y-8">
      <ol className="flex flex-wrap gap-2" aria-label="Setup steps">
        {STEPS.map((s, i) => (
          <li key={s} className={`chip ${i === step ? "bg-hl" : i < step ? "bg-strong" : ""}`} aria-current={i === step ? "step" : undefined}>{i < step ? "✓ " : `${i + 1}. `}{s}</li>
        ))}
      </ol>
      {err && <p className="rounded-control bg-review-surface p-3">{err}</p>}

      {step <= 1 && (
        <Section title="Your documents">
          <UploadDrop onFiles={upload} busy={busy} />
          {!!track.documents?.length && (
            <ul className="grid gap-2 md:grid-cols-2">
              {track.documents.map((d) => (
                <li key={d.id} className="card flex items-center justify-between gap-2 p-3">
                  <span className="truncate">{d.filename}</span>
                  <span className="flex items-center gap-2 text-meta">
                    {d.status === "indexed" && <span className="pill">{DOC_TYPE[d.doc_type] || d.doc_type}</span>}
                    {d.ocr_pages > 0 && <span className="pill">OCR {d.ocr_pages} p.</span>}
                    {d.status === "failed" ? <span className="text-[color:var(--needs-review)]">{d.error}</span> : d.status !== "indexed" ? "waiting" : `${d.pages} p.`}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-meta text-ink-muted">Tip: add a past exam or an exercise sheet, so the tutor copies its structure and style.</p>
          <button className="btn-primary" disabled={(!track.documents?.length && track.valley === "revision") || run?.status === "running"} onClick={() => start("prepare")}>
            Read my course
          </button>
        </Section>
      )}
      {run && (run.flow === "prepare" ? step <= 1 || run.status === "failed" : step >= 3) && <RunProgress run={run} onResume={resume} />}
      {step === 2 && <LevelCheck trackId={track.id} chapters={track.chapters} onDone={() => reload()} />}
      {step === 3 && !run?.status?.match(/running|queued/) && (
        <Section title={track.valley === "revision" ? "Build my revision pack" : "Build my tutorial"}>
          <p>Level: <strong>{track.measured_level ? LEVEL_LABEL[track.measured_level] : "—"}</strong>. {track.valley === "revision"
            ? "The tutor writes résumés, fiches, QCM, quizzes, exercises and a mock exam, then plans them up to the exam."
            : "The tutor orders the concepts, writes the first pages and opens page one."}</p>
          <button className="btn-primary" onClick={() => start("build")}>Build</button>
        </Section>
      )}
    </div>
  );
}

function Revision({ track }: { track: Track }) {
  const arts = useApi<{ artifacts: ArtifactSummary[] }>(`/tutor/tracks/${track.id}/artifacts`);
  const plan = useApi<any>(`/tutor/tracks/${track.id}/plan`);
  const report = useApi<any>(`/tutor/tracks/${track.id}/report`);
  const byChapter: Record<string, ArtifactSummary[]> = {};
  arts.data?.artifacts.filter((a) => a.type !== "mock_exam").forEach((a) => { (byChapter[a.chapter || "—"] ||= []).push(a); });
  const mock = arts.data?.artifacts.filter((a) => a.type === "mock_exam").at(-1);
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = (plan.data?.entries || []).filter((e: any) => e.date >= today).slice(0, 6);
  return (
    <div className="space-y-10">
      <section className="hero p-7 md:p-9">
        <div className="relative z-10 grid gap-6 md:grid-cols-[1fr_auto]">
          <div className="space-y-2">
            <span className="badge">{track.exam_date ? `Exam in ${plan.data?.days_left ?? "…"} days` : "Exam revision"}</span>
            <h1 className="text-page">{track.title}</h1>
            <p>Level {track.measured_level ? LEVEL_LABEL[track.measured_level] : "—"} · readiness {report.data ? Math.round(report.data.readiness * 100) : "…"}%</p>
            <div className="bar max-w-md"><span style={{ width: `${Math.round((report.data?.readiness || 0) * 100)}%` }} /></div>
          </div>
          <div className="flex flex-col gap-2">
            {mock && <Link className="btn-primary" href={`/tutor/${track.id}/a/${mock.id}`}>Take the mock exam</Link>}
            <Link className="btn-secondary" href={`/tutor/${track.id}/report`}>Readiness report</Link>
          </div>
        </div>
      </section>

      {upcoming.length > 0 && (
        <Section title="Plan">
          <ul className="grid gap-2 md:grid-cols-3">
            {upcoming.map((e: any, i: number) => (
              <li key={i} className="card space-y-1 p-4">
                <p className="text-meta text-ink-muted">{new Date(e.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })} · {e.minutes} min</p>
                <p className="font-semibold">{e.activity === "mock_exam" ? "Mock exam" : e.title}</p>
                <span className="pill">{e.activity}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {arts.loading && !arts.data && <Skeleton lines={4} />}
      {Object.entries(byChapter).map(([ch, list]) => (
        <Section key={ch} title={ch}>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {["resume", "fiches", "qcm", "quiz", "exercises"].map((type) => {
              const a = list.find((x) => x.type === type);
              return (
                <li key={type}>
                  {a ? (
                    <Link href={`/tutor/${track.id}/a/${a.id}`} className="game-card block h-full space-y-2 p-4 transition hover:-translate-y-1">
                      <p className="text-problem font-semibold">{ARTIFACT_LABEL[type]}</p>
                      <p className="text-meta">{a.count} {type === "resume" ? "sections" : "items"}</p>
                      <LikenessBadge value={a.likeness} />
                    </Link>
                  ) : <div className="card h-full p-4 text-ink-muted">{ARTIFACT_LABEL[type]}: not enough material</div>}
                </li>
              );
            })}
          </ul>
        </Section>
      ))}
      <AskBox trackId={track.id} />
    </div>
  );
}

export default function TrackPage() {
  const { trackId } = useParams<{ trackId: string }>();
  const router = useRouter();
  const track = useApi<Track>(`/tutor/tracks/${trackId}`);
  const t = track.data;
  useEffect(() => { if (t?.status === "ready" && t.valley === "skills") router.replace(`/tutor/${t.id}/learn`); }, [t, router]);
  return (
    <AppShell crumbs={[{ label: "Tutor", href: "/tutor" }, { label: t?.title || "Track" }]}>
      {track.loading && !t && <Skeleton lines={5} />}
      {track.error && <ErrorBox message={track.error.message} onRetry={track.reload} />}
      {t && (t.status === "ready" ? (t.valley === "revision" ? <Revision track={t} /> : <Skeleton lines={3} label="Opening the tutorial" />)
        : <><h1 className="mb-6 text-page-compact">{t.title}</h1><Setup track={t} reload={track.reload} /></>)}
    </AppShell>
  );
}
