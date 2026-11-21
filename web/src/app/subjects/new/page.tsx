"use client";
// C01 Create subject — UC03/UC05. Limits shown before selection; rights/privacy acknowledged; per-file rows.
import { useRouter } from "next/navigation";
import { FormEvent, useRef, useState } from "react";
import { AppShell, useMe } from "@/components/AppShell";
import { TopicLauncher } from "@/components/TopicLauncher";
import { DemoLabel, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function DemoFileButton({ onFile }: { onFile: (f: File) => void }) {
  const { me } = useMe();
  if (!me?.is_demo) return null;
  return (
    <div className="card mt-4 border-discovery">
      <DemoLabel />
      <p className="mt-2 text-meta">A permission-cleared demo course (MATH 101 — Algebra Foundations) is available for the demo account.</p>
      <button type="button" className="btn-secondary mt-3" onClick={async () => {
        const blob = await api<Blob>("/demo/course-file");
        onFile(new File([blob], "MATH101-algebra-foundations-DEMO.pdf", { type: "application/pdf" }));
      }}>Use the demo course file</button>
    </div>
  );
}

export default function CreateSubject() {
  const router = useRouter();
  const { data: limits } = useApi<any>("/limits");
  const [mode, setMode] = useState<"upload" | "topic">("upload");
  const [name, setName] = useState("");
  const [role, setRole] = useState("course");
  const [files, setFiles] = useState<File[]>([]);
  const [paste, setPaste] = useState("");
  const [rights, setRights] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const maxMb = limits ? Math.round(limits.max_file_bytes / 1048576) : 20;

  const addFiles = (list: FileList | File[]) => {
    const arr = Array.from(list);
    setFiles((f) => [...f, ...arr].slice(0, limits?.max_files_per_batch ?? 5));
    if (!name && arr[0]) setName(arr[0].name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "topic") {
        const r = await api("/subjects/guided", { method: "POST", json: { name: name || "Algebra foundations (guided)", discipline: "algebra" } });
        router.push(`/subjects/${r.subject.id}/setup`);
        return;
      }
      const fd = new FormData();
      fd.set("name", name);
      fd.set("role", role);
      fd.set("rights_ack", String(rights));
      fd.set("paste_text", paste);
      files.forEach((f) => fd.append("files", f));
      const r = await api("/subjects", { method: "POST", body: fd, retries: 0 });
      router.push(`/subjects/${r.subject.id}/setup`);
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <AppShell crumbs={[{ href: "/subjects", label: "Subjects" }, { label: "New subject" }]}>
      <section className="hero mb-8 p-6 md:p-10" aria-labelledby="learn-h">
        <div className="relative z-10 max-w-3xl">
          <h1 id="learn-h" className="text-page-compact md:text-page">What do you want to learn?</h1>
          <p className="muted mt-2">No files needed — type a topic and start right away.</p>
          <div className="mt-5"><TopicLauncher dark autoFocus /></div>
        </div>
      </section>
      <form onSubmit={submit} className="game-card max-w-prose space-y-6 p-6" data-screen="C01">
        <h2 className="text-section">Or build it from your own course files</h2>
        {error && <ErrorBox message={error} />}
        <fieldset className="flex flex-wrap gap-2">
          <legend className="label">How do you want to start?</legend>
          {[["upload", "Upload or paste course material"], ["topic", "I'm unsure — guided topic"]].map(([v, t]) => (
            <label key={v} className={`flex min-h-[48px] items-center gap-2 rounded-control border-2 px-4 ${mode === v ? "border-action bg-success-surface" : "border-stroke bg-surface"}`}>
              <input type="radio" name="mode" checked={mode === v} onChange={() => setMode(v as any)} /> {t}
            </label>
          ))}
        </fieldset>
        <div>
          <label htmlFor="name" className="label">Subject name</label>
          <input id="name" className="field" value={name} onChange={(e) => setName(e.target.value)} required={mode === "upload"} />
        </div>
        {mode === "upload" ? (
          <>
            <fieldset>
              <legend className="label">What are these files?</legend>
              <div className="flex flex-wrap gap-2">
                {[["course", "Course"], ["notes", "Notes"], ["past_exam", "Past exam"]].map(([v, t]) => (
                  <label key={v} className="flex min-h-[44px] items-center gap-2 rounded-control border-2 border-stroke bg-surface px-3">
                    <input type="radio" name="role" checked={role === v} onChange={() => setRole(v)} /> {t}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="card">
              <p className="font-semibold">Files</p>
              <p className="mt-1 text-meta text-ink-muted" id="limits">
                {limits ? `Text PDF, PPTX, TXT, MD · up to ${maxMb} MB per file · ${limits.max_files_per_batch} files at a time · ${limits.max_pages_per_file} pages per file. Scanned PDFs/photos (OCR) arrive later.` : "Loading limits…"}
              </p>
              <input ref={inputRef} id="files" type="file" multiple accept=".pdf,.pptx,.txt,.md" className="sr-only" aria-describedby="limits"
                onChange={(e) => e.target.files && addFiles(e.target.files)} />
              <label htmlFor="files" className="btn-secondary mt-3 cursor-pointer">Choose files</label>
              {files.length > 0 && (
                <ul className="mt-3 space-y-2" aria-label="Selected files">
                  {files.map((f, i) => (
                    <li key={i} className="flex flex-wrap items-center justify-between gap-2 rounded-detail border border-border px-3 py-2">
                      <span>{f.name} <span className="text-meta text-ink-muted">· {(f.size / 1024).toFixed(0)} KB{f.size > (limits?.max_file_bytes ?? Infinity) ? " · too large" : ""}</span></span>
                      <button type="button" className="btn-link" onClick={() => setFiles(files.filter((_, j) => j !== i))}>Remove<span className="sr-only"> {f.name}</span></button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <DemoFileButton onFile={(f) => addFiles([f])} />
            <div>
              <label htmlFor="paste" className="label">Or paste notes (optional)</label>
              <textarea id="paste" className="field" value={paste} onChange={(e) => setPaste(e.target.value)} />
            </div>
            <label className="flex items-start gap-3">
              <input type="checkbox" className="mt-1 h-5 w-5" checked={rights} onChange={(e) => setRights(e.target.checked)} />
              <span>I may use these materials for my own study. They stay private to me and are never shared or used for training.</span>
            </label>
          </>
        ) : (
          <div className="card">
            <p>Start without a file: ThinkFirst proposes a starter scope you confirm. It is labeled <strong>AI-generated</strong>, never “extracted from your course”.</p>
            <p className="mt-2 text-meta text-ink-muted">Available guided topic in this build: Algebra foundations (Demo data).</p>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" disabled={busy || (mode === "upload" && (!rights || (!files.length && !paste.trim())))} aria-busy={busy}>
            {busy ? "Creating…" : "Create subject"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => router.back()}>Cancel</button>
        </div>
        {mode === "upload" && !rights && <p className="text-meta text-ink-muted">Confirm the study-use statement to create the subject.</p>}
      </form>
    </AppShell>
  );
}
