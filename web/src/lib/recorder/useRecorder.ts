"use client";
/* Browser capture adapter around the pure state machine.
   - Requests audio only after intentional activation; secure context + MediaRecorder required.
   - Elapsed capture time is a separate timer that excludes pauses (chunk count is not time).
   - 10 s without a command acknowledgement => stop tracks, keep late playable data, capture error.
   - Observable suspension (tab hidden) pauses; ended tracks finalize; never auto-resume.
   - Chunks are written to IndexedDB as they arrive for reload recovery. */
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { newKey } from "../api";
import { clearTake, loadTake, LocalTake, markFinalized, saveChunk } from "./localStore";
import { classifyError, initialRecState, pickMime, RecEvent, RecState, transition } from "./machine";

const ACK_TIMEOUT_MS = 10_000;

export function useRecorder(taskId: string) {
  const [state, dispatch] = useReducer((s: RecState, e: RecEvent) => transition(s, e), initialRecState);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [localSaved, setLocalSaved] = useState<"none" | "device" | "failed">("none");
  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const metaRef = useRef<LocalTake | null>(null);
  const seqRef = useRef(0);
  const timerRef = useRef<{ startedAt: number | null; acc: number }>({ startedAt: null, acc: 0 });
  const ackRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const clearAck = () => {
    if (ackRef.current) clearTimeout(ackRef.current);
    ackRef.current = null;
  };
  const armAck = () => {
    clearAck();
    ackRef.current = setTimeout(() => {
      stopTracks();
      const hasPartial = chunksRef.current.length > 0;
      if (hasPartial) finalizeBlob();
      dispatch({ type: "COMMAND_TIMEOUT", hasPartial });
    }, ACK_TIMEOUT_MS);
  };

  const tick = () => {
    const t = timerRef.current;
    setElapsedMs(t.acc + (t.startedAt ? performance.now() - t.startedAt : 0));
  };
  const pauseClock = () => {
    const t = timerRef.current;
    if (t.startedAt) t.acc += performance.now() - t.startedAt;
    t.startedAt = null;
    tick();
  };

  const finalizeBlob = useCallback(() => {
    const mime = metaRef.current?.mime || "audio/webm";
    const b = new Blob(chunksRef.current, { type: mime });
    if (b.size > 0) {
      setBlob(b);
      setBlobUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(b);
      });
    }
    if (metaRef.current) markFinalized({ ...metaRef.current, captureMs: timerRef.current.acc });
    return b;
  }, []);

  // Reload recovery: offer a take that was saved on this device.
  useEffect(() => {
    let alive = true;
    loadTake(taskId).then((found) => {
      if (!alive || !found || found.blob.size === 0) return;
      metaRef.current = found.meta;
      chunksRef.current = [found.blob];
      timerRef.current.acc = found.meta.captureMs || 0;
      setElapsedMs(found.meta.captureMs || 0);
      setBlob(found.blob);
      setBlobUrl(URL.createObjectURL(found.blob));
      setLocalSaved("device");
      dispatch({ type: "RECOVERED_DRAFT" });
    });
    return () => {
      alive = false;
    };
  }, [taskId]);

  const enable = useCallback(async () => {
    const supported = typeof window !== "undefined" && window.isSecureContext && !!navigator.mediaDevices?.getUserMedia &&
      typeof MediaRecorder !== "undefined";
    if (!supported) {
      dispatch({ type: "DENIED", cause: "unsupported" });
      return;
    }
    dispatch({ type: "ENABLE" });
    const slow = setTimeout(() => dispatch({ type: "PERMISSION_SLOW" }), 10_000);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      clearTimeout(slow);
      if (stateRef.current.phase !== "permission_pending") {
        stream.getTracks().forEach((t) => t.stop()); // stale/late grant cannot enter ready
        return;
      }
      streamRef.current = stream;
      stream.getAudioTracks().forEach((t) => (t.onended = () => onTrackEnded()));
      dispatch({ type: "GRANTED" });
    } catch (err) {
      clearTimeout(slow);
      dispatch({ type: "DENIED", cause: classifyError(err) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onTrackEnded = () => {
    const p = stateRef.current.phase;
    if (["recording", "paused", "pausing", "resuming"].includes(p)) {
      pauseClock();
      try {
        if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
      } catch { /* noop */ }
      const hasPartial = chunksRef.current.length > 0;
      if (hasPartial) finalizeBlob();
      dispatch({ type: "INTERRUPTED", hasPartial });
    } else if (p === "ready") {
      dispatch({ type: "INTERRUPTED", hasPartial: false });
    }
  };

  const start = useCallback(() => {
    if (stateRef.current.phase !== "ready" || !streamRef.current) return;
    const mime = pickMime((m) => MediaRecorder.isTypeSupported(m));
    let rec: MediaRecorder;
    try {
      rec = mime ? new MediaRecorder(streamRef.current, { mimeType: mime }) : new MediaRecorder(streamRef.current);
    } catch (err) {
      dispatch({ type: "START_FAILED", cause: classifyError(err) });
      return;
    }
    chunksRef.current = [];
    seqRef.current = 0;
    timerRef.current = { startedAt: null, acc: 0 };
    setBlob(null);
    metaRef.current = { taskId, takeKey: newKey(), mime: rec.mimeType || mime || "audio/webm", updatedAt: Date.now(), finalized: false, captureMs: 0 };
    rec.ondataavailable = async (ev) => {
      if (!ev.data || ev.data.size === 0) return;
      chunksRef.current.push(ev.data);
      const ok = metaRef.current ? await saveChunk({ ...metaRef.current, captureMs: timerRef.current.acc }, seqRef.current++, ev.data) : false;
      setLocalSaved(ok ? "device" : "failed");
    };
    rec.onstart = () => {
      clearAck();
      timerRef.current.startedAt = performance.now();
      dispatch({ type: "STARTED" });
    };
    rec.onpause = () => {
      clearAck();
      pauseClock();
      dispatch({ type: "PAUSED" });
    };
    rec.onresume = () => {
      clearAck();
      timerRef.current.startedAt = performance.now();
      dispatch({ type: "RESUMED" });
    };
    rec.onstop = () => {
      clearAck();
      pauseClock();
      const b = finalizeBlob();
      stopTracks(); // release input after finalization
      if (stateRef.current.phase === "finalizing") dispatch({ type: "FINALIZED", playable: b.size > 0 });
    };
    recRef.current = rec;
    dispatch({ type: "START" });
    armAck();
    rec.start(1000);
  }, [taskId, finalizeBlob, stopTracks]);

  const pause = useCallback(() => {
    if (stateRef.current.phase !== "recording") return;
    dispatch({ type: "PAUSE" });
    armAck();
    recRef.current?.pause();
  }, []);
  const resume = useCallback(() => {
    if (stateRef.current.phase !== "paused") return;
    dispatch({ type: "RESUME" });
    armAck();
    recRef.current?.resume();
  }, []);
  const finish = useCallback(() => {
    if (!["recording", "paused"].includes(stateRef.current.phase)) return;
    dispatch({ type: "FINISH" });
    armAck();
    recRef.current?.stop();
  }, []);
  const retake = useCallback(async () => {
    // New take revision; the previous local draft is replaced only now, deliberately.
    await clearTake(taskId);
    chunksRef.current = [];
    setBlob(null);
    setElapsedMs(0);
    dispatch({ type: "RETAKE" });
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      stream.getAudioTracks().forEach((t) => (t.onended = () => onTrackEnded()));
      dispatch({ type: "GRANTED" });
    } catch (err) {
      dispatch({ type: "DENIED", cause: classifyError(err) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);
  const retryMic = useCallback(() => {
    dispatch({ type: "RETRY_MIC" });
    enable();
  }, [enable]);

  // Observable suspension pauses capture; the student resumes explicitly.
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "hidden" && stateRef.current.phase === "recording") pause();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [pause]);

  useEffect(() => {
    if (state.phase !== "recording") return;
    const id = setInterval(tick, 500);
    return () => clearInterval(id);
  }, [state.phase]);

  // Stop stale grants and tracks on exit.
  useEffect(() => () => {
    clearAck();
    try {
      if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
    } catch { /* noop */ }
    stopTracks();
  }, [stopTracks]);

  const releaseForText = useCallback(() => {
    if (["recording", "paused"].includes(stateRef.current.phase)) finish();
    else stopTracks();
  }, [finish, stopTracks]);

  return {
    state, elapsedMs, blob, blobUrl, mime: metaRef.current?.mime || blob?.type || "audio/webm", localSaved,
    enable, start, pause, resume, finish, retake, retryMic, releaseForText, reviewPartial: () => dispatch({ type: "REVIEW_PARTIAL" }),
    clearLocal: () => clearTake(taskId), captureMs: () => Math.round(timerRef.current.acc),
  };
}
