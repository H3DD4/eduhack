"use client";
/* Declare → probe → reconcile. The probe never shows right/wrong: it measures, it does not teach. */
import { useRef, useState } from "react";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { TeacherAvatar } from "@/components/avatar/TeacherAvatar";
import { ApiError } from "@/lib/api";
import { LEVEL_LABEL, tutor, type Level, type LevelResult } from "@/lib/tutor";
import { Tex } from "./Tex";

const LEVELS: { id: Level; blurb: string }[] = [
  { id: "beginner", blurb: "I am discovering this subject or I have big gaps." },
  { id: "intermediate", blurb: "I followed the course but I am not sure about everything." },
  { id: "advanced", blurb: "I master most of it and want exam-level practice." },
];

const VERDICT: Record<LevelResult["verdict"], string> = {
  confirmed: "Your answers confirm the level you chose.",
  higher: "You know more than you thought: we start higher.",
  lower: "We will start a little lower to build solid foundations.",
  unverified: "We use the level you chose; it will adjust as you practise.",
};

export function LevelCheck({ trackId, chapters, onDone }: { trackId: string; chapters: string[]; onDone: (r: LevelResult) => void }) {
  const [level, setLevel] = useState<Level | null>(null);
  const [item, setItem] = useState<any>(null);
  const [progress, setProgress] = useState({ answered: 0, max: 10 });
  const [result, setResult] = useState<LevelResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const shown = useRef(Date.now());

  const start = async (skip: boolean) => {
    if (!level) return;
    setBusy(true); setErr(null);
    try {
      const r = await tutor.declare(trackId, level, skip);
      if (r.result) setResult(r.result);
      else { setItem(r.item); setProgress(r.item?.progress || progress); shown.current = Date.now(); }
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };

  const answer = async (choice: number) => {
    setBusy(true);
    try {
      const r = await tutor.probeAnswer(trackId, item.id, choice, Date.now() - shown.current);
      setProgress(r.progress);
      if (r.result) { setResult(r.result); setItem(null); }
      else { setItem(r.item); shown.current = Date.now(); }
    } catch (e) { setErr((e as ApiError).message); } finally { setBusy(false); }
  };

  if (result) {
    const resultScript = `Your measured level is ${LEVEL_LABEL[result.measured]}. ${VERDICT[result.verdict]}`;
    return (
      <section className="hero space-y-4 p-7" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="badge">Level check</span>
          <SpeakButton text={resultScript} title="Level check result" label="Speak verdict" />
        </div>
        <h2 className="text-page">Your level: <span className="hl">{LEVEL_LABEL[result.measured]}</span></h2>
        <p className="text-problem">{VERDICT[result.verdict]}</p>
        <TeacherAvatar text={resultScript} title="Level Check Coach" compact stageHeight={220} />
        {Object.keys(result.level_by_chapter).length > 0 && (
          <ul className="grid gap-2 sm:grid-cols-2">
            {Object.entries(result.level_by_chapter).map(([ch, l]) => (
              <li key={ch} className="flex items-center justify-between rounded-control border-2 border-ink bg-surface px-3 py-2">
                <span>{ch}</span><span className="pill">{LEVEL_LABEL[l]}</span>
              </li>
            ))}
          </ul>
        )}
        {result.rapid_guesses > 0 && <p className="text-meta">{result.rapid_guesses} very fast answer(s) were not counted.</p>}
        <button className="btn-primary" onClick={() => onDone(result)}>Continue</button>
      </section>
    );
  }

  if (item) {
    return (
      <section className="game-card space-y-4 p-6">
        <div className="flex items-center gap-3 text-meta">
          <div className="bar flex-1"><span style={{ width: `${(progress.answered / progress.max) * 100}%` }} /></div>
          <span>{progress.answered}/{progress.max}</span>
        </div>
        <div className="flex items-start justify-between gap-2">
          <p className="text-problem"><Tex text={item.stem} /></p>
          <SpeakButton text={item.stem} title="Level check question" label="Speak" />
        </div>
        <div className="grid gap-2">
          {item.options.map((o: any, i: number) => (
            <button key={i} className="option text-left" disabled={busy} onClick={() => answer(i)}>
              <span className="mr-2 font-mono">{String.fromCharCode(65 + i)}.</span><Tex text={o.text} />
            </button>
          ))}
        </div>
        <p className="text-meta text-ink-muted">No feedback during the check. Unsure? Pick your best guess; take your time.</p>
        {err && <p className="rounded-control bg-review-surface p-2">{err}</p>}
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-section">How well do you know this subject?</h2>
        <p className="text-ink-muted">Choose honestly; a short check of {chapters.length ? "your chapters" : "the course"} then confirms it.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3" role="radiogroup">
        {LEVELS.map((l) => (
          <button key={l.id} role="radio" aria-checked={level === l.id} className="option p-5 text-left" onClick={() => setLevel(l.id)}>
            <span className="block text-problem font-semibold">{LEVEL_LABEL[l.id]}</span>
            <span className="text-meta">{l.blurb}</span>
          </button>
        ))}
      </div>
      {err && <p className="rounded-control bg-review-surface p-2">{err}</p>}
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" disabled={!level || busy} onClick={() => start(false)}>Start the 3-minute check</button>
        <button className="btn-link" disabled={!level || busy} onClick={() => start(true)}>Skip the check</button>
      </div>
    </section>
  );
}
