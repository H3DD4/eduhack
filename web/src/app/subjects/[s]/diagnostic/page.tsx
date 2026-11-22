"use client";
// C03 Adaptive diagnostic & optional baseline (UC07 + diagnostic.md architecture).
// Measures mastery, misconceptions, confidence calibration and learning behavior in 8-12 short questions,
// while keeping "Skip and open the roadmap" always available (records insufficient evidence, never zero ability).
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SpeakButton } from "@/components/avatar/AvatarSpeakerContext";
import { TeacherAvatar } from "@/components/avatar/TeacherAvatar";
import { LevelReport } from "@/components/LevelReport";
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
  // Start-wizard subjects: placement state (AI questions being written?) + the level report once finished.
  const [lvl, setLvl] = useState<any>(null);
  const loadLevel = () => api(`/subjects/${s}/level`).then(setLvl).catch(() => undefined);
  const wizard = lvl && lvl.placement.state !== "not_needed";
  const preparing = lvl?.placement.state === "preparing";
  useEffect(() => { loadLevel(); }, [s]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!preparing) return;
    const id = setInterval(loadLevel, 2000);
    return () => clearInterval(id);
  }, [preparing]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (session?.status === "completed") loadLevel(); }, [session?.status]);  // eslint-disable-line react-hooks/exhaustive-deps

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
    if (wizard) {  // "skip the level test" = start from scratch as a beginner
      await api(`/subjects/${s}/intent`, { method: "PATCH", json: { prior_knowledge: "none" } });
      router.push(`/subjects/${s}/start`);
      return;
    }
    await api(`/subjects/${s}/diagnostic/skip`, { method: "POST" });
    router.push(`/subjects/${s}/roadmap`);
  };

  const item = session?.current_item;
  const profile = session?.profile;
  const view = profile?.student_view;

  return (
    <SubjectShell subjectId={s} crumb={wizard ? "Level test" : "Optional baseline"}>
      <section className="card max-w-prose space-y-5 !p-6 md:!p-8" data-screen="C03">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-section">{wizard ? <>Find your <span className="hl">level</span></> : <>Find where to <span className="hl">start</span></>}</h2>
            <p className="text-meta text-ink-muted">
              {wizard
                ? "5–12 multiple-choice questions, easy first, then adapted to your answers. No help; “I don't know” is always fine."
                : "8–12 short questions to map your starting frontier. It’s not a test, and skipping never locks concepts."}
            </p>
            {wizard && lvl.placement.uses_ai_questions && (
              <p className="text-meta text-ink-muted">{lvl.placement.verified_items} questions written for this roadmap and double-checked by an independent AI pass.</p>
            )}
          </div>
          {ks && (
            <span className="badge">
              {ks.skills?.length || 0} skills · {ks.item_count || 0} {wizard ? "questions" : "calibrated items"}
            </span>
          )}
        </div>

        {loading && <p className="text-meta text-ink-muted">Loading knowledge space…</p>}

        {preparing && (
          <div className="hero p-6" aria-busy="true"><div className="relative z-10 space-y-1">
            <p className="text-section !text-[1.25rem]">Writing your test questions…</p>
            <p className="muted">Three questions per concept (easy, medium, hard), each checked by a second, independent AI pass. Usually under a minute.</p>
          </div></div>
        )}

        {!loading && !session && !preparing && (
          <div className="space-y-4">
            <p>
              We start with an easy question, adapt along the prerequisite graph, and highlight the exact concept
              where your next study session will pay off most.
            </p>
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" disabled={busy} onClick={() => handleStart(false)}>
                {wizard ? "Start the level test (~5 min)" : "Start adaptive check (~3 min)"}
              </button>
              <button className="btn-secondary" disabled={busy} onClick={handleSkip}>
                {wizard ? "Skip — start from scratch" : "Skip and open the roadmap"}
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
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="label !mb-0">2. Your answer</p>
                <SpeakButton text={item.prompt} title={`Question ${item.step_no}`} subjectId={s} label="Speak question" />
              </div>
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
                {wizard ? "Stop — start from scratch" : "Skip and open the roadmap"}
              </button>
            </div>
          </div>
        )}

        {session?.status === "completed" && view && (
          <div className="space-y-4 border-t border-stroke pt-4" data-phase="diagnostic-result">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-page-compact">{view.headline}</h3>
              <SpeakButton
                text={`${view.headline}. Your next frontier: ${view.where_we_start?.map((w: any) => w.title).join(", ")}. ${view.strength?.message || ""} ${view.real_gap || ""} ${view.calibration_line || ""} First session booked: ${view.first_session_booked?.slot} on ${view.first_session_booked?.starting_skill?.title}. ${view.transparency || ""}`}
                title="Diagnostic profile"
                subjectId={s}
                label="Speak summary"
              />
            </div>
            <TeacherAvatar
              text={`${view.headline}! [wave] Your starting frontier is ${view.where_we_start?.map((w: any) => w.title).join(", ")}. [point] ${view.strength?.message || ""} [happy] ${view.real_gap || ""} [encouraging] ${view.calibration_line || ""} [nod] Your first session is booked for ${view.first_session_booked?.slot}.`}
              hint={view.where_we_start?.[0]?.title || "algebra"}
              title="Diagnostic result"
              compact
              stageHeight={250}
            />
            <div className="fade-in space-y-2 rounded-card border-2 border-ink bg-surface-subtle p-5 shadow-hard">
              <p><span className="text-ink-muted">Your next frontier:</span> {view.where_we_start?.map((w: any) => w.title).join(", ")}</p>
              <p><span className="text-ink-muted">Strength spotted:</span> {view.strength?.message}</p>
              <p><span className="text-ink-muted">Where to focus first:</span> {view.real_gap}</p>
              <p><span className="text-ink-muted">Confidence check:</span> {view.calibration_line}</p>
              <p><span className="text-ink-muted">First session:</span> {view.first_session_booked?.slot} on “{view.first_session_booked?.starting_skill?.title}”</p>
              <p className="text-meta text-ink-muted">{view.transparency}</p>
            </div>
            {wizard && lvl?.report?.available && <LevelReport report={lvl.report} />}
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" onClick={() => router.push(`/subjects/${s}/roadmap`)}>
                {wizard ? "See my roadmap (built on your level)" : "Open my calibrated roadmap"}
              </button>
              {wizard && (
                <button className="btn-secondary" onClick={() => router.push(`/subjects/${s}/start`)}>
                  My path &amp; course summary
                </button>
              )}
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
