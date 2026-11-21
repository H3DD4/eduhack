"""The initial profile the diagnostic hands to the tutor, the planner and the help ladder.

Every value carries its own confidence: a profile built from 10 answers is a starting estimate, not a verdict.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import fmean, median
from typing import Any

from thinkfirst.domain.diagnostic.inference import SkillState
from thinkfirst.domain.diagnostic.stopping import StopConfig, StopReason
from thinkfirst.domain.knowledge.graph import SkillGraph
from thinkfirst.domain.tracking import indicators as ind

FRONTIER_THRESHOLD = 0.7      # prerequisite counts as met above this P(L)
RAPID_RETEST_SHARE = 0.30     # retest if this share of answers were rapid guesses


@dataclass(frozen=True)
class AnswerRecord:
    item_id: str
    skills: tuple[str, ...]
    correct: bool
    dont_know: bool
    rapid_guess: bool
    duration_ms: int
    typical_ms: int
    confidence: int | None = None
    misconception: str | None = None


@dataclass(frozen=True)
class SkillMastery:
    skill_id: str
    p_l: float
    n: int
    inferred: bool
    status: str    # "mastered" | "not_mastered" | "uncertain"


@dataclass(frozen=True)
class MisconceptionEvidence:
    code: str
    skill_id: str
    count: int


@dataclass(frozen=True)
class InitialProfile:
    mastery: dict[str, SkillMastery]
    frontier: list[str]                                     # skills ready to learn next
    theta: float                                            # Elo ability for this subject
    expertise: dict[str, str]                               # chapter -> novice | intermediate | advanced
    misconceptions: list[MisconceptionEvidence]
    calibration_gap: float | None                           # points; positive = over-confident
    behavior_priors: dict[str, Any]
    data_quality: dict[str, Any]
    stop_reason: StopReason
    n_items: int
    low_confidence: bool
    needs_retest: bool
    notes: list[str] = field(default_factory=list)

    @property
    def evidence_note(self) -> str:
        return f"Based on {self.n_items} answers. This gets more accurate every session."

    def to_dict(self) -> dict[str, Any]:
        return {
            "mastery": {k: vars(v) for k, v in self.mastery.items()},
            "frontier": self.frontier, "theta": round(self.theta, 1), "expertise": self.expertise,
            "misconceptions": [vars(m) for m in self.misconceptions], "calibration_gap": self.calibration_gap,
            "behavior_priors": self.behavior_priors, "data_quality": self.data_quality,
            "stop_reason": self.stop_reason.value, "n_items": self.n_items, "low_confidence": self.low_confidence,
            "needs_retest": self.needs_retest, "evidence_note": self.evidence_note, "notes": self.notes,
        }


def _stage(mean_p: float) -> str:
    return "novice" if mean_p < 0.4 else "intermediate" if mean_p < 0.75 else "advanced"


def build_profile(graph: SkillGraph, states: dict[str, SkillState], theta: float, records: list[AnswerRecord],
                  misconceptions: dict[tuple[str, str], int], stop_reason: StopReason, stop: StopConfig) -> InitialProfile:
    mastery: dict[str, SkillMastery] = {}
    for s in graph.skills:
        st = states[s.id]
        status = "not_mastered" if st.p_l < stop.low else "mastered" if st.p_l > stop.high else "uncertain"
        mastery[s.id] = SkillMastery(s.id, round(st.p_l, 3), st.n, st.inferred and st.n == 0, status)

    mastered = [sid for sid, m in mastery.items() if m.p_l >= FRONTIER_THRESHOLD]
    by_chapter: dict[str, list[float]] = defaultdict(list)
    for s in graph.skills:
        by_chapter[s.chapter or "all"].append(states[s.id].p_l)

    obs = [ind.Observation(correct=r.correct, duration_ms=r.duration_ms, typical_ms=r.typical_ms,
                           confidence=r.confidence) for r in records]
    cal = ind.calibration(obs)
    n = len(records)
    rapid = sum(r.rapid_guess for r in records)
    rapid_share = rapid / n if n else 0.0
    priors = {
        "response_time_ratio": round(median(r.duration_ms / r.typical_ms for r in records), 2) if n else None,
        "dont_know_rate": round(sum(r.dont_know for r in records) / n, 2) if n else None,
        "struggle_tolerance": None,                 # needs edit signals: measured in practice sessions, not here
        "confidence": round(min(1.0, n / 12), 2),   # low until more sessions confirm it
    }
    notes: list[str] = []
    needs_retest = rapid_share >= RAPID_RETEST_SHARE
    if needs_retest:
        notes.append("Many answers looked like rapid guesses: retest early.")
    if stop_reason is StopReason.FATIGUE:
        notes.append("Stopped early; finish the measurement during the first sessions.")
    low_conf = stop_reason in (StopReason.FATIGUE, StopReason.NO_ITEMS, StopReason.MANUAL) or needs_retest
    return InitialProfile(
        mastery=mastery, frontier=graph.frontier(mastered), theta=theta,
        expertise={c: _stage(fmean(v)) for c, v in by_chapter.items()},
        misconceptions=[MisconceptionEvidence(code, sid, c) for (code, sid), c in sorted(misconceptions.items())],
        calibration_gap=round(cal.value, 1) if cal.value is not None else None,
        behavior_priors=priors,
        data_quality={"rapid_guesses": rapid, "answers": n, "rapid_share": round(rapid_share, 2)},
        stop_reason=stop_reason, n_items=n, low_confidence=low_conf, needs_retest=needs_retest, notes=notes)
