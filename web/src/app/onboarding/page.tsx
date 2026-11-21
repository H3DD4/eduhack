"use client";
// A02 Goal and preferences — UC01. Unsure is valid; no learning-style labels; no microphone permission here.
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
const INPUTS = [
  { v: "text", t: "Typing" },
  { v: "voice", t: "Speaking (you choose when to turn the microphone on)" },
];

export default function Onboarding() {
  const router = useRouter();
  const [goal, setGoal] = useState("unsure");
  const [input, setInput] = useState("text");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api("/me/onboarding", { method: "PATCH", json: { goal, input_preference: input,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone } });
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
        <fieldset className="mt-6 space-y-2">
          <legend className="label">Goal</legend>
          {GOALS.map((g) => (
            <label key={g.v} className="flex min-h-[48px] items-center gap-3 rounded-control border-2 border-stroke bg-surface px-4">
              <input type="radio" name="goal" value={g.v} checked={goal === g.v} onChange={() => setGoal(g.v)} /> {g.t}
            </label>
          ))}
        </fieldset>
        <fieldset className="mt-6 space-y-2">
          <legend className="label">How do you prefer to answer? (you can switch any time)</legend>
          {INPUTS.map((g) => (
            <label key={g.v} className="flex min-h-[48px] items-center gap-3 rounded-control border-2 border-stroke bg-surface px-4">
              <input type="radio" name="input" value={g.v} checked={input === g.v} onChange={() => setInput(g.v)} /> {g.t}
            </label>
          ))}
        </fieldset>
        {error && <p role="alert" className="mt-4 text-review">{error} <button className="btn-link" onClick={save}>Retry</button></p>}
        <button className="btn-primary mt-8 w-full" onClick={save} disabled={busy}>Continue</button>
      </div>
    </AppShell>
  );
}
