"""Stopping rules: the diagnostic stops at the first of these."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from thinkfirst.domain.diagnostic.inference import SkillState
from thinkfirst.domain.diagnostic.selection import is_classified
from thinkfirst.domain.knowledge.graph import SkillGraph


class StopReason(StrEnum):
    ALL_CLASSIFIED = "all_classified"   # every key skill has P(L) < 0.2 or > 0.8
    MAX_ITEMS = "max_items"             # 12 items answered
    MAX_TIME = "max_time"               # 10 minutes reached
    FATIGUE = "fatigue"                 # frustration/disengagement: stop early, profile marked low confidence
    NO_ITEMS = "no_items"               # item bank exhausted
    MANUAL = "manual"                   # the student (or the app) ended it


@dataclass(frozen=True)
class StopConfig:
    max_items: int = 12
    max_ms: int = 600_000
    min_items: int = 5                  # never stop on classification before this many answers
    low: float = 0.2
    high: float = 0.8
    min_evidence: int = 2


def check_stop(graph: SkillGraph, states: dict[str, SkillState], n_items: int, elapsed_ms: int, fatigue: bool,
               cfg: StopConfig) -> StopReason | None:
    if fatigue:
        return StopReason.FATIGUE
    key = [s.id for s in graph.skills if s.is_key]
    if (n_items >= cfg.min_items and key
            and all(is_classified(states[sid], cfg.low, cfg.high, cfg.min_evidence) for sid in key)):
        return StopReason.ALL_CLASSIFIED
    if n_items >= cfg.max_items:
        return StopReason.MAX_ITEMS
    if elapsed_ms >= cfg.max_ms:
        return StopReason.MAX_TIME
    return None
