"""Items, the Q-matrix (which skills each item needs) and the item bank quality rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from thinkfirst.domain.knowledge.graph import GraphError, SkillGraph

MAX_DIAGNOSTIC_MS = 90_000  # "answerable in under 90 seconds"


@dataclass(frozen=True)
class Item:
    id: str
    skills: tuple[str, ...]                      # Q-matrix row: often 1, sometimes 2-3
    difficulty: float = 1000.0                   # Elo
    typical_ms: int = 60_000                     # typical answer time (rapid-guess baseline)
    diagnostic: bool = False                     # part of the small, verified diagnostic set
    verified: bool = False                       # reference answer checked (math checker, tests or a human)
    generated: bool = False                      # AI-generated
    calibrated: bool = False                     # enough real answers to trust `difficulty`
    cross_checked: bool = False                  # generated item whose key an independent second pass reproduced
    n_answers: int = 0
    language: str = "en"
    # wrong option id -> misconception code: choosing it is evidence of that misconception, not just "wrong"
    misconceptions: Mapping[str, str] = field(default_factory=dict, compare=False)

    @property
    def misconception_codes(self) -> frozenset[str]:
        return frozenset(self.misconceptions.values())

    @property
    def eligible_for_diagnostic(self) -> bool:
        """Verified, quick, flagged. An uncalibrated generated item is only allowed once its key was independently
        cross-checked (the engine still halves its weight because its difficulty is only declared)."""
        if not (self.diagnostic and self.verified and self.skills):
            return False
        if self.generated and not self.calibrated and not self.cross_checked:
            return False
        return self.typical_ms <= MAX_DIAGNOSTIC_MS


@dataclass(frozen=True)
class QualityIssue:
    rule: str
    message: str
    item_id: str | None = None
    skill_id: str | None = None


class ItemBank:
    def __init__(self, items: Iterable[Item]):
        self._items: dict[str, Item] = {}
        for it in items:
            if it.id in self._items:
                raise GraphError(f"duplicate item {it.id!r}")
            if not it.skills:
                raise GraphError(f"item {it.id!r} needs at least one skill (Q-matrix row)")
            self._items[it.id] = it

    @property
    def items(self) -> list[Item]:
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def get(self, item_id: str) -> Item:
        return self._items[item_id]

    def for_skill(self, skill_id: str, *, diagnostic_only: bool = False) -> list[Item]:
        return [i for i in self._items.values() if skill_id in i.skills
                and (not diagnostic_only or i.eligible_for_diagnostic)]

    def q_matrix(self) -> dict[str, tuple[str, ...]]:
        return {i.id: i.skills for i in self._items.values()}

    def validate(self, graph: SkillGraph, *, min_items_per_key_skill: int = 2) -> list[QualityIssue]:
        """The item bank quality rules; an empty list means the bank is ready for a diagnostic."""
        issues: list[QualityIssue] = []
        for it in self._items.values():
            unknown = [s for s in it.skills if s not in graph]
            if unknown:
                issues.append(QualityIssue("q_matrix", f"item references unknown skills {unknown}", item_id=it.id))
            if it.diagnostic and not it.verified:
                issues.append(QualityIssue("verified_key", "diagnostic item without a verified reference answer", item_id=it.id))
            if it.diagnostic and it.generated and not it.calibrated and not it.cross_checked:
                issues.append(QualityIssue("generated_uncalibrated",
                                           "generated items stay out of the diagnostic until calibrated", item_id=it.id))
            if it.diagnostic and it.typical_ms > MAX_DIAGNOSTIC_MS:
                issues.append(QualityIssue("answer_time", "diagnostic items must be answerable in under 90 seconds", item_id=it.id))
        for s in graph.skills:
            if not s.is_key:
                continue
            n = len(self.for_skill(s.id, diagnostic_only=True))
            if n < min_items_per_key_skill:
                issues.append(QualityIssue(
                    "min_items_per_key_skill",
                    f"{n} eligible diagnostic item(s); one item alone can be a slip or a guess "
                    f"(need {min_items_per_key_skill})", skill_id=s.id))
        return issues
