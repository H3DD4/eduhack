"""Elo ability (theta) and item difficulty, on the usual 400-point logistic scale.

    p = 1 / (1 + 10 ** ((d - theta) / 400))

The diagnostic picks the item that maximises p * (1 - p) (closest to 50% predicted success: one answer tells us
the most). Practice later targets ~70% instead, because there the goal is learning, not measuring.
"""

from __future__ import annotations

ELO_SCALE = 400.0
DEFAULT_THETA = 1000.0

# Starting theta from the student's level (onboarding step 5) and goal (step 4). Placeholders to calibrate.
LEVEL_PRIORS = {"middle_school": 900.0, "high_school": 1000.0, "university": 1100.0, "professional": 1100.0}
GOAL_ADJUSTMENT = {"exam": 0.0, "certification": 0.0, "mastery": 50.0}

# Author estimates (easy / medium / hard) used until real answers calibrate an item.
DIFFICULTY_PRIORS = {"easy": 900.0, "medium": 1100.0, "hard": 1300.0}


def prior_theta(level: str | None = None, goal: str | None = None) -> float:
    return LEVEL_PRIORS.get(level or "", DEFAULT_THETA) + GOAL_ADJUSTMENT.get(goal or "", 0.0)


def expected_success(theta: float, difficulty: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((difficulty - theta) / ELO_SCALE))


def item_information(p: float) -> float:
    """How much one answer tells us: maximal at p = 0.5."""
    return p * (1.0 - p)


def update_theta(theta: float, difficulty: float, correct: bool, *, k: float = 32.0, weight: float = 1.0) -> float:
    return theta + k * weight * ((1.0 if correct else 0.0) - expected_success(theta, difficulty))


def update_difficulty(difficulty: float, theta: float, correct: bool, *, k: float = 16.0, weight: float = 1.0) -> float:
    """An item answered correctly more often than expected is easier than we thought."""
    return difficulty - k * weight * ((1.0 if correct else 0.0) - expected_success(theta, difficulty))


def calibration_weight(n_answers: int, min_answers: int = 30) -> float:
    """Items with too few real answers stay 'uncalibrated' and count for less (0.5 .. 1.0)."""
    if min_answers <= 0:
        return 1.0
    return 0.5 + 0.5 * min(1.0, max(0, n_answers) / min_answers)
