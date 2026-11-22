"use client";
/* One practice item (QCM, quiz, exercise) with the ThinkFirst help ladder:
   attempt first → 1 nudge → 2 hint to the course → 3 similar example → 4 full solution.
   In a mock exam (`mode="mock"`) it only collects the answer: no checking, no help. */
import { useRef, useState } from "react";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { ApiError } from "@/lib/api";
import { tutor, type AttemptResult, type HelpResult, type Item } from "@/lib/tutor";
import { Citations, LikenessBadge } from "./bits";
import { Md, Tex } from "./Tex";

const LADDER = [
  { level: 1, label: "Nudge me" },
  { level: 2, label: "Hint from my course" },
  { level: 3, label: "Show a similar example" },
  { level: 4, label: "Show the solution" },
];

export function ItemPlayer({ trackId, item, mode = "practice", index, value, onChange, onDone }: {
  trackId: string; item: Item; mode?: "practice" | "lesson" | "mock"; index?: number;
  value?: any; onChange?: (v: any) => void; onDone?: (r: AttemptResult) => void;
}) {
  const [answer, setAnswer] = useState<any>(value ?? (item.kind === "qcm" ? (item.multiple ? [] : null) : item.kind === "exercise" ? {} : ""));
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [help, setHelp] = useState<HelpResult[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tries, setTries] = useState(0);
  const started = useRef(Date.now());
  const maxHelp = help.reduce((m, h) => Math.max(m, h.level), 0);
  const mock = mode === "mock";

  const set = (v: any) => { setAnswer(v); onChange?.(v); };

  const check = async () => {
    setBusy(true); setNotice(null);
    try {
      const r = await tutor.attempt(trackId, item.id, answer, Date.now() - started.current, maxHelp);
      setResult(r); setTries((t) => t + 1);
      onDone?.(r);
    } catch (e) {
      setNotice((e as ApiError).message);
    } finally { setBusy(false); }
  };

  const askHelp = async (level: number) => {
    setBusy(true); setNotice(null);
    try {
      const h = await tutor.help(trackId, item.id, level);
      setHelp((x) => [...x, h]);
    } catch (e) {
      setNotice((e as ApiError).message);   // e.g. "Try an answer first, even a partial one."
    } finally { setBusy(false); }
  };

  const retry = () => { setResult(null); started.current = Date.now(); };
  const empty = answer == null || (Array.isArray(answer) && !answer.length) || answer === "" ||
    (item.kind === "exercise" && !Object.values(answer || {}).some((v) => String(v).trim()));

  return (
    <article className="game-card space-y-4 p-5" aria-labelledby={`q-${item.id}`}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <span className="badge">{index != null ? `Q${index + 1} · ` : ""}{item.kind === "qcm" ? (item.multiple ? "Several answers" : "One answer") : item.kind === "quiz" ? "Short answer" : "Exercise"}</span>
        <div className="flex items-center gap-2">
          {item.points != null && <span className="pill">{item.points} pt</span>}
          {!mock && <LikenessBadge value={item.likeness} />}
          {!mock && (
            <SpeakButton
              text={
                item.kind === "qcm"
                  ? `${item.stem}. Options: ${item.options.map((o, idx) => `${String.fromCharCode(65 + idx)}: ${o.text}`).join(". ")}`
                  : item.kind === "quiz"
                  ? item.question
                  : `${item.title}. ${item.statement}. ${item.parts.map((p) => `${p.label} ${p.prompt}`).join(". ")}`
              }
              title={item.kind === "exercise" ? item.title : `Question ${index != null ? index + 1 : ""}`}
              hint={item.kind === "exercise" ? item.concept_keys?.[0] : item.concept_key}
              label="Speak"
            />
          )}
        </div>
      </header>

      {item.kind === "qcm" && (
        <>
          <p id={`q-${item.id}`} className="text-problem"><Tex text={item.stem} /></p>
          <div role={item.multiple ? "group" : "radiogroup"} className="grid gap-2">
            {item.options.map((o, i) => {
              const on = item.multiple ? (answer as number[]).includes(i) : answer === i;
              const sol = result?.solution?.correct as number[] | undefined;
              const mark = sol ? (sol.includes(i) ? "border-success bg-success-surface" : on ? "bg-review-surface" : "") : "";
              return (
                <button key={i} type="button" role={item.multiple ? "checkbox" : "radio"} aria-checked={on} disabled={!!result && !mock}
                  className={`option text-left ${mark}`}
                  onClick={() => set(item.multiple ? (on ? (answer as number[]).filter((x) => x !== i) : [...answer, i]) : i)}>
                  <span className="mr-2 font-mono">{String.fromCharCode(65 + i)}.</span><Tex text={o.text} />
                  {sol && result?.solution?.why?.[i] && (on || sol.includes(i)) && <span className="mt-1 block text-meta text-ink-muted">{result.solution.why[i]}</span>}
                </button>
              );
            })}
          </div>
        </>
      )}

      {item.kind === "quiz" && (
        <>
          <p id={`q-${item.id}`} className="text-problem"><Tex text={item.question} /></p>
          {item.answer_type === "true_false" ? (
            <div className="flex gap-2" role="radiogroup">
              {[["true", "True / Vrai"], ["false", "False / Faux"]].map(([v, l]) => (
                <button key={v} type="button" role="radio" aria-checked={answer === v} className="option" disabled={!!result && !mock} onClick={() => set(v)}>{l}</button>
              ))}
            </div>
          ) : (
            <input className="field w-full" value={answer} disabled={!!result && !mock} onChange={(e) => set(e.target.value)}
              placeholder={item.answer_type === "number" ? "Your number (2,5 or 2.5)" : item.answer_type === "expression" ? "Your expression, e.g. 3x^2 - 2" : "Your answer"}
              onKeyDown={(e) => { if (e.key === "Enter" && !mock && !empty) check(); }} />
          )}
        </>
      )}

      {item.kind === "exercise" && (
        <>
          <h3 id={`q-${item.id}`} className="text-problem font-semibold">{item.title}</h3>
          <Md text={item.statement} />
          <ol className="space-y-3">
            {item.parts.map((p) => (
              <li key={p.label} className="space-y-1">
                <label className="label" htmlFor={`${item.id}-${p.label}`}><span className="font-mono">{p.label}</span> <Tex text={p.prompt} /> <span className="text-meta text-ink-muted">({p.points} pt)</span></label>
                <textarea id={`${item.id}-${p.label}`} className="field min-h-[72px] w-full" value={answer?.[p.label] || ""} disabled={!!result && !mock}
                  onChange={(e) => set({ ...answer, [p.label]: e.target.value })} />
              </li>
            ))}
          </ol>
        </>
      )}

      {!mock && (
        <>
          {help.map((h, i) => (
            <div key={i} className="hint-in rounded-control border-2 border-ink bg-help-surface p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-meta font-semibold">{LADDER[h.level - 1].label}</p>
                <SpeakButton text={h.message} title={LADDER[h.level - 1].label} label="Speak hint" />
              </div>
              <Md text={h.message} />
              <Citations items={h.citations} />
            </div>
          ))}
          {notice && <p role="status" className="rounded-control bg-review-surface p-3">{notice}</p>}

          {result && (
            <div className={`fade-in rounded-control border-2 border-ink p-3 ${result.correct ? "bg-success-surface" : "bg-review-surface"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold">{result.correct ? "Correct" : result.score > 0 ? `Partly right (${Math.round(result.score * 100)}%)` : "Not yet"}</p>
                <SpeakButton
                  text={`${result.correct ? "Correct." : "Not yet."} ${result.feedback || ""} ${result.solution?.explanation || ""}`}
                  title="Assessment feedback"
                  label="Speak feedback"
                />
              </div>
              {result.feedback && <Md text={result.feedback} />}
              {result.solution?.explanation && <Md text={result.solution.explanation} />}
              {result.solution?.answer && <p>Answer: <Tex text={String(result.solution.answer)} /></p>}
              {result.solution?.parts?.map((p: any) => (
                <div key={p.label} className="mt-2"><span className="font-mono">{p.label}</span> <Tex text={p.answer || ""} />
                  {p.steps?.length > 0 && <ol className="ml-6 list-decimal">{p.steps.map((s: string, i: number) => <li key={i}><Tex text={s} /></li>)}</ol>}
                </div>
              ))}
              <Citations items={result.solution?.citations} />
              {result.mastery && (
                <div className="mt-2 flex items-center gap-2 text-meta">
                  <span>Mastery</span>
                  <div className="bar w-40"><span style={{ width: `${Math.round(result.mastery.p_mastery * 100)}%` }} /></div>
                  <span>{Math.round(result.mastery.p_mastery * 100)}%{result.mastery.mastered ? " · mastered" : ` · review ${result.mastery.next_review}`}</span>
                </div>
              )}
            </div>
          )}

          <footer className="flex flex-wrap items-center gap-2">
            {!result && <button className="btn-primary" disabled={busy || empty} onClick={check}>Check my answer</button>}
            {result && !result.correct && <button className="btn-primary" onClick={retry}>Try again</button>}
            {!result?.correct && LADDER.map((l) => (
              <button key={l.level} className="btn-help" disabled={busy || l.level > maxHelp + 1 || (l.level >= 2 && tries === 0)}
                title={l.level >= 2 && tries === 0 ? "Try an answer first" : undefined} onClick={() => askHelp(l.level)}>
                {l.label}
              </button>
            ))}
          </footer>
        </>
      )}
    </article>
  );
}
