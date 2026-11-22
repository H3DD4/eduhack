"""Learner model per (track, concept): Elo rating + BKT mastery + spaced review dates.

"The LLM talks, models measure": these numbers decide levels, priorities and when a skill is earned.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any


# --------------------------------------------------------------------------------------------- Elo
def elo_expected(student: float, item: float) -> float:
    return 1.0 / (1.0 + 10 ** ((item - student) / 400.0))


def elo_update(student: float, item: float, score: float, *, k_student: float = 32, k_item: float = 12) -> tuple[float, float]:
    e = elo_expected(student, item)
    return student + k_student * (score - e), item - k_item * (score - e)


def item_for_success(student: float, p: float = 0.7) -> float:
    """Item difficulty that the student solves with probability p (70 % practice, 50 % diagnostic)."""
    return student - 400 * math.log10(p / (1 - p))


# --------------------------------------------------------------------------------------------- BKT
BKT = {"p_init": 0.2, "p_learn": 0.15, "p_slip": 0.1, "p_guess": 0.2}


def bkt_update(p: float, correct: bool, *, help_level: int = 0, guess: float | None = None) -> float:
    slip, g, learn = BKT["p_slip"], guess if guess is not None else BKT["p_guess"], BKT["p_learn"]
    if help_level >= 3:          # heavy help: a correct answer says little about mastery
        g = min(0.6, g + 0.25)
    if correct:
        post = p * (1 - slip) / (p * (1 - slip) + (1 - p) * g)
    else:
        post = p * slip / (p * slip + (1 - p) * (1 - g))
    return post + (1 - post) * learn * (0.5 if help_level >= 3 else 1.0)


# --------------------------------------------------------------------------------------------- reviews
def next_interval(prev_days: float, score: float, help_level: int) -> float:
    """FSRS-lite: grow on clean success, shrink on failure or heavy help."""
    if score < 0.5:
        return 1.0
    if help_level >= 3:
        return max(1.0, prev_days)
    return 1.0 if prev_days <= 0 else min(60.0, prev_days * (2.5 if score >= 0.9 else 1.8))


def level_from_elo(elo: float) -> str:
    return "beginner" if elo < 1000 else "intermediate" if elo < 1200 else "advanced"


def update_concept(rec: dict[str, Any], *, score: float, item_difficulty: float, help_level: int = 0,
                   guess: float | None = None, today: date | None = None) -> tuple[dict[str, Any], float]:
    """Apply one graded attempt. Returns (updated record, updated item difficulty)."""
    today = today or datetime.now(UTC).date()
    # help discounts the evidence: level 2 -> 75 %, level 3 -> 50 %, level 4 -> no evidence of skill
    weight = {0: 1.0, 1: 1.0, 2: 0.75, 3: 0.5, 4: 0.0}.get(help_level, 0.0)
    elo_s, elo_i = elo_update(rec["elo"], item_difficulty, score, k_student=32 * weight + 4)
    rec["elo"] = round(elo_s, 1)
    rec["p_mastery"] = round(bkt_update(rec["p_mastery"], score >= 0.7, help_level=help_level, guess=guess), 4)
    rec["attempts"] += 1
    rec["correct"] += 1 if score >= 0.7 else 0
    rec["help_total"] += help_level
    rec["interval_days"] = next_interval(rec.get("interval_days", 0.0), score, help_level)
    rec["last_seen"] = today.isoformat()
    rec["next_review"] = (today + timedelta(days=round(rec["interval_days"]))).isoformat()
    return rec, round(elo_i, 1)


def new_record(track_id: str, owner_id: str, concept_key: str, elo: float) -> dict[str, Any]:
    return {"id": f"{track_id}:{concept_key}", "track_id": track_id, "owner_id": owner_id, "concept_key": concept_key,
            "elo": elo, "p_mastery": 0.2, "attempts": 0, "correct": 0, "help_total": 0, "last_seen": None,
            "next_review": None, "interval_days": 0.0}
