import { describe, expect, it } from "vitest";
import { autoDirect, parseScript, SCRIPTS, speakable, toSegments } from "./director";
import { personaFor, PERSONAS } from "./rig";

describe("TeacherAvatar director & persona transcription", () => {
  it("selects the right scientist persona from subject/concept hints", () => {
    expect(personaFor("Algebra — Linear equations")).toBe("khwarizmi");
    expect(personaFor("Expand 3(2x + 5)")).toBe("khwarizmi");
    expect(personaFor("Chemistry and atomic reactions")).toBe("curie");
    expect(personaFor("Relativity and photon energy E = mc^2")).toBe("einstein");
    expect(personaFor("Classical mechanics and motion")).toBe("newton");
    expect(Object.keys(PERSONAS)).toEqual(["newton", "einstein", "curie", "khwarizmi"]);
  });

  it("converts math symbols and exponents into natural spoken words", () => {
    const s = speakable("Expand 3 × x³ ÷ √y and E = mc²");
    expect(s).toContain("times");
    expect(s).toContain("cubed");
    expect(s).toContain("divided by");
    expect(s).toContain("square root of");
    expect(s).toContain("squared");
  });

  it("parses inline stage tags ([bow], [board: ...], [point], [celebrate]) into avatar segments", () => {
    const segs = parseScript(SCRIPTS.khwarizmi);
    expect(segs.length).toBeGreaterThan(2);
    expect(segs[0].gestures).toContain("bow");
    expect(segs.some((s) => s.board && s.board.includes("3x + 5 = 20"))).toBe(true);
    expect(segs.some((s) => s.emotion === "proud" || s.gestures.includes("celebrate"))).toBe(true);
  });

  it("auto-directs plain system-generated text with equations, questions, and feedback into speaking avatar beats", () => {
    const systemText =
      "Hello! Look at the expression 2(x + 5) = 2x + 10. Why does the factor 2 multiply both terms inside the brackets? Well done — your reasoning is solid.";
    const segs = autoDirect(systemText, "khwarizmi");
    expect(segs.length).toBe(4);
    expect(segs[0].gestures).toContain("wave");
    // Equation extracted onto the floating board with a point gesture
    expect(segs[1].board).toBeTruthy();
    expect(segs[1].gestures).toContain("point");
    // Question triggers thinking emotion & gesture
    expect(segs[2].emotion).toBe("thinking");
    expect(segs[2].gestures).toContain("think");
    // Positive feedback triggers encouraging emotion
    expect(segs[3].emotion).toBe("encouraging");
  });

  it("auto-Choose mode in toSegments picks parseScript for tagged scripts and autoDirect for plain text", () => {
    const tagged = toSegments("[wave] Welcome! [board: F = m a] Force equals mass times acceleration.", "newton");
    expect(tagged[0].gestures).toContain("wave");
    expect(tagged[0].board).toBe("F = m a");

    const plain = toSegments("Why does the apple fall toward the ground? Because gravity pulls masses together.", "newton");
    expect(plain.length).toBe(2);
    expect(plain[0].gestures).toContain("apple");
  });
});
