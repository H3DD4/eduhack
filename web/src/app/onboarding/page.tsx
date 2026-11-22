"use client";
// A02 Onboarding — one question per screen, under 3 minutes, safe defaults on every step.
// "Skip the rest and continue" saves immediately with what is answered (essential tier only), as before.
// Payload to PATCH /me/onboarding is unchanged.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import { useAvatarSpeaker } from "@/components/avatar/AvatarSpeakerContext";

type Choice = { v: string; t: string; d?: string };
const GOALS: Choice[] = [
  { v: "understand", t: "Understand my course" },
  { v: "exam", t: "Prepare for an exam" },
  { v: "self_study", t: "Learn a topic on my own" },
  { v: "unsure", t: "Not sure yet" },
];
const STATUS: Choice[] = [
  { v: "school", t: "School student", d: "Middle school, high school, Bac" },
  { v: "university", t: "University student", d: "Degree, engineering, masters" },
  { v: "working", t: "Working", d: "Learning for my job or a certificate" },
  { v: "self_learner", t: "Learning on my own" },
];
const LEVEL_OF: Record<string, string> = { school: "high_school", university: "university", working: "professional", self_learner: "professional" };
const FIELDS: Record<string, string[]> = {
  school: ["Sciences", "Mathematics", "Computer science", "Economics and management", "Literature and languages"],
  university: ["Computer science", "Engineering", "Medicine and health", "Business and management", "Law", "Mathematics", "Sciences", "Design and arts", "Humanities"],
  working: ["Software and IT", "Cybersecurity", "Data and AI", "Engineering", "Finance and accounting", "Marketing", "Health", "Education", "Design"],
  self_learner: ["Programming", "Data and AI", "Languages", "Business", "Sciences", "Design", "History"],
};
const YEARS: Record<string, string[]> = {
  school: ["Middle school", "1st year high school", "2nd year high school", "Final year / Bac"],
  university: ["1st year", "2nd year", "3rd year", "4th year", "5th year", "Doctorate"],
};
const INTERESTS = ["Programming", "Artificial intelligence", "Cybersecurity", "Mathematics", "Physics", "Biology", "Economics", "Languages", "History", "Design", "Psychology"];
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

const STEPS = ["about", "status", "field", "interests", "goal", "confidence", "slot", "input", "privacy", "deal"] as const;
const SECONDS_LEFT = [170, 150, 135, 110, 95, 80, 65, 50, 35, 15];

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
  const { speakWithAvatar, voiceGuideEnabled } = useAvatarSpeaker();
  const [step, setStep] = useState(0);
  const [goal, setGoal] = useState("unsure");
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [status, setStatus] = useState("");
  const [field, setField] = useState("");
  const [detail, setDetail] = useState(""); // year of study or job title
  const [interests, setInterests] = useState<string[]>([]);
  const [otherInterest, setOtherInterest] = useState("");
  const [hours, setHours] = useState("5");
  const [dealAccepted, setDealAccepted] = useState(true);
  const [behaviorTier, setBehaviorTier] = useState(false);
  const [priorConfidence, setPriorConfidence] = useState<number>(3);
  const [firstSessionSlot, setFirstSessionSlot] = useState("Tomorrow at 18:00");
  const [input, setInput] = useState("text");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const key = STEPS[step];
  const last = step === STEPS.length - 1;

  // Coming back from Settings: start from what was answered before.
  useEffect(() => {
    api("/me/consent").then((r: any) => {
      const c = r.consent ?? r, o = c.onboarding ?? {};
      if (o.status) setStatus(o.status);
      if (o.field) setField(o.field);
      if (o.study_year || o.job_title) setDetail(o.study_year || o.job_title);
      if (o.comfort?.interests?.length) setInterests(o.comfort.interests);
      if (o.rhythm?.hours_per_week) setHours(String(o.rhythm.hours_per_week));
      if (o.goal) setGoal(o.goal);
      if (o.prior_confidence) setPriorConfidence(o.prior_confidence);
      if (c.birth_year) setAge(String(new Date().getFullYear() - c.birth_year));
    }).catch(() => undefined);
    api("/auth/me").then((r: any) => { const n = (r.user ?? r).display_name; if (n) setName(n); }).catch(() => undefined);
  }, []);

  const ageNum = age.trim() ? Number(age.trim()) : null;
  const ageOk = ageNum === null || (Number.isInteger(ageNum) && ageNum >= 5 && ageNum <= 100);
  const missing = key === "about" ? (!name.trim() ? "Tell us what to call you." : ageNum === null ? "Enter your age." : !ageOk ? "Enter an age between 5 and 100." : null)
    : key === "status" ? (!status ? "Choose what describes you." : null)
    : key === "field" ? (!field.trim() ? "Choose or type your speciality." : null) : null;

  const save = async () => {
    setBusy(true);
    setError(null);
    const parsedYear = ageNum !== null && ageOk ? new Date().getFullYear() - ageNum : null;
    const student = status === "school" || status === "university";
    try {
      await api("/me/onboarding", {
        method: "PATCH",
        json: {
          goal, level: LEVEL_OF[status] ?? "university", input_preference: input,
          display_name: name.trim() || null, status: status || null, field: field.trim() || null,
          study_year: student ? detail.trim() : "", job_title: status === "working" ? detail.trim() : "",
          interests, hours_per_week: Number(hours) > 0 && Number(hours) <= 80 ? Number(hours) : null,
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
  const next = () => {
    if (missing) { setError(missing); return; }
    setError(null);
    if (last) save();
    else setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };
  const toggleInterest = (x: string) => setInterests((l) => (l.includes(x) ? l.filter((y) => y !== x) : [...l, x].slice(0, 12)));
  const addOther = () => { const x = otherInterest.trim(); if (x) { setInterests((l) => (l.includes(x) ? l : [...l, x].slice(0, 12))); setOtherInterest(""); } };
  const back = () => setStep((s) => Math.max(0, s - 1));

  useEffect(() => {
    if (!voiceGuideEnabled) return;
    const prompts: Record<(typeof STEPS)[number], string> = {
      about: "First, tell us what to call you and how old you are. Your name and age stay in ThinkFirst. Say next when ready.",
      status: "What describes you? Choose school student, university student, working, or learning on my own. Say choose and the option, then next.",
      field: "Choose or type your speciality or working field, and optionally your year of study or job title. Say next when ready.",
      interests: "What do you like learning? Pick any topics you want and how many hours you can study per week. Say next when ready.",
      goal: "What brings you here? Choose understand my course, prepare for an exam, learn on my own, or not sure. Say choose and the option, then next.",
      confidence: "How confident do you feel? Choose a confidence level from lost to very confident, then say next.",
      slot: "When is your first session? Choose one of the suggested times, or type another time. Say next when ready.",
      input: "How do you like to answer? Choose typing or speaking, then say next.",
      privacy: "Review optional learning behavior tracking. Essential data is always on. Say next when ready.",
      deal: "This is the learning agreement. Say choose I'm in to accept, then say save and start to continue.",
    };
    speakWithAvatar(`Question ${step + 1} of ${STEPS.length}. ${prompts[key]} Press Ask by voice when you are ready; the microphone is not always listening.`, {
      title: "Voice guide",
      hint: "voice navigation",
    });
  }, [key, speakWithAvatar, step, voiceGuideEnabled]);

  // Number keys pick an option on choice screens; Enter moves on.
  useEffect(() => {
    const map: Record<string, { opts: Choice[]; set: (v: string) => void }> = {
      goal: { opts: GOALS, set: setGoal }, status: { opts: STATUS, set: (v) => { setStatus(v); setError(null); } },
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
          {key === "about" && (<>
            <h1 className="mt-2 text-page-compact">First, <span className="hl">you</span></h1>
            <p className="mt-2 text-ink-muted">Your name and age stay in ThinkFirst. They are never sent to the AI.</p>
            <label className="label mt-6" htmlFor="onb-name">What should we call you?</label>
            <input id="onb-name" className="field" autoComplete="given-name" maxLength={120} value={name} onChange={(e) => { setName(e.target.value); setError(null); }} />
            <label className="label mt-5" htmlFor="onb-age">How old are you?</label>
            <input id="onb-age" type="number" inputMode="numeric" min={5} max={100} className="field max-w-[10rem]" value={age} onChange={(e) => { setAge(e.target.value); setError(null); }} />
            {ageNum !== null && ageOk && ageNum < 18 && <p className="mt-2 text-meta text-ink-muted">Under 18: we ask a guardian before saving more than your account.</p>}
          </>)}
          {key === "status" && (<>
            <h1 className="mt-2 text-page-compact">What <span className="hl">describes you</span>?</h1>
            <p className="mt-2 text-ink-muted">So lessons and the first question are the right level.</p>
            <Options name="Situation" options={STATUS} value={status} onPick={(v) => { if (v !== status) { setField(""); setDetail(""); } setStatus(v); setError(null); }} />
          </>)}
          {key === "field" && (<>
            <h1 className="mt-2 text-page-compact">{status === "working" ? <>Your <span className="hl">working field</span>?</> : <>Your <span className="hl">speciality</span>?</>}</h1>
            <p className="mt-2 text-ink-muted">We suggest topics for it and take examples from it.</p>
            <ul className="mt-6 flex flex-wrap gap-2" aria-label="Common fields">
              {(FIELDS[status] ?? FIELDS.university).map((f) => (
                <li key={f}><button type="button" className="chip" aria-pressed={field === f} onClick={() => { setField(f); setError(null); }}>{f}</button></li>
              ))}
            </ul>
            <label className="label mt-5" htmlFor="onb-field">Or type it</label>
            <input id="onb-field" className="field" maxLength={120} value={field} placeholder="e.g. Cybersecurity, Nursing, Civil engineering" onChange={(e) => { setField(e.target.value); setError(null); }} />
            {YEARS[status] && (<>
              <label className="label mt-5" htmlFor="onb-year">{status === "school" ? "Grade" : "Year of study"} (optional)</label>
              <select id="onb-year" className="field" value={detail} onChange={(e) => setDetail(e.target.value)}>
                <option value="">Choose</option>{YEARS[status].map((y) => <option key={y}>{y}</option>)}
              </select>
            </>)}
            {status === "working" && (<>
              <label className="label mt-5" htmlFor="onb-job">Job title (optional)</label>
              <input id="onb-job" className="field" maxLength={120} value={detail} onChange={(e) => setDetail(e.target.value)} />
            </>)}
          </>)}
          {key === "interests" && (<>
            <h1 className="mt-2 text-page-compact">What do you <span className="hl">like</span> learning?</h1>
            <p className="mt-2 text-ink-muted">Pick as many as you want. Optional.</p>
            <ul className="mt-6 flex flex-wrap gap-2" aria-label="Interests">
              {[...INTERESTS, ...interests.filter((x) => !INTERESTS.includes(x))].map((x) => (
                <li key={x}><button type="button" className="chip" aria-pressed={interests.includes(x)} onClick={() => toggleInterest(x)}>{x}</button></li>
              ))}
            </ul>
            <label className="label mt-5" htmlFor="onb-other">Something else</label>
            <div className="flex gap-2">
              <input id="onb-other" className="field" maxLength={60} value={otherInterest} onChange={(e) => setOtherInterest(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addOther(); } }} />
              <button type="button" className="btn-secondary" onClick={addOther}>Add</button>
            </div>
            <label className="label mt-5" htmlFor="onb-hours">Hours you can study per week</label>
            <input id="onb-hours" type="number" inputMode="numeric" min={1} max={80} className="field max-w-[10rem]" value={hours} onChange={(e) => setHours(e.target.value)} />
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

          {error && <p role="alert" className="mt-4 text-review">{error} {!missing && <button type="button" className="btn-link" onClick={save}>Retry</button>}</p>}

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
