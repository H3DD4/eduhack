"use client";
// A02 Onboarding architecture (UC01 + diagnostic.md):
// Under 3 minutes, every field has a named consumer (Identity, Consent/Policy gate, Plan brain, Diagnostic prior,
// Calibration baseline, Session brain). One-click "Continue" works immediately with safe defaults (essential tier only).
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";

const GOALS = [
  { v: "understand", t: "Understand my course" },
  { v: "exam", t: "Prepare for an exam" },
  { v: "self_study", t: "Self-study a topic" },
  { v: "unsure", t: "Unsure" },
];
const LEVELS = [
  { v: "high_school", t: "High school / Bac" },
  { v: "university", t: "University / Engineering" },
  { v: "professional", t: "Self-learner / Certification" },
];
const INPUTS = [
  { v: "text", t: "Typing" },
  { v: "voice", t: "Speaking (you choose when to turn the microphone on)" },
];

export default function Onboarding() {
  const router = useRouter();
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

  const save = async () => {
    setBusy(true);
    setError(null);
    const parsedYear = birthYear.trim() ? Number(birthYear.trim()) : null;
    try {
      await api("/me/onboarding", {
        method: "PATCH",
        json: {
          goal,
          level,
          input_preference: input,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          birth_year: parsedYear,
          deal_accepted: dealAccepted,
          prior_confidence: priorConfidence,
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

  return (
    <AppShell focused requireSetup={false}>
      <div className="mx-auto max-w-form px-4 py-10" data-screen="A02">
        <h1 className="text-page-compact">What brings you here?</h1>
        <p className="mt-1 text-meta text-ink-muted">
          Quick setup (~60s). Every answer tunes your starting roadmap and diagnostic prior.
        </p>

        <div className="mt-5 rounded-control border-2 border-stroke bg-surface-subtle p-4">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={dealAccepted}
              onChange={(e) => setDealAccepted(e.target.checked)}
              className="mt-1"
            />
            <span>
              <strong>The deal:</strong> “I won&apos;t give you answers. I&apos;ll make you better at finding them.”
            </span>
          </label>
        </div>

        <fieldset className="mt-6 space-y-2">
          <legend className="label">Goal (Plan brain &amp; diagnostic length)</legend>
          {GOALS.map((g) => (
            <label key={g.v} className="flex min-h-[48px] items-center gap-3 rounded-control border-2 border-stroke bg-surface px-4">
              <input type="radio" name="goal" value={g.v} checked={goal === g.v} onChange={() => setGoal(g.v)} /> {g.t}
            </label>
          ))}
        </fieldset>

        <fieldset className="mt-6 space-y-2">
          <legend className="label">Current level (Diagnostic starting prior θ)</legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {LEVELS.map((l) => (
              <label key={l.v} className="flex min-h-[44px] items-center gap-2 rounded-control border border-stroke bg-surface px-3 text-meta">
                <input type="radio" name="level" value={l.v} checked={level === l.v} onChange={() => setLevel(l.v)} /> {l.t}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="onb-confidence">
              Starting confidence (1–5, calibration baseline)
            </label>
            <select
              id="onb-confidence"
              className="input mt-1 w-full"
              value={priorConfidence}
              onChange={(e) => setPriorConfidence(Number(e.target.value))}
            >
              <option value={1}>1 — Very unsure</option>
              <option value={2}>2 — A bit rusty</option>
              <option value={3}>3 — Moderately confident</option>
              <option value={4}>4 — Confident</option>
              <option value={5}>5 — Very confident</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="onb-slot">
              First study session commitment
            </label>
            <input
              id="onb-slot"
              className="input mt-1 w-full"
              value={firstSessionSlot}
              onChange={(e) => setFirstSessionSlot(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="onb-birth-year">
              Birth year (optional, age gate for minors protection)
            </label>
            <input
              id="onb-birth-year"
              type="number"
              placeholder="e.g. 2005"
              className="input mt-1 w-full"
              value={birthYear}
              onChange={(e) => setBirthYear(e.target.value)}
            />
          </div>
          <div className="flex items-end">
            <label className="flex min-h-[44px] items-center gap-2 rounded-control border border-stroke bg-surface px-3 py-2 text-meta">
              <input
                type="checkbox"
                checked={behaviorTier}
                onChange={(e) => setBehaviorTier(e.target.checked)}
              />
              <span>Allow learning-behavior signals (hesitation, edits, rhythm) to adapt pacing</span>
            </label>
          </div>
        </div>

        <fieldset className="mt-6 space-y-2">
          <legend className="label">How do you prefer to answer? (you can switch any time)</legend>
          {INPUTS.map((g) => (
            <label key={g.v} className="flex min-h-[48px] items-center gap-3 rounded-control border-2 border-stroke bg-surface px-4">
              <input type="radio" name="input" value={g.v} checked={input === g.v} onChange={() => setInput(g.v)} /> {g.t}
            </label>
          ))}
        </fieldset>

        {error && (
          <p role="alert" className="mt-4 text-review">
            {error} <button className="btn-link" onClick={save}>Retry</button>
          </p>
        )}
        <button className="btn-primary mt-8 w-full" onClick={save} disabled={busy}>
          Continue
        </button>
      </div>
    </AppShell>
  );
}
