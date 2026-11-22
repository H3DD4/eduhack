import { describe, expect, it } from "vitest";
import { buildJourney, isAchieved } from "./RoadmapJourney";

function makeConcept(id: string, title: string, states: string[] = [], placement_status?: string) {
  return {
    id,
    key: id,
    title,
    prerequisites: [],
    evidence: { states, attempts: states.length },
    placement_status,
  };
}

describe("isAchieved", () => {
  it("treats applied_independently, recalled_later, and placement_status known as achieved", () => {
    expect(isAchieved(makeConcept("c1", "A", []))).toBe(false);
    expect(isAchieved(makeConcept("c2", "B", ["introduced", "practised_with_support", "explained"]))).toBe(false);
    expect(isAchieved(makeConcept("c3", "C", ["applied_independently"]))).toBe(true);
    expect(isAchieved(makeConcept("c4", "D", ["recalled_later"]))).toBe(true);
    expect(isAchieved(makeConcept("c5", "E", [], "known"))).toBe(true);
  });
});

describe("buildJourney", () => {
  it("returns an empty array for empty units", () => {
    expect(buildJourney([])).toEqual([]);
  });

  it("sets index 0 as current and locks later milestones across units on a fresh roadmap", () => {
    const units = [
      {
        unit_no: 1,
        title: "Unit 1",
        concepts: [makeConcept("c1", "First"), makeConcept("c2", "Second")],
        foundations: [],
      },
      {
        unit_no: 2,
        title: "Unit 2",
        concepts: [makeConcept("c3", "Third")],
        foundations: [],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.map((m) => [m.c.id, m.status, m.previous?.id ?? null])).toEqual([
      ["c1", "current", null],
      ["c2", "locked", "c1"],
      ["c3", "locked", "c2"],
    ]);
  });

  it("marks sequential achieved milestones done and advances current across unit boundaries", () => {
    const units = [
      {
        unit_no: 1,
        title: "Unit 1",
        concepts: [
          makeConcept("c1", "First", ["applied_independently"]),
          makeConcept("c2", "Second", ["recalled_later"]),
        ],
        foundations: [],
      },
      {
        unit_no: 2,
        title: "Unit 2",
        concepts: [makeConcept("c3", "Third", ["explained"]), makeConcept("c4", "Fourth")],
        foundations: [],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.map((m) => [m.c.id, m.status, m.achieved])).toEqual([
      ["c1", "done", true],
      ["c2", "done", true],
      ["c3", "current", false],
      ["c4", "locked", false],
    ]);
  });

  it("keeps out-of-order achieved milestones locked with achieved=true until earlier ones are done", () => {
    const units = [
      {
        unit_no: 1,
        title: "Unit 1",
        concepts: [
          makeConcept("c1", "First", ["practised_with_support"]),
          makeConcept("c2", "Second", ["applied_independently"]),
          makeConcept("c3", "Third", []),
        ],
        foundations: [],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.map((m) => [m.c.id, m.status, m.achieved])).toEqual([
      ["c1", "current", false],
      ["c2", "locked", true],
      ["c3", "locked", false],
    ]);
  });

  it("marks leading placement-known milestones done and locks later known milestones behind unknown ones", () => {
    const units = [
      {
        unit_no: 1,
        title: "Unit 1",
        concepts: [
          makeConcept("c1", "Known 1", [], "known"),
          makeConcept("c2", "Unknown", [], "to_learn"),
          makeConcept("c3", "Known Later", [], "known"),
        ],
        foundations: [],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.map((m) => [m.c.id, m.status, m.achieved])).toEqual([
      ["c1", "done", true],
      ["c2", "current", false],
      ["c3", "locked", true],
    ]);
  });

  it("marks every milestone done when all concepts are achieved", () => {
    const units = [
      {
        unit_no: 1,
        title: "Unit 1",
        concepts: [
          makeConcept("c1", "First", ["applied_independently"]),
          makeConcept("c2", "Second", ["recalled_later"]),
        ],
        foundations: [],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.every((m) => m.status === "done")).toBe(true);
  });

  it("ignores foundations in mixed units and falls back to foundations in foundation-only units", () => {
    const units = [
      {
        unit_no: 1,
        title: "Mixed",
        concepts: [makeConcept("c1", "Core 1")],
        foundations: [makeConcept("f1", "Foundation 1")],
      },
      {
        unit_no: 2,
        title: "Foundations Only",
        concepts: [],
        foundations: [makeConcept("f2", "Foundation 2"), makeConcept("f3", "Foundation 3")],
      },
    ];
    const journey = buildJourney(units);
    expect(journey.map((m) => [m.c.id, m.status])).toEqual([
      ["c1", "current"],
      ["f2", "locked"],
      ["f3", "locked"],
    ]);
  });
});
