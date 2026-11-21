"""DiagnosticEngine: one pure, in-memory adaptive session.

    engine = DiagnosticEngine(graph, bank, theta=prior_theta("university", "exam"))
    while (item := engine.next_item()) is not None:
        ... show the item, collect confidence (1-5) first, then the answer ...
        engine.submit(Answer(item.id, correct=..., duration_ms=..., confidence=...))
    profile = engine.finish()

Steps (design doc, "How each step works"): prior -> select skill -> select item -> answer -> check -> update
(BKT + Elo + graph inference) -> adaptive moves. No help is available on diagnostic items, and the caller is
responsible for grading against a verified key before calling `submit`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace

from thinkfirst.domain.diagnostic.inference import SkillState, spread
from thinkfirst.domain.diagnostic.profile import AnswerRecord, InitialProfile, build_profile
from thinkfirst.domain.diagnostic.selection import (
    select_closing_item,
    select_first_item,
    select_item,
    select_skill,
)
from thinkfirst.domain.diagnostic.stopping import StopConfig, StopReason, check_stop
from thinkfirst.domain.knowledge.graph import SkillGraph
from thinkfirst.domain.knowledge.qmatrix import Item, ItemBank
from thinkfirst.domain.mastery import bkt, elo
from thinkfirst.domain.tracking import indicators as ind


@dataclass(frozen=True)
class DiagnosticConfig:
    stop: StopConfig = field(default_factory=StopConfig)
    bkt_params: bkt.BKTParams = field(default_factory=bkt.BKTParams)
    elo_k: float = 32.0
    inference_strength: float = 0.3
    inference_decay: float = 0.5
    rapid_guess_weight: float = 0.2     # a rapid guess counts for little
    uncalibrated_weight: float = 0.5    # items with unknown difficulty count for less


@dataclass(frozen=True)
class Answer:
    item_id: str
    correct: bool                       # graded by the caller against a verified key
    duration_ms: int
    confidence: int | None = None       # 1-5, rated before answering
    dont_know: bool = False             # counts as "not mastered", not as a blind guess
    misconception: str | None = None    # code of the misconception behind the chosen wrong option
    response_len: int | None = None
    negative_words: int = 0
    focus_switches: int = 0
    pause_ms: int = 0


@dataclass(frozen=True)
class AnswerOutcome:
    item_id: str
    weight: float
    rapid_guess: bool
    stop_reason: StopReason | None
    followup_scheduled: bool = False


class DiagnosticEngine:
    def __init__(self, graph: SkillGraph, bank: ItemBank, *, theta: float = elo.DEFAULT_THETA,
                 config: DiagnosticConfig | None = None):
        self.graph = graph
        self.cfg = config or DiagnosticConfig()
        self.theta = theta
        self.states: dict[str, SkillState] = {s.id: SkillState(s.id, self.cfg.bkt_params.p_init) for s in graph.skills}
        self._eligible: list[Item] = [i for i in bank.items
                                      if i.eligible_for_diagnostic and all(s in graph for s in i.skills)]
        self._asked: set[str] = set()
        self._records: list[AnswerRecord] = []
        self._obs: list[ind.Observation] = []
        self._misconceptions: Counter[tuple[str, str]] = Counter()
        self._followup: tuple[str, str] | None = None
        self._followed_up: set[tuple[str, str]] = set()
        self._closing_tried = False
        self._closing: Item | None = None
        self._current: Item | None = None
        self._elapsed_ms = 0
        self._stop: StopReason | None = None

    # ---- state ----
    @property
    def stop_reason(self) -> StopReason | None:
        return self._stop

    @property
    def finished(self) -> bool:
        return self._stop is not None

    @property
    def n_items(self) -> int:
        return len(self._records)

    # ---- choosing ----
    def _unasked(self, skill_id: str | None = None) -> list[Item]:
        return [i for i in self._eligible if i.id not in self._asked and (skill_id is None or skill_id in i.skills)]

    def next_item(self) -> Item | None:
        if self._stop is not None:
            return None
        if self._current is not None:
            return self._current  # not answered yet: same item
        item = self._pick()
        if item is None:
            self._stop = StopReason.NO_ITEMS
            return None
        self._current = item
        return item

    def _pick(self) -> Item | None:
        if self._closing is not None:
            item, self._closing = self._closing, None
            return item
        if self._followup is not None:
            skill_id, code = self._followup
            self._followup = None
            pool = self._unasked(skill_id)
            confirm = [i for i in pool if code in i.misconception_codes]
            picked = select_item(confirm or pool, self.theta)  # one follow-up item to confirm the misconception
            if picked is not None:
                return picked
        if not self._records:
            return select_first_item(self._unasked(), self.graph)
        s = self.cfg.stop
        available = {sid for i in self._unasked() for sid in i.skills}
        skill = select_skill(self.graph, self.states, available, low=s.low, high=s.high, min_evidence=s.min_evidence)
        if skill is None:  # everything classified or nothing left to ask about: fall back to any unasked item
            return select_item(self._unasked(), self.theta)
        return select_item(self._unasked(skill.id), self.theta)

    # ---- answering ----
    def submit(self, answer: Answer) -> AnswerOutcome:
        if self._stop is not None:
            raise RuntimeError("The diagnostic is finished.")
        item = self._current
        if item is None or item.id != answer.item_id:
            raise ValueError("Answer does not match the item last returned by next_item().")
        cfg = self.cfg
        obs = ind.Observation(correct=answer.correct and not answer.dont_know, duration_ms=answer.duration_ms,
                              typical_ms=item.typical_ms, confidence=answer.confidence,
                              response_len=answer.response_len, negative_words=answer.negative_words,
                              focus_switches=answer.focus_switches, pause_ms=answer.pause_ms)
        rapid = ind.is_rapid_guess(obs) and not answer.dont_know
        correct = bool(obs.correct)

        weight = cfg.rapid_guess_weight if rapid else 1.0
        if not item.calibrated:
            weight *= cfg.uncalibrated_weight
        params = replace(cfg.bkt_params, p_guess=0.0) if answer.dont_know else cfg.bkt_params  # "I don't know" = not mastered

        for sid in item.skills:  # the Q-matrix row: one answer updates several skills
            st = self.states[sid]
            self.states[sid] = replace(st, p_l=bkt.update(st.p_l, correct, params, weight=weight),
                                       n=st.n + (0 if rapid else 1), rapid=st.rapid + int(rapid), inferred=False)
        for sid in item.skills:  # graph inference spreads the evidence
            self.states = spread(self.graph, self.states, sid, correct, strength=cfg.inference_strength * weight,
                                 decay=cfg.inference_decay)
        self.theta = elo.update_theta(self.theta, item.difficulty, correct, k=cfg.elo_k, weight=weight)

        followup = False
        if answer.misconception and not correct:
            key = (answer.misconception, item.skills[0])
            self._misconceptions[key] += 1
            if key not in self._followed_up:
                self._followed_up.add(key)
                self._followup, followup = (item.skills[0], answer.misconception), True

        self._asked.add(item.id)
        self._current = None
        self._elapsed_ms += max(0, answer.duration_ms)
        self._obs.append(obs)
        self._records.append(AnswerRecord(item.id, item.skills, correct, answer.dont_know, rapid, answer.duration_ms,
                                          item.typical_ms, answer.confidence, answer.misconception))

        fatigue = ind.frustration_risk(self._obs).active or ind.disengagement(self._obs).active
        reason = check_stop(self.graph, self.states, self.n_items, self._elapsed_ms, fatigue, cfg.stop)
        if reason is StopReason.ALL_CLASSIFIED and not correct and not self._closing_tried:
            # End on a success: one more item the student is likely to solve, if the budget allows.
            self._closing_tried = True
            closing = select_closing_item(self._unasked(), self.states, self.theta)
            if closing is not None and self.n_items < cfg.stop.max_items:
                self._closing, reason = closing, None
        self._stop = reason
        return AnswerOutcome(item.id, weight, rapid, reason, followup)

    def stop(self) -> None:
        """End early (the student quits): the profile is marked low confidence."""
        if self._stop is None:
            self._stop = StopReason.MANUAL
        self._current = None

    def finish(self) -> InitialProfile:
        reason = self._stop or StopReason.MANUAL
        return build_profile(self.graph, self.states, self.theta, self._records, dict(self._misconceptions), reason,
                             self.cfg.stop)
