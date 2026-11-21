"use client";
// C03 Adaptive diagnostic & optional baseline (UC07 + diagnostic.md architecture).
// Measures mastery, misconceptions, confidence calibration and learning behavior in 8-12 short questions,
// while keeping "Skip and open the roadmap" always available (records insufficient evidence, never zero ability).
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SubjectShell } from "@/components/SubjectShell";
import { MathText } from "@/components/ui";
import { api, trackEvent } from "@/lib/api";

const CONFIDENCE_LEVELS = [
  { v: 1, label: "1 · Guessing" },
  { v: 2, label: "2 · Unsure" },
  { v: 3, label: "3 · Fairly sure" },
  { v: 4, label: "4 · Confident" },
  { v: 5, label: "5 · Certain" },
];

export default function Diagnostic() {
  const { s } = useParams<{ s: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<any>(null);
  const [ks, setKs] = useState<any>(null);
  const [confidence, setConfidence] = useState<number>(3);
  const [selectedOption, setSelectedOption] = useState<string>("");
  const [typedAnswer, setTypedAnswer] = useState<string>("");
  const [edits, setEdits] = useState<number>(0);
  const [focusSwitches, setFocusSwitches] = useState<number>(0);
  const [nudge, setNudge] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const shownAt = useRef<number>(Date.now());

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "hidden") setFocusSwitches((n) => n + 1);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => {
    let active = true;
    api(`/subjects/${s}/diagnostic`)
      .then((res) => {
        if (!active) return;
        setKs(res.knowledge_space);
        if (res.adaptive) setSession(res.adaptive);
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => {
      active = false;
    };
  }, [s]);

  const resetInputs = () => {
    setConfidence(3);
    setSelectedOption("");
    setTypedAnswer("");
    setEdits(0);
    setFocusSwitches(0);
    setError(null);
    shownAt.current = Date.now();
  };

  const handleStart = async (restart = false) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api(`/subjects/${s}/diagnostic/start`, {
        method: "POST",
        json: { restart },
      });
      setSession(res);
      setNudge(null);
      resetInputs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async (dontKnow = false) => {
    if (!session?.current_item) return;
    setBusy(true);
    setError(null);
    const durationMs = Math.max(500, Date.now() - shownAt.current);
    try {
      const res = await api(`/subjects/${s}/diagnostic/answer`, {
        method: "POST",
        json: {
          item_id: session.current_item.id,
          answer: typedAnswer,
          option_id: selectedOption || null,
          confidence,
          dont_know: dontKnow,
          duration_ms: durationMs,
          edits,
          focus_switches: focusSwitches,
        },
      });
      setSession(res);
      setNudge(res.last_answer?.nudge || null);
      resetInputs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const handleSkip = async () => {
    setBusy(true);
    await api(`/subjects/${s}/diagnostic/skip`, { method: "POST" });
    router.push(`/subjects/${s}/roadmap`);
  };

  const item = session?.current_item;
  const profile = session?.profile;
  const view = profile?.student_view;

  return (
    <SubjectShell subjectId={s} crumb="Optional baseline">
      <section className="card max-w-prose space-y-5 !p-6 md:!p-8" data-screen="C03">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-section">Find where to <span className="hl">start</span></h2>
            <p className="text-meta text-ink-muted">
              8–12 short questions to map your starting frontier. It’s not a test, and skipping never locks concepts.
            </p>
          </div>
          {ks && (
            <span className="badge">
              {ks.skills?.length || 0} skills · {ks.item_count || 0} calibrated items
            </span>
          )}
        </div>

        {loading && <p className="text-meta text-ink-muted">Loading knowledge space…</p>}

        {!loading && !session && (
          <div className="space-y-4">
            <p>
              We start with an easy question, adapt along the prerequisite graph, and highlight the exact concept
              where your next study session will pay off most.
            </p>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" disabled={busy} onClick={() => handleStart(false)}>
                Start adaptive check (~3 min)
              </button>
              <button className="btn-secondary" disabled={busy} onClick={handleSkip}>
                Skip and open the roadmap
              </button>
            </div>
          </div>
        )}

        {item && session?.status === "active" && (
          <div className="space-y-5 border-t border-stroke pt-4" data-phase="diagnostic-question">
            <div className="bar" role="progressbar" aria-label="Diagnostic progress" aria-valuemin={0} aria-valuemax={item.max_items} aria-valuenow={item.step_no}>
              <span style={{ width: `${Math.round((100 * item.step_no) / Math.max(1, item.max_items))}%` }} />
            </div>
            <div className="flex items-center justify-between text-meta text-ink-muted">
              <span>Question {item.step_no} of up to {item.max_items}</span>
              <span>~{Math.max(1, Math.round((item.remaining_seconds_estimate || 180) / 60))} min remaining</span>
            </div>

            {nudge && (
              <p role="status" className="hint-in rounded-control border-2 border-ink bg-surface-subtle px-4 py-3">
                {nudge}
              </p>
            )}

            <fieldset className="space-y-2">
              <legend className="label">1. How confident do you feel about this topic right now?</legend>
              <div className="flex flex-wrap gap-2">
                {CONFIDENCE_LEVELS.map((c) => (
                  <button
                    key={c.v}
                    type="button"
                    onClick={() => {
                      setConfidence(c.v);
                      trackEvent("rated_confidence", { type: "item", id: item.id, skills: item.skills }, {}, { confidence: c.v, phase: "diagnostic" }, s);
                    }}
                    aria-pressed={confidence === c.v}
                    className="chip text-meta"
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="space-y-3">
              <p className="label">2. Your answer</p>
              <p className="font-mono text-problem"><MathText text={item.prompt} /></p>
              {item.options && item.options.length > 0 && (
                <div className="space-y-2">
                  {item.options.map((opt: any) => (
                    <label
                      key={opt.id}
                      className="option"
                    >
                      <input
                        type="radio"
                        name="diag-option"
                        value={opt.id}
                        checked={selectedOption === opt.id}
                        onChange={() => {
                          if (selectedOption && selectedOption !== opt.id) setEdits((n) => n + 1);
                          setSelectedOption(opt.id);
                          setTypedAnswer(opt.text);
                        }}
                      />
                      <span>{opt.text}</span>
                    </label>
                  ))}
                </div>
              )}

              {item.kind === "expand" && (
                <div>
                  <label className="label" htmlFor="diag-input">
                    Or type your algebraic expression
                  </label>
                  <input
                    id="diag-input"
                    className="input mt-1 w-full"
                    value={typedAnswer}
                    onChange={(e) => {
                      setTypedAnswer(e.target.value);
                      setSelectedOption("");
                      setEdits((n) => n + 1);
                    }}
                    placeholder="e.g. 2x + 6"
                  />
                </div>
              )}
            </div>

            {error && <p role="alert" className="text-review">{error}</p>}

            <div className="flex flex-wrap items-center gap-3">
              <button
                className="btn-primary"
                disabled={busy || (!selectedOption && !typedAnswer.trim())}
                onClick={() => handleSubmit(false)}
              >
                Submit answer
              </button>
              <button className="btn-secondary" disabled={busy} onClick={() => handleSubmit(true)}>
                I don&apos;t know yet
              </button>
              <button className="btn-link ml-auto" disabled={busy} onClick={handleSkip}>
                Skip and open the roadmap
              </button>
            </div>
          </div>
        )}

        {session?.status === "completed" && view && (
          <div className="space-y-4 border-t border-stroke pt-4" data-phase="diagnostic-result">
            <h3 className="text-page-compact">{view.headline}</h3>
            <div className="fade-in space-y-2 rounded-card border-2 border-ink bg-surface-subtle p-5 shadow-hard">
              <p><span className="text-ink-muted">Your next frontier:</span> {view.where_we_start?.map((w: any) => w.title).join(", ")}</p>
              <p><span className="text-ink-muted">Strength spotted:</span> {view.strength?.message}</p>
              <p><span className="text-ink-muted">Where to focus first:</span> {view.real_gap}</p>
              <p><span className="text-ink-muted">Confidence check:</span> {view.calibration_line}</p>
              <p><span className="text-ink-muted">First session:</span> {view.first_session_booked?.slot} on “{view.first_session_booked?.starting_skill?.title}”</p>
              <p className="text-meta text-ink-muted">{view.transparency}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" onClick={() => router.push(`/subjects/${s}/roadmap`)}>
                Open my calibrated roadmap
              </button>
              <button className="btn-secondary" disabled={busy} onClick={() => handleStart(true)}>
                Retake check
              </button>
            </div>
          </div>
        )}
      </section>
    </SubjectShell>
  );
}
