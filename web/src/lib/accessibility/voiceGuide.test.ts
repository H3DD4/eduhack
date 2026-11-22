import { describe, expect, it } from "vitest";
import { parseVoiceGuideIntent, voiceGuidePagePrompt } from "./voiceGuide";

describe("voice guide commands", () => {
  it("extracts a topic without treating generic learn requests as topic names", () => {
    expect(parseVoiceGuideIntent("I want to learn about calculus")).toEqual({ type: "learn", topic: "calculus" });
    expect(parseVoiceGuideIntent("learn biology")).toEqual({ type: "learn", topic: "biology" });
    expect(parseVoiceGuideIntent("I want to learn something new")).toEqual({ type: "navigate", href: "/subjects/new", label: "new subject" });
  });

  it("maps app navigation and step commands", () => {
    expect(parseVoiceGuideIntent("go to planner")).toEqual({ type: "navigate", href: "/planner", label: "Planner" });
    expect(parseVoiceGuideIntent("next")).toEqual({ type: "next" });
    expect(parseVoiceGuideIntent("choose exam")).toEqual({ type: "select", option: "exam" });
    expect(parseVoiceGuideIntent("focus email")).toEqual({ type: "focus", field: "email" });
    expect(parseVoiceGuideIntent("type student@example.com")).toEqual({ type: "type", value: "student@example.com" });
    expect(parseVoiceGuideIntent("click privacy and data")).toEqual({ type: "click", control: "privacy and data" });
  });

  it("provides route-specific, concise spoken guidance", () => {
    expect(voiceGuidePagePrompt("/subjects/new", "?topic=biology")).toContain("biology entered");
    expect(voiceGuidePagePrompt("/subjects/new")).toContain("choose files manually");
  });
});
