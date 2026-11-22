"use client";
// C01 Start learning — the start wizard: why (exam / new) → what (topic) → material (files / paste / none) →
// prior knowledge (test my level / start from scratch) → review. Then C02 builds the roadmap and the learning path
// (/subjects/:s/start) takes over: level → course summary → first lesson.
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { DemoLabel, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Illo, type IlloName } from "@/components/Illo";

type Goal = "exam" | "explore";
type Prior = "some" | "none";
const STEPS = ["Why", "Topic", "Material", "Your level", "Check"];
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";

function Choice({ pressed, onClick, icon, title, text, name }:
  { pressed: boolean; onClick: () => void; icon: IlloName; title: string; text: string; name?: string }) {
  return (
    <button type="button" aria-pressed={pressed} onClick={onClick} aria-label={name ?? title}
      className={`game-card flex w-full items-start gap-4 p-5 text-left ${pressed ? "!bg-hl" : ""}`}>
      <span aria-hidden className="flex h-14 w-14 shrink-0 items-center justify-center rounded-card border-2 border-ink bg-soft"><Illo name={icon} size={42} /></span>
      <span><span className="block text-[1.25rem] font-bold">{title}</span><span className="mt-1 block text-ink-muted">{text}</span></span>
    </button>
  );
}

// Must render INSIDE <AppShell>: useMe() reads the shell's context (outside it, `me` is always undefined).
function DemoCourseButton({ onFile }: { onFile: (f: File) => void }) {
  const { me } = useMe();
  if (!me?.is_demo) return null;
  return (
    <div className="card border-discovery">
      <DemoLabel />
      <p className="mt-2 text-meta">A permission-cleared demo course (MATH 101 — Algebra Foundations) is available for the demo account.</p>
      <button type="button" className="btn-secondary mt-3" onClick={async () => {
        const blob = await api<Blob>("/demo/course-file");
        onFile(new File([blob], "MATH101-algebra-foundations-DEMO.pdf", { type: "application/pdf" }));
      }}>Use the demo course file</button>
    </div>
  );
}

export default function StartWizard() {
  const router = useRouter();
  const { data: limits } = useApi<any>("/limits");
  const { data: sugg } = useApi<any>("/topics/suggestions");
  const [step, setStep] = useState(0);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [examDate, setExamDate] = useState("");
  const [topic, setTopic] = useState("");
  const [material, setMaterial] = useState<"files" | "none" | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [paste, setPaste] = useState("");
  const [rights, setRights] = useState(false);
  const [prior, setPrior] = useState<Prior | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const headRef = useRef<HTMLHeadingElement>(null);
  const maxMb = limits ? Math.round(limits.max_file_bytes / 1048576) : 20;

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("topic");
    if (t) setTopic(t.slice(0, 200));
  }, []);
  useEffect(() => { headRef.current?.focus(); }, [step]);

  const addFiles = (list: FileList | File[]) => {
    const arr = Array.from(list);
    setFiles((f) => [...f, ...arr].slice(0, limits?.max_files_per_batch ?? 5));
    if (!topic && arr[0]) setTopic(arr[0].name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "));
  };
  const hasMaterial = material === "files" && (files.length > 0 || paste.trim().length > 0);
  const maxBytes = limits?.max_file_bytes ?? 20 * 1048576;
  const tooBig = files.filter((f) => f.size > maxBytes);
  const canNext = [
    !!goal,
    topic.trim().length >= 2,
    material === "none" || (material === "files" && hasMaterial && rights && tooBig.length === 0),
    !!prior,
    true,
  ][step];
  const next = () => canNext && setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.set("topic", topic.trim());
      fd.set("goal", goal!);
      fd.set("prior_knowledge", prior!);
      if (goal === "exam" && examDate) fd.set("exam_date", examDate);
      if (material === "files") {
        fd.set("rights_ack", String(rights));
        fd.set("paste_text", paste);
        files.forEach((f) => fd.append("files", f));
      }
      const r = await api("/subjects/start", { method: "POST", body: fd, retries: 0 });
      router.push(`/subjects/${r.subject.id}/setup`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <AppShell crumbs={[{ label: "Start learning" }]} back={false}>
      <div className="mx-auto max-w-prose" data-screen="C01">
        <div className="mb-6 flex items-center gap-3">
          <button type="button" className="btn-secondary !min-h-[42px] !rounded-pill !px-4" onClick={step === 0 ? () => router.push("/subjects") : back}
            aria-label={step === 0 ? "Back to Subjects" : "Back to the previous question"}>← Back</button>
          <div className="bar flex-1" role="progressbar" aria-label="Start wizard progress" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1}>
            <span style={{ width: `${Math.round((100 * (step + 1)) / STEPS.length)}%` }} />
          </div>
          <span className="text-meta text-ink-muted">{step + 1}/{STEPS.length}</span>
        </div>
        {error && <div className="mb-4"><ErrorBox message={error} /></div>}

        <section key={step} className="step-in space-y-5">
          {step === 0 && (
            <>
              <h1 ref={headRef} tabIndex={-1} className="text-page-compact md:text-page">Why are you learning?</h1>
              <div className="grid gap-4">
                <Choice pressed={goal === "exam"} onClick={() => setGoal("exam")} icon="exam" title="I'm preparing for an exam"
                  text="A focused path: what is typically asked, classic traps, and a summary to revise from." />
                <Choice pressed={goal === "explore"} onClick={() => setGoal("explore")} icon="explore" title="I want to learn something new"
                  text="Learn any topic from zero or deepen it — with or without your own documents." />
              </div>
              {goal === "exam" && (
                <div className="fade-in">
                  <label htmlFor="exam-date" className="label">Exam date (optional)</label>
                  <input id="exam-date" type="date" className="field max-w-xs" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
                </div>
              )}
            </>
          )}

          {step === 1 && (
            <>
              <h1 ref={headRef} tabIndex={-1} className="text-page-compact md:text-page">What do you want to learn?</h1>
              <label htmlFor="topic" className="sr-only">Topic</label>
              <input id="topic" className="field !min-h-[56px] text-problem" maxLength={200} value={topic} autoFocus
                placeholder="e.g. Ohm's law, derivatives, French revolution, Python loops…" onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && next()} />
              {sugg?.suggestions && (
                <ul className="flex flex-wrap gap-2" aria-label="Suggested topics">
                  {sugg.suggestions.map((x: any) => (
                    <li key={x.topic}><button type="button" className="chip text-ink" aria-pressed={topic === x.topic} onClick={() => setTopic(x.topic)}>
                      <span aria-hidden className="text-action">{x.icon}</span> {x.topic}</button></li>
                  ))}
                </ul>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h1 ref={headRef} tabIndex={-1} className="text-page-compact md:text-page">Do you have course material?</h1>
              <div className="grid gap-4">
                <Choice pressed={material === "files"} onClick={() => setMaterial("files")} icon="course" title="Yes — use my course"
                  text="Upload your course (several files: PDF, Word, PowerPoint, text) or paste notes. The roadmap and summary follow it page by page." />
                <Choice pressed={material === "none"} onClick={() => setMaterial("none")} icon="sources" title="No — find the material for me"
                  text={sugg && !sugg.ai_available ? "Needs an AI service (not configured here)." : "ThinkFirst builds the roadmap from openly licensed sources (with citations). Only your topic text is used to search."} />
              </div>
              {material === "files" && (
                <div className="fade-in game-card space-y-4 p-5">
                  <div>
                    <p className="font-semibold">Files</p>
                    <p className="mt-1 text-meta text-ink-muted" id="limits">
                      {limits ? `PDF (with text), Word .docx, PowerPoint .pptx, TXT, MD · up to ${maxMb} MB per file · ${limits.max_files_per_batch} files at a time · ${limits.max_pages_per_file} pages per file.` : "Loading limits…"}
                    </p>
                    <input id="files" type="file" multiple accept={ACCEPT} className="sr-only" aria-describedby="limits"
                      onChange={(e) => e.target.files && addFiles(e.target.files)} />
                    <label htmlFor="files" className="btn-secondary mt-3 cursor-pointer">Choose files</label>
                    {files.length > 0 && (
                      <ul className="mt-3 space-y-2" aria-label="Selected files">
                        {files.map((f, i) => (
                          <li key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-detail border border-border px-3 py-2">
                            <span className="break-all">{f.name} <span className="text-meta text-ink-muted">· {(f.size / 1024).toFixed(0)} KB{f.size > maxBytes ? <strong className="text-review"> · too large (max {maxMb} MB)</strong> : ""}</span></span>
                            <button type="button" className="btn-link" onClick={() => setFiles(files.filter((_, j) => j !== i))}>Remove<span className="sr-only"> {f.name}</span></button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <DemoCourseButton onFile={(f) => addFiles([f])} />
                  <div>
                    <label htmlFor="paste" className="label">Or paste text (optional)</label>
                    <textarea id="paste" className="field min-h-[120px]" value={paste} onChange={(e) => setPaste(e.target.value)} />
                  </div>
                  <label className="flex items-start gap-3">
                    <input type="checkbox" className="mt-1 h-5 w-5" checked={rights} onChange={(e) => setRights(e.target.checked)} />
                    <span>I may use these materials for my own study. They stay private to me and are never shared or used for training.</span>
                  </label>
                </div>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <h1 ref={headRef} tabIndex={-1} className="text-page-compact md:text-page">Do you already know something about “{topic.trim()}”?</h1>
              <div className="grid gap-4">
                <Choice pressed={prior === "some"} onClick={() => setPrior("some")} icon="levelTest" title="Yes — test my level"
                  text="A short adaptive multiple-choice test (5–12 questions, ~5 min). We find what you already know, your level and your gaps." />
                <Choice pressed={prior === "none"} onClick={() => setPrior("none")} icon="scratch" title="No — start from scratch"
                  text="You are treated as a full beginner: every term explained, step by step, nothing assumed." />
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <h1 ref={headRef} tabIndex={-1} className="text-page-compact md:text-page">Your plan</h1>
              <ol className="space-y-3">
                {[
                  [goal === "exam" ? "exam" : "explore", goal === "exam" ? `Exam preparation${examDate ? ` · exam on ${examDate}` : ""}` : "Learning something new"],
                  ["topic", topic.trim()],
                  [material === "files" ? "course" : "sources", material === "files" ? `Your material: ${files.length} file(s)${paste.trim() ? " + pasted text" : ""}` : "No files — open sources with citations"],
                  [prior === "some" ? "levelTest" : "scratch", prior === "some" ? "Level test first, then everything adapts to your level" : "Start from scratch as a beginner"],
                ].map(([i, t]) => (
                  <li key={t} className="game-card flex items-center gap-3 p-4"><span aria-hidden className="flex h-11 w-11 shrink-0 items-center justify-center rounded-card border-2 border-ink bg-soft"><Illo name={i as IlloName} size={32} /></span><span className="font-semibold">{t}</span></li>
                ))}
              </ol>
              <p className="text-ink-muted">Next: ThinkFirst builds your roadmap → {prior === "some" ? "you take the level test → " : ""}you get a course summary written for your level → you start learning.</p>
            </>
          )}
        </section>

        <div className="mt-8 flex flex-wrap gap-3">
          {step < STEPS.length - 1 ? (
            <button type="button" className="btn-primary" onClick={next} disabled={!canNext}>Continue</button>
          ) : (
            <button type="button" className="btn-primary" onClick={submit} disabled={busy} aria-busy={busy}>{busy ? "Building…" : "Build my learning path"}</button>
          )}
          <button type="button" className="btn-secondary" onClick={() => router.back()}>Cancel</button>
        </div>
        {step === 2 && material === "files" && tooBig.length > 0 && (
          <p role="alert" className="mt-2 text-review">{tooBig.map((f) => f.name).join(", ")} {tooBig.length > 1 ? "are" : "is"} larger than {maxMb} MB. Remove it, split the PDF, or paste the chapters you need.</p>
        )}
        {step === 2 && material === "files" && !rights && <p className="mt-2 text-meta text-ink-muted">Confirm the study-use statement to continue.</p>}
      </div>
    </AppShell>
  );
}
