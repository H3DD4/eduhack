"use client";
// A02 Onboarding — one question per screen, under 3 minutes, safe defaults on every step.
// "Skip the rest and continue" saves immediately with what is answered (essential tier only), as before.
// Payload to PATCH /me/onboarding is unchanged.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";

type Choice = { v: string; t: string; d?: string };
const GOALS: Choice[] = [
  { v: "understand", t: "Understand my course" },
  { v: "exam", t: "Prepare for an exam" },
  { v: "self_study", t: "Learn a topic on my own" },
  { v: "unsure", t: "Not sure yet" },
];
const LEVELS: Choice[] = [
  { v: "high_school", t: "High school / Bac" },
  { v: "university", t: "University or engineering" },
  { v: "professional", t: "Self-learner or certification" },
];
const CONFIDENCE: Choice[] = [
  { v: "1", t: "Lost" }, { v: "2", t: "A bit rusty" }, { v: "3", t: "Okay" }, { v: "4", t: "Confident" }, { v: "5", t: "Very confident" },
];
const SLOTS: Choice[] = [
  { v: "Today at 18:00", t: "Today at 18:00" },
  { v: "Tomorrow at 18:00", t: "Tomorrow at 18:00" },
  { v: "Saturday morning", t: "Saturday morning" },
  { v: "I will choose later", t: "I'll choose later" },
];
const INPUTS: Choice[] = [
  { v: "text", t: "Typing" },
  { v: "voice", t: "Speaking", d: "You choose when the microphone is on." },
];

const STEPS = ["goal", "level", "confidence", "slot", "input", "privacy", "deal"] as const;
const SECONDS_LEFT = [150, 125, 100, 80, 60, 40, 15];

function Options({ name, options, value, onPick }: { name: string; options: Choice[]; value: string; onPick: (v: string) => void }) {
  return (
    <div role="radiogroup" aria-label={name} className="mt-6 space-y-3">
      {options.map((o, i) => (
        <button key={o.v} type="button" role="radio" aria-checked={value === o.v} className="option justify-between text-problem" onClick={() => onPick(o.v)}>
          <span>
            <span className="mr-3 text-meta text-ink-muted" aria-hidden>{i + 1}</span>{o.t}
            {o.d && <span className="block text-meta text-ink-muted">{o.d}</span>}
          </span>
          <span aria-hidden className={`h-5 w-5 shrink-0 rounded-pill border-2 border-ink ${value === o.v ? "bg-ink" : "bg-surface"}`} />
        </button>
      ))}
    </div>
  );
}

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [goal, setGoal] = useState("unsure");
  const [level, setLevel] = useState("university");
  const [birthYear, setBirthYear] = useState<string>("");
  const [dealAccepted, setDealAccepted] = useState(true);
  const [behaviorTier, setBehaviorTier] = useState(false);
  const [priorConfidence, setPriorConfidence] = useState<number>(3);
  const [firstSessionSlot, setFirstSessionSlot] = useState("Tomorrow at 18:00");
  const [input, setInput] = useState("text");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const key = STEPS[step];
  const last = step === STEPS.length - 1;

  const save = async () => {
    setBusy(true);
    setError(null);
    const parsedYear = birthYear.trim() ? Number(birthYear.trim()) : null;
    try {
      await api("/me/onboarding", {
        method: "PATCH",
        json: {
          goal, level, input_preference: input,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          birth_year: parsedYear, deal_accepted: dealAccepted, prior_confidence: priorConfidence,
          first_session_slot: firstSessionSlot,
          grant_tiers: behaviorTier ? ["essential", "learning_behavior"] : ["essential"],
        },
      });
      router.replace("/subjects");
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };
  const next = () => (last ? save() : setStep((s) => Math.min(STEPS.length - 1, s + 1)));
  const back = () => setStep((s) => Math.max(0, s - 1));

  // Number keys pick an option on choice screens; Enter moves on.
  useEffect(() => {
    const map: Record<string, { opts: Choice[]; set: (v: string) => void }> = {
      goal: { opts: GOALS, set: setGoal }, level: { opts: LEVELS, set: setLevel },
      confidence: { opts: CONFIDENCE, set: (v) => setPriorConfidence(Number(v)) },
      slot: { opts: SLOTS, set: setFirstSessionSlot }, input: { opts: INPUTS, set: setInput },
    };
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && ["INPUT", "TEXTAREA"].includes(t.tagName)) return;
      const m = map[key];
      const n = Number(e.key);
      if (m && n >= 1 && n <= m.opts.length) m.set(m.opts[n - 1].v);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [key]);

  return (
    <AppShell focused requireSetup={false}>
      <div className="mx-auto flex min-h-screen max-w-form flex-col px-4 py-6" data-screen="A02">
        <div className="flex items-center justify-between gap-3">
          <button type="button" className="btn-secondary !min-h-[44px] !px-3" onClick={back} disabled={step === 0} aria-label="Back">
            <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" /></svg>
          </button>
          <Logo size={30} />
          <span className="text-meta text-ink-muted" aria-live="polite">About {SECONDS_LEFT[step]} s left</span>
        </div>
        <div className="bar mt-5" role="progressbar" aria-label="Setup progress" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1}>
          <span style={{ width: `${Math.round(((step + 1) / STEPS.length) * 100)}%` }} />
        </div>

        <form className="step-in mt-8 flex flex-1 flex-col" key={key} onSubmit={(e) => { e.preventDefault(); next(); }}>
          <p className="text-meta text-ink-muted">Question {step + 1} of {STEPS.length}</p>

          {key === "goal" && (<>
            <h1 className="mt-2 text-page-compact">What brings you <span className="hl">here</span>?</h1>
            <p className="mt-2 text-ink-muted">This sets how long your first check is.</p>
            <Options name="Goal" options={GOALS} value={goal} onPick={setGoal} />
          </>)}
          {key === "level" && (<>
            <h1 className="mt-2 text-page-compact">Where are you <span className="hl">studying</span>?</h1>
            <p className="mt-2 text-ink-muted">So the first question is the right level.</p>
            <Options name="Level" options={LEVELS} value={level} onPick={setLevel} />
          </>)}
          {key === "confidence" && (<>
            <h1 className="mt-2 text-page-compact">How <span className="hl">sure</span> do you feel about your subject?</h1>
            <p className="mt-2 text-ink-muted">No wrong answer. We compare it with your results later.</p>
            <Options name="Starting confidence" options={CONFIDENCE} value={String(priorConfidence)} onPick={(v) => setPriorConfidence(Number(v))} />
          </>)}
          {key === "slot" && (<>
            <h1 className="mt-2 text-page-compact">When is your <span className="hl">first session</span>?</h1>
            <p className="mt-2 text-ink-muted">People who pick a time are more likely to show up.</p>
            <Options name="First session" options={SLOTS} value={firstSessionSlot} onPick={setFirstSessionSlot} />
            <label className="label mt-5" htmlFor="onb-slot">Or type your own time</label>
            <input id="onb-slot" className="field" value={firstSessionSlot} onChange={(e) => setFirstSessionSlot(e.target.value)} />
          </>)}
          {key === "input" && (<>
            <h1 className="mt-2 text-page-compact">How do you like to <span className="hl">answer</span>?</h1>
            <p className="mt-2 text-ink-muted">You can switch at any time.</p>
            <Options name="Answer with" options={INPUTS} value={input} onPick={setInput} />
          </>)}
          {key === "privacy" && (<>
            <h1 className="mt-2 text-page-compact">What can we use to <span className="hl">adapt</span>?</h1>
            <p className="mt-2 text-ink-muted">You can change this any time in Settings.</p>
            <div className="mt-6 space-y-3">
              <div className="card !p-4">
                <p className="flex items-center justify-between gap-3">Essential <span className="badge">Always on</span></p>
                <p className="mt-1 text-meta text-ink-muted">Answers, help used and time per question. Needed for ThinkFirst to work.</p>
              </div>
              <button type="button" role="switch" aria-checked={behaviorTier} className="option !items-start flex-col" onClick={() => setBehaviorTier((b) => !b)}>
                <span className="flex w-full items-center justify-between gap-3">Learning behavior
                  <span aria-hidden className={`flex h-7 w-12 items-center rounded-pill border-2 border-ink px-0.5 transition-colors ${behaviorTier ? "justify-end bg-strong" : "justify-start bg-surface"}`}><span className="h-5 w-5 rounded-pill bg-ink" /></span>
                </span>
                <span className="text-meta text-ink-muted">Pauses, edits and rhythm, so pacing adapts to you. Optional.</span>
              </button>
              <div>
                <label className="label" htmlFor="onb-birth-year">Birth year (optional)</label>
                <input id="onb-birth-year" type="number" inputMode="numeric" placeholder="e.g. 2007" className="field" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} />
                <p className="mt-1 text-meta text-ink-muted">Under 18? We ask a guardian before saving more than your account.</p>
              </div>
            </div>
          </>)}
          {key === "deal" && (<>
            <h1 className="mt-2 text-page-compact">One last thing: <span className="hl">the deal</span></h1>
            <div className="hero mt-6 p-6">
              <p className="relative z-10 text-section">“I won&apos;t give you answers. I&apos;ll make you better at finding them.”</p>
              <p className="relative z-10 mt-2">Try first, then help comes one step at a time.</p>
            </div>
            <label className="option mt-5">
              <input type="checkbox" checked={dealAccepted} onChange={(e) => setDealAccepted(e.target.checked)} />
              <span>I&apos;m in</span>
            </label>
          </>)}

          {error && <p role="alert" className="mt-4 text-review">{error} <button type="button" className="btn-link" onClick={save}>Retry</button></p>}

          <div className="mt-auto space-y-3 pt-8">
            <button type="submit" className="btn-primary w-full" disabled={busy} aria-busy={busy}>
              {last ? (busy ? "Saving…" : "Save and start") : "Next"}
            </button>
            {!last && <button type="button" className="btn-link w-full justify-center" onClick={save} disabled={busy}>Skip the rest and continue</button>}
          </div>
        </form>
      </div>
    </AppShell>
  );
}
