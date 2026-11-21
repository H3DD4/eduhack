"use client";
// Explain-back (S02 explanation/follow-up) — UC21 + blueprint audio phase table.
// Voice and text share the rubric; transcript must be confirmed (and corrected) before assessment.
import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, newKey, pollJob, sha256Hex } from "@/lib/api";
import { ctas, statusCopy } from "@/lib/recorder/machine";
import { useRecorder } from "@/lib/recorder/useRecorder";
import { ErrorBox, LiveRegion, SimulatedLabel } from "../ui";
import { RubricFeedback } from "./RubricFeedback";

type Phase = "compose" | "uploading" | "transcribing" | "confirmation" | "assessing" | "feedback" | "job_recovery";

const fmt = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}`;

function Recorder({ taskId, caps, retention, setRetention, onUse, onUseText }:
  { taskId: string; caps: any; retention: string; setRetention: (r: string) => void;
    onUse: (blob: Blob, mime: string, captureMs: number) => void; onUseText: () => void }) {
  const r = useRecorder(taskId);
  const s = r.state;
  const c = ctas(s);
  const primary = () => {
    switch (s.phase) {
      case "permission_intent": return r.enable();
      case "blocked": r.releaseForText(); return onUseText();
      case "ready": return r.start();
      case "recording": return r.finish();
      case "paused": return r.resume();
      case "capture_error": return s.hasPartial ? r.reviewPartial() : r.retake();
      case "playback": return r.blob && onUse(r.blob, r.mime, r.captureMs());
    }
  };
  const secondary = () => {
    switch (s.phase) {
      case "permission_intent": case "permission_pending": case "ready": r.releaseForText(); return onUseText();
      case "blocked": return r.retryMic();
      case "recording": return r.pause();
      case "paused": return r.finish();
      case "capture_error": return s.hasPartial ? r.retake() : (r.releaseForText(), onUseText());
      case "playback": return r.retake();
    }
  };
  return (
    <div className="space-y-4" data-recorder-phase={s.phase}>
      <LiveRegion message={statusCopy(s)} />
      {s.phase === "permission_intent" && (
        <div className="space-y-3 rounded-detail border border-border bg-canvas p-4 text-meta">
          <p className="text-body">{statusCopy(s)}</p>
          <p><strong>Who receives what:</strong>{" "}
            {caps?.audio_processor ? `Your audio is sent to ${caps.audio_processor} for transcription only.` :
              "Demo: no speech recognition is configured. Your audio is stored privately and not analysed; a labeled fixture transcript is shown for you to edit."}{" "}
            {caps?.text_processors?.length ? `Your confirmed text (not audio) is checked by ${caps.text_processors.join(", then ")}.` : "Your confirmed text is checked by the built-in demo assessor (Simulated assessment)."}
          </p>
          <fieldset>
            <legend className="font-semibold">Keep the audio?</legend>
            <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ret" checked={retention === "delete_after_confirmation"} onChange={() => setRetention("delete_after_confirmation")} />
              Delete the audio after I confirm the text (default)</label>
            <label className="flex min-h-[44px] items-center gap-2"><input type="radio" name="ret" checked={retention === "replay_7_days"} onChange={() => setRetention("replay_7_days")} />
              Keep it for replay, deleted 7 days after upload</label>
          </fieldset>
          <p>Transcript history is kept until you delete it. Length, accent, pauses and fluency are never scored.</p>
        </div>
      )}
      {s.phase !== "permission_intent" && <p className="font-semibold">{statusCopy(s)}</p>}
      {["recording", "paused", "pausing", "resuming"].includes(s.phase) && (
        <p className="text-meta text-ink-muted"><span aria-hidden>{s.phase === "recording" ? "● " : "❚❚ "}</span>Captured {fmt(r.elapsedMs)} <span className="sr-only">(time is not announced continuously)</span></p>
      )}
      {r.localSaved === "device" && ["recording", "paused", "playback", "capture_error"].includes(s.phase) && <p className="text-meta text-help">Saved on this device as you record (best effort).</p>}
      {r.localSaved === "failed" && <p className="text-meta text-review">This draft cannot be saved on this device. Keep this tab open until you upload.</p>}
      {s.phase === "playback" && r.blobUrl && <audio controls src={r.blobUrl} className="w-full" aria-label="Your recording" />}
      <div className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={primary} disabled={c.primaryDisabled} aria-disabled={c.primaryDisabled}>{c.primary}</button>
        {c.secondary && <button className="btn-secondary" onClick={secondary} disabled={c.secondary === "Stay here"}>{c.secondary}</button>}
      </div>
    </div>
  );
}

export function ExplainFlow({ task, subjectId, caps, defaultInput, draft, onDraft, onAssessed, next, retentionPref }:
  { task: any; subjectId: string; caps: any; defaultInput: "text" | "voice"; draft: string; onDraft: (t: string) => void;
    onAssessed: () => void; next: (a: any) => ReactNode; retentionPref: string }) {
  const [mode, setMode] = useState<"voice" | "text">(defaultInput);
  const [phase, setPhase] = useState<Phase>(task.last_assessment ? "feedback" : "compose");
  const [version, setVersion] = useState<any>(null);
  const [original, setOriginal] = useState<any>(null);
  const [take, setTake] = useState<any>(null);
  const [edited, setEdited] = useState("");
  const [resolved, setResolved] = useState<string[]>([]);
  const [keepUnclear, setKeepUnclear] = useState(false);
  const [supplement, setSupplement] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const [retention, setRetention] = useState(retentionPref || "delete_after_confirmation");
  const [announce, setAnnounce] = useState("");
  const uploadKey = useRef<string | null>(null);
  const confirmKey = useRef(newKey());
  const editRef = useRef<HTMLTextAreaElement>(null);
  const headRef = useRef<HTMLHeadingElement>(null);

  const loadState = useCallback(async () => {
    const st = await api(`/tasks/${task.id}/explain`);
    const versions = st.versions.filter((v: any) => v.kind !== "supplement");
    const latest = versions[versions.length - 1];
    const orig = versions.find((v: any) => v.kind === "original_asr" && v.take_id === latest?.take_id) || null;
    setOriginal(orig);
    setTake(st.takes.find((t: any) => t.id === latest?.take_id) || st.takes[st.takes.length - 1] || null);
    return { st, latest };
  }, [task.id]);

  // Resume the actual phase after reload (job recovery).
  useEffect(() => {
    if (task.last_assessment) return;
    loadState().then(({ st, latest }) => {
      if (latest && !latest.confirmed) {
        setVersion(latest);
        setEdited(latest.text);
        setPhase("confirmation");
      } else {
        const pending = st.takes.find((t: any) => t.job && !["succeeded", "failed", "cancelled"].includes(t.job.status));
        if (pending) waitTranscription(pending.job.id);
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task.id]);
  useEffect(() => { if (task.last_assessment) setPhase("feedback"); }, [task.last_assessment]);
  useEffect(() => { headRef.current?.focus(); }, [phase]);

  const waitTranscription = async (jobId: string) => {
    setPhase("transcribing");
    setAnnounce("Turning your recording into text. You will check it first.");
    const job = await pollJob(jobId, (_j, ms) => setSlow(ms > 60_000));
    if (job.status !== "succeeded") {
      setPhase("job_recovery");
      setErr(job.status === "slow" ? "This is taking longer than usual. Check status, or save and leave — the job continues." : "Transcription did not finish. Retry the same job or use text.");
      return;
    }
    const { latest } = await loadState();
    setVersion(latest);
    setEdited(latest?.text || "");
    setPhase("confirmation");
    setAnnounce("Transcript ready. Check names, numbers and meaning.");
  };

  const upload = async (blob: Blob, mime: string, captureMs: number) => {
    setErr(null);
    setPhase("uploading");
    setAnnounce("Uploading. Assessment has not started.");
    uploadKey.current = uploadKey.current || newKey();
    const timer = setTimeout(() => setSlow(true), 30_000);
    try {
      const buf = await blob.arrayBuffer();
      const fd = new FormData();
      fd.set("file", new File([buf], mime.includes("mp4") ? "take.m4a" : "take.webm", { type: mime.split(";")[0] }));
      fd.set("idempotency_key", uploadKey.current);
      fd.set("retention", retention);
      fd.set("capture_ms", String(captureMs));
      const sum = await sha256Hex(buf);
      if (sum) fd.set("checksum", sum);
      const r = await api(`/tasks/${task.id}/audio`, { method: "POST", body: fd });
      clearTimeout(timer);
      setSlow(false);
      if (!sum || r.receipt.checksum === sum) {
        const { clearTake } = await import("@/lib/recorder/localStore");
        await clearTake(task.id); // verified server receipt: clear the on-device copy
      }
      uploadKey.current = null;
      await waitTranscription(r.job.id);
    } catch (e) {
      clearTimeout(timer);
      setPhase("compose");
      setErr(`${(e as ApiError).message} Not uploaded yet — your recording is still on this device. Retry when ready.`);
    }
  };

  const reviewText = async () => {
    setErr(null);
    try {
      const r = await api(`/tasks/${task.id}/typed`, { method: "POST", json: { text: draft } });
      const v = { id: r.version_id, kind: "typed", text: draft, unresolved: [], source_label: "Typed by you" };
      setVersion(v);
      setOriginal(null);
      setEdited(draft);
      setPhase("confirmation");
    } catch (e) {
      setErr((e as ApiError).message);
    }
  };

  const unresolved = (version?.unresolved || []).filter((u: any) => edited.includes(u.text) && !resolved.includes(u.id));

  const confirm = async () => {
    setErr(null);
    try {
      let vid = version.id;
      if (edited.trim() !== version.text.trim() || resolved.length) {
        const c = await api(`/tasks/${task.id}/corrections`, { method: "POST", json: { base_version_id: vid, text: edited, resolved_span_ids: resolved } });
        vid = c.version_id;
      }
      setPhase("assessing");
      setAnnounce("Checking the ideas against this task's rubric.");
      const r = await api(`/tasks/${task.id}/confirm`, { method: "POST", json: {
        version_id: vid, supplement: supplement || null, keep_unresolved: keepUnclear, idempotency_key: confirmKey.current } });
      const job = r.job.status === "succeeded" ? r.job : await pollJob(r.job.id, (_j, ms) => setSlow(ms > 60_000));
      if (job.status !== "succeeded") {
        setPhase("job_recovery");
        setErr("The check did not finish. Retry the same check — your confirmed text is saved.");
        return;
      }
      confirmKey.current = newKey();
      await loadState(); // reflect server-side audio deletion after confirmation
      onAssessed();
      setPhase("feedback");
    } catch (e) {
      const ae = e as ApiError;
      setPhase("confirmation");
      setErr(ae.code === "UNRESOLVED_SPANS" ? "Some words are still marked unclear. Check them, or choose to keep them as unclear (they will not be scored)." : ae.message);
    }
  };

  const deleteAudio = async () => {
    if (!take) return;
    await api(`/audio/${take.id}`, { method: "DELETE" });
    setTake({ ...take, playable: false, status: "deleted" });
    setAnnounce("Audio deleted; transcript history remains.");
  };

  const a = task.last_assessment;
  return (
    <section aria-labelledby="ex-h" className="space-y-5">
      <LiveRegion message={announce} />
      <h2 id="ex-h" ref={headRef} tabIndex={-1} className="sr-only">Explanation step: {phase}</h2>
      {err && <ErrorBox message={err}>{phase === "job_recovery" && <button className="btn-secondary" onClick={() => location.reload()}>Check status</button>}</ErrorBox>}

      {phase === "compose" && (
        <>
          <div role="tablist" aria-label="Answer mode" className="flex gap-2">
            {(["voice", "text"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                className={mode === m ? "btn-secondary !border-action bg-success-surface" : "btn-secondary"}>{m === "voice" ? "Voice" : "Text"}</button>
            ))}
          </div>
          {mode === "voice" ? (
            <Recorder taskId={task.id} caps={caps} retention={retention} setRetention={setRetention} onUse={upload} onUseText={() => setMode("text")} />
          ) : (
            <div className="space-y-3">
              <label htmlFor="ex-text" className="label">Your explanation</label>
              <textarea id="ex-text" className="field !min-h-[160px]" value={draft} onChange={(e) => onDraft(e.target.value)}
                aria-describedby="ex-hint" />
              <p id="ex-hint" className="text-meta text-ink-muted">Typing uses the same concept rubric. Short is fine; length earns nothing. Mixing French, English or Arabic is fine.</p>
              <div className="flex flex-wrap gap-3">
                <button className="btn-primary" onClick={reviewText} disabled={!draft.trim()}>Review text</button>
              </div>
              {!draft.trim() && <p className="text-meta text-ink-muted">Add text to review it.</p>}
            </div>
          )}
        </>
      )}

      {(phase === "uploading" || phase === "transcribing" || phase === "assessing") && (
        <div className="card" aria-busy="true">
          <p className="font-semibold">{phase === "uploading" ? "Uploading. Assessment has not started." : phase === "transcribing" ? "Turning your recording into text. You will check it first." : "Checking the ideas against this task's rubric."}</p>
          {slow && <p className="mt-2 text-meta">This is taking longer than usual. You can wait, or save and leave — nothing is lost.</p>}
          <button className="btn-primary mt-4" disabled>{phase === "uploading" ? "Uploading" : phase === "transcribing" ? "Preparing text" : "Assessing"}</button>
        </div>
      )}

      {phase === "confirmation" && version && (
        <div className="space-y-4" data-phase="transcript-confirmation">
          <p className="font-semibold">Check names, numbers, and meaning. Unclear words are not mistakes in understanding.</p>
          {original && (
            <div className="rounded-detail border border-border bg-canvas p-3">
              <p className="text-meta text-ink-muted">{original.source_label}</p>
              {original.source_label?.startsWith("Demo") && <div className="mt-1"><SimulatedLabel label="Demo transcription" /></div>}
              <p className="mt-2">{original.text}</p>
            </div>
          )}
          {take?.playable && <audio controls src={`/api/audio/${take.id}`} className="w-full" aria-label="Your recording" />}
          <div>
            <label htmlFor="ex-edit" className="label">{original ? "Corrected text (what you meant)" : "Your text"}</label>
            <textarea id="ex-edit" ref={editRef} className="field !min-h-[160px]" value={edited} onChange={(e) => setEdited(e.target.value)} />
          </div>
          {(version.unresolved || []).length > 0 && (
            <fieldset className="rounded-detail border border-border p-3">
              <legend className="font-semibold">Possibly unclear words</legend>
              {(version.unresolved || []).map((u: any) => (
                <label key={u.id} className="flex min-h-[44px] items-center gap-2">
                  <input type="checkbox" checked={resolved.includes(u.id) || !edited.includes(u.text)}
                    disabled={!edited.includes(u.text)}
                    onChange={(e) => setResolved(e.target.checked ? [...resolved, u.id] : resolved.filter((x) => x !== u.id))} />
                  “{u.text}” is what I meant {!edited.includes(u.text) && <span className="text-meta text-ink-muted">(edited away)</span>}
                </label>
              ))}
              {unresolved.length > 0 && (
                <label className="mt-2 flex min-h-[44px] items-center gap-2"><input type="checkbox" checked={keepUnclear} onChange={(e) => setKeepUnclear(e.target.checked)} />
                  Keep the remaining words as unclear (anything depending on them stays unscored)</label>
              )}
            </fieldset>
          )}
          <div>
            <label htmlFor="ex-supp" className="label">Add reasoning (optional)</label>
            <textarea id="ex-supp" className="field !min-h-[80px]" value={supplement} onChange={(e) => setSupplement(e.target.value)} aria-describedby="supp-hint" />
            <p id="supp-hint" className="text-meta text-ink-muted">Kept separate from your recording and labeled as added reasoning.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={confirm} disabled={!edited.trim() || (unresolved.length > 0 && !keepUnclear)}>Confirm and assess</button>
            <button className="btn-secondary" onClick={() => editRef.current?.focus()}>Edit text</button>
            {take?.playable && <button className="btn-secondary" onClick={deleteAudio}>Delete audio now</button>}
          </div>
        </div>
      )}

      {phase === "feedback" && a && (
        <div className="space-y-4" data-phase="explanation-feedback">
          <h3 className="text-section">What this answer showed, and what remains uncertain</h3>
          {task.last_attempt?.response_text && (
            <details className="rounded-detail border border-border p-3"><summary className="cursor-pointer font-semibold">Your confirmed text</summary>
              <p className="mt-2">{task.last_attempt.response_text}</p>
              {task.last_attempt.supplement_text && <p className="mt-2 text-meta">Added reasoning: {task.last_attempt.supplement_text}</p>}
            </details>
          )}
          <RubricFeedback assessment={a} subjectId={subjectId} />
          {take && take.status === "deleted" && <p className="text-meta text-ink-muted">Audio deleted; transcript history remains.</p>}
          {next(a)}
        </div>
      )}
    </section>
  );
}
