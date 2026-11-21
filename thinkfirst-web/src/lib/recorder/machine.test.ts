import { describe, expect, it } from "vitest";
import { classifyError, ctas, initialRecState, pickMime, RecEvent, RecState, transition } from "./machine";

const run = (events: RecEvent[], from: RecState = initialRecState) => events.reduce(transition, from);

describe("recorder state machine (blueprint audio phase table)", () => {
  it("happy path with acknowledged commands", () => {
    const s = run([{ type: "ENABLE" }, { type: "GRANTED" }, { type: "START" }, { type: "STARTED" },
      { type: "PAUSE" }, { type: "PAUSED" }, { type: "RESUME" }, { type: "RESUMED" }, { type: "FINISH" },
      { type: "FINALIZED", playable: true }]);
    expect(s.phase).toBe("playback");
  });

  it("ignored permission prompt never becomes denial", () => {
    const s = run([{ type: "ENABLE" }, { type: "PERMISSION_SLOW" }]);
    expect(s).toEqual({ phase: "permission_pending", slow: true });
    expect(ctas(s).secondary).toBe("Use text");
  });

  it("denied / missing / busy devices map to cause-specific blocked states", () => {
    expect(classifyError({ name: "NotAllowedError" })).toBe("denied");
    expect(classifyError({ name: "NotFoundError" })).toBe("not_found");
    expect(classifyError({ name: "NotReadableError" })).toBe("hardware");
    const s = run([{ type: "ENABLE" }, { type: "DENIED", cause: "denied" }]);
    expect(s).toEqual({ phase: "blocked", cause: "denied" });
    expect(ctas(s).primary).toBe("Use text");
    expect(transition(s, { type: "RETRY_MIC" }).phase).toBe("permission_pending");
  });

  it("unsupported context disables retry", () => {
    const s = run([{ type: "DENIED", cause: "unsupported" }]);
    expect(ctas(s).secondary).toBeNull();
    expect(transition(s, { type: "RETRY_MIC" })).toBe(s);
  });

  it("rapid duplicate commands produce one transition", () => {
    const ready = run([{ type: "ENABLE" }, { type: "GRANTED" }]);
    const s = run([{ type: "START" }, { type: "START" }, { type: "START" }], ready);
    expect(s.phase).toBe("starting");
    expect(run([{ type: "STARTED" }, { type: "STARTED" }], s).phase).toBe("recording");
    const pausing = run([{ type: "STARTED" }, { type: "PAUSE" }, { type: "PAUSE" }, { type: "FINISH" }], s);
    expect(pausing.phase).toBe("pausing"); // finish while a pause is pending is ignored
  });

  it("unacknowledged command times out into recoverable capture error", () => {
    const rec = run([{ type: "ENABLE" }, { type: "GRANTED" }, { type: "START" }, { type: "STARTED" }, { type: "PAUSE" }]);
    const s = transition(rec, { type: "COMMAND_TIMEOUT", hasPartial: true });
    expect(s).toEqual({ phase: "capture_error", reason: "timeout", hasPartial: true });
    expect(transition(s, { type: "REVIEW_PARTIAL" }).phase).toBe("playback");
  });

  it("interruption never auto-resumes and empty takes are not playable", () => {
    const rec = run([{ type: "ENABLE" }, { type: "GRANTED" }, { type: "START" }, { type: "STARTED" }]);
    const s = transition(rec, { type: "INTERRUPTED", hasPartial: false });
    expect(s.phase).toBe("capture_error");
    expect(transition(s, { type: "RESUMED" })).toBe(s);
    expect(transition(s, { type: "REVIEW_PARTIAL" })).toBe(s);
    const fin = run([{ type: "FINISH" }, { type: "FINALIZED", playable: false }], rec);
    expect(fin).toEqual({ phase: "capture_error", reason: "empty", hasPartial: false });
  });

  it("reload recovery of a device-saved take goes to playback only from intent", () => {
    expect(transition(initialRecState, { type: "RECOVERED_DRAFT" })).toEqual({ phase: "playback", recovered: true });
  });

  it("negotiates supported MIME instead of assuming one", () => {
    expect(pickMime((m) => m === "audio/mp4")).toBe("audio/mp4");
    expect(pickMime(() => false)).toBeNull();
  });
});
