/* Recorder state machine — blueprint "Audio explain back" phase table (capture phases).
   Pure: no browser APIs, so every transition is unit-tested (machine.test.ts).
   Rules: commands are acknowledged before entering the next state; duplicate commands while a command is
   pending are ignored; interruptions never auto-resume; no empty take is ever playable/graded. */

export type BlockCause = "denied" | "not_found" | "hardware" | "unsupported";

export type RecState =
  | { phase: "permission_intent" }
  | { phase: "permission_pending"; slow: boolean }
  | { phase: "blocked"; cause: BlockCause }
  | { phase: "ready" }
  | { phase: "starting" }
  | { phase: "recording" }
  | { phase: "pausing" }
  | { phase: "paused" }
  | { phase: "resuming" }
  | { phase: "finalizing" }
  | { phase: "capture_error"; reason: "interrupted" | "empty" | "timeout"; hasPartial: boolean }
  | { phase: "playback"; recovered?: boolean };

export type RecEvent =
  | { type: "ENABLE" }
  | { type: "PERMISSION_SLOW" }
  | { type: "GRANTED" }
  | { type: "DENIED"; cause: BlockCause }
  | { type: "RETRY_MIC" }
  | { type: "START" }
  | { type: "STARTED" }
  | { type: "START_FAILED"; cause: BlockCause }
  | { type: "PAUSE" }
  | { type: "PAUSED" }
  | { type: "RESUME" }
  | { type: "RESUMED" }
  | { type: "FINISH" }
  | { type: "FINALIZED"; playable: boolean }
  | { type: "INTERRUPTED"; hasPartial: boolean }
  | { type: "COMMAND_TIMEOUT"; hasPartial: boolean }
  | { type: "REVIEW_PARTIAL" }
  | { type: "RETAKE" }
  | { type: "RECOVERED_DRAFT" };

export const initialRecState: RecState = { phase: "permission_intent" };

export function transition(s: RecState, e: RecEvent): RecState {
  switch (s.phase) {
    case "permission_intent":
      if (e.type === "ENABLE") return { phase: "permission_pending", slow: false };
      if (e.type === "DENIED") return { phase: "blocked", cause: e.cause };
      if (e.type === "RECOVERED_DRAFT") return { phase: "playback", recovered: true };
      return s;
    case "permission_pending":
      if (e.type === "PERMISSION_SLOW") return { ...s, slow: true }; // never infer denial from silence
      if (e.type === "GRANTED") return { phase: "ready" };
      if (e.type === "DENIED") return { phase: "blocked", cause: e.cause };
      return s;
    case "blocked":
      if (e.type === "RETRY_MIC" && s.cause !== "unsupported") return { phase: "permission_pending", slow: false };
      return s;
    case "ready":
      if (e.type === "START") return { phase: "starting" };
      if (e.type === "INTERRUPTED") return { phase: "permission_intent" }; // stale grant: cannot stay ready
      return s;
    case "starting":
      if (e.type === "STARTED") return { phase: "recording" };
      if (e.type === "START_FAILED") return { phase: "blocked", cause: e.cause };
      if (e.type === "COMMAND_TIMEOUT") return { phase: "capture_error", reason: "timeout", hasPartial: e.hasPartial };
      return s; // duplicate START ignored
    case "recording":
      if (e.type === "PAUSE") return { phase: "pausing" };
      if (e.type === "FINISH") return { phase: "finalizing" };
      if (e.type === "INTERRUPTED") return { phase: "capture_error", reason: "interrupted", hasPartial: e.hasPartial };
      return s;
    case "pausing":
      if (e.type === "PAUSED") return { phase: "paused" };
      if (e.type === "COMMAND_TIMEOUT") return { phase: "capture_error", reason: "timeout", hasPartial: e.hasPartial };
      if (e.type === "INTERRUPTED") return { phase: "capture_error", reason: "interrupted", hasPartial: e.hasPartial };
      return s;
    case "paused":
      if (e.type === "RESUME") return { phase: "resuming" };
      if (e.type === "FINISH") return { phase: "finalizing" };
      if (e.type === "INTERRUPTED") return { phase: "capture_error", reason: "interrupted", hasPartial: e.hasPartial };
      return s;
    case "resuming":
      if (e.type === "RESUMED") return { phase: "recording" };
      if (e.type === "COMMAND_TIMEOUT") return { phase: "capture_error", reason: "timeout", hasPartial: e.hasPartial };
      if (e.type === "INTERRUPTED") return { phase: "capture_error", reason: "interrupted", hasPartial: e.hasPartial };
      return s;
    case "finalizing":
      if (e.type === "FINALIZED") return e.playable ? { phase: "playback" } : { phase: "capture_error", reason: "empty", hasPartial: false };
      if (e.type === "COMMAND_TIMEOUT") return { phase: "capture_error", reason: "timeout", hasPartial: e.hasPartial };
      return s;
    case "capture_error":
      if (e.type === "REVIEW_PARTIAL" && s.hasPartial) return { phase: "playback" };
      if (e.type === "RETAKE") return { phase: "permission_pending", slow: false };
      return s;
    case "playback":
      if (e.type === "RETAKE") return { phase: "permission_pending", slow: false };
      return s;
  }
}

export function isCommandPending(s: RecState): boolean {
  return ["starting", "pausing", "resuming", "finalizing", "permission_pending"].includes(s.phase);
}

/** Primary / secondary CTA per phase (verbatim from the blueprint table). */
export function ctas(s: RecState): { primary: string; primaryDisabled: boolean; secondary: string | null } {
  switch (s.phase) {
    case "permission_intent": return { primary: "Enable microphone", primaryDisabled: false, secondary: "Use text" };
    case "permission_pending": return { primary: "Waiting", primaryDisabled: true, secondary: "Use text" };
    case "blocked": return { primary: "Use text", primaryDisabled: false, secondary: s.cause === "unsupported" ? null : "Try microphone again" };
    case "ready": return { primary: "Start recording", primaryDisabled: false, secondary: "Use text" };
    case "starting": return { primary: "Starting", primaryDisabled: true, secondary: "Stay here" };
    case "recording": return { primary: "Finish recording", primaryDisabled: false, secondary: "Pause" };
    case "pausing": return { primary: "Pausing", primaryDisabled: true, secondary: "Stay here" };
    case "paused": return { primary: "Resume", primaryDisabled: false, secondary: "Finish recording" };
    case "resuming": return { primary: "Resuming", primaryDisabled: true, secondary: "Stay here" };
    case "finalizing": return { primary: "Preparing playback", primaryDisabled: true, secondary: "Stay here" };
    case "capture_error": return { primary: s.hasPartial ? "Review captured part" : "Record again", primaryDisabled: false, secondary: s.hasPartial ? "Record again" : "Use text" };
    case "playback": return { primary: "Use recording", primaryDisabled: false, secondary: "Record another take" };
  }
}

export const BLOCK_COPY: Record<BlockCause, string> = {
  denied: "Microphone access is blocked here. Check browser/system settings, or use text.",
  not_found: "No matching microphone was found. Connect one or use text.",
  hardware: "The microphone could not be opened. Check your input device, then retry or use text.",
  unsupported: "Recording is unavailable in this browser or page. Use text.",
};

export function statusCopy(s: RecState): string {
  switch (s.phase) {
    case "permission_intent": return "Explain naturally. We assess your ideas, not your voice. Review the text before assessment.";
    case "permission_pending": return s.slow ? "Still waiting for a microphone choice. Text works too." : "Waiting for your microphone choice.";
    case "blocked": return BLOCK_COPY[s.cause];
    case "ready": return "Microphone connected. Recording has not started.";
    case "starting": return "Starting…";
    case "recording": return "Recording. Take your time.";
    case "pausing": return "Pausing…";
    case "paused": return "Paused; audio is not being added. The microphone connection remains open.";
    case "resuming": return "Resuming…";
    case "finalizing": return "Preparing your recording.";
    case "capture_error":
      if (s.reason === "empty") return "No playable audio was captured. Record another take or use text.";
      return s.hasPartial ? "Recording was interrupted. Review the captured part." : "Recording was interrupted and nothing playable was kept. Record again or use text.";
    case "playback": return s.recovered ? "We found a recording saved on this device. Listen if you wish, then check the transcript." : "Listen if you wish, then check the transcript.";
  }
}

export function classifyError(err: unknown): BlockCause {
  const name = (err as { name?: string })?.name || "";
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "not_found";
  if (name === "NotReadableError" || name === "AbortError") return "hardware";
  return "hardware";
}

export const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function pickMime(isSupported: (m: string) => boolean): string | null {
  return MIME_CANDIDATES.find((m) => isSupported(m)) ?? null;
}
