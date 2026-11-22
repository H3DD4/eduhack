"use client";
// New track: pick the valley, describe the goal, then continue on the track page (upload → prepare → level → build).
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ApiError } from "@/lib/api";
import { tutor, type Valley } from "@/lib/tutor";

function NewTrackForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [valley, setValley] = useState<Valley>((params.get("valley") as Valley) || "revision");
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState("");
  const [goal, setGoal] = useState("");
  const [examDate, setExamDate] = useState("");
  const [chapters, setChapters] = useState("");
  const [allowWeb, setAllowWeb] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const t = await tutor.create({
        valley, title: title.trim(), subject: subject.trim(), goal: goal.trim(), allow_web: allowWeb,
        exam_date: valley === "revision" && examDate ? examDate : null,
        chapters: chapters.split(/[\n,;]/).map((c) => c.trim()).filter(Boolean),
      });
      router.push(`/tutor/${t.id}`);
    } catch (e) { setErr((e as ApiError).message); setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="mx-auto max-w-form space-y-6" data-screen="TUTOR-NEW">
      <h1 className="text-page-compact">New track</h1>
      <fieldset className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Valley">
        {([["revision", "Revise for an exam", "Material shaped like your past exams"], ["skills", "Learn a skill", "Progressive tutorial, page by page"]] as const).map(([v, t, d]) => (
          <button key={v} type="button" role="radio" aria-checked={valley === v} className="option p-4 text-left" onClick={() => setValley(v)}>
            <span className="block font-semibold">{t}</span><span className="text-meta">{d}</span>
          </button>
        ))}
      </fieldset>
      <div>
        <label className="label" htmlFor="title">Title</label>
        <input id="title" required className="field w-full" value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder={valley === "revision" ? "Maths — DS n°3 Dérivation" : "Python basics"} />
      </div>
      <div>
        <label className="label" htmlFor="subject">Subject</label>
        <input id="subject" className="field w-full" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Mathématiques" />
      </div>
      {valley === "revision" ? (
        <>
          <div>
            <label className="label" htmlFor="date">Exam date</label>
            <input id="date" type="date" className="field w-full" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="ch">Chapters on the exam <span className="text-meta text-ink-muted">(optional, one per line)</span></label>
            <textarea id="ch" className="field min-h-[80px] w-full" value={chapters} onChange={(e) => setChapters(e.target.value)} />
          </div>
        </>
      ) : (
        <div>
          <label className="label" htmlFor="goal">What do you want to be able to do?</label>
          <textarea id="goal" className="field min-h-[80px] w-full" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Write small Python scripts that read and clean a CSV file" />
        </div>
      )}
      <label className="flex items-start gap-3">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={allowWeb} onChange={(e) => setAllowWeb(e.target.checked)} />
        <span>Fill gaps with trusted web sources <span className="block text-meta text-ink-muted">Only open educational sites; every web passage is labelled with its source and licence.</span></span>
      </label>
      {err && <p className="rounded-control bg-review-surface p-3">{err}</p>}
      <button className="btn-primary" disabled={busy || !title.trim()}>{busy ? "Creating…" : "Continue"}</button>
    </form>
  );
}

export default function NewTrack() {
  return (
    <AppShell crumbs={[{ label: "Tutor", href: "/tutor" }, { label: "New track" }]}>
      <Suspense><NewTrackForm /></Suspense>
    </AppShell>
  );
}
