"""Bayesian Knowledge Tracing: P(L) = probability the student has mastered one skill."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    p_init: float = 0.30      # prior mastery before any evidence
    p_transit: float = 0.10   # chance to learn the skill between two practice opportunities
    p_slip: float = 0.10      # knows the skill but answers wrong
    p_guess: float = 0.20     # does not know the skill but answers right


def posterior(p_l: float, correct: bool, params: BKTParams) -> float:
    if correct:
        num = p_l * (1.0 - params.p_slip)
        den = num + (1.0 - p_l) * params.p_guess
    else:
        num = p_l * params.p_slip
        den = num + (1.0 - p_l) * (1.0 - params.p_guess)
    return num / den if den > 0 else p_l


def update(p_l: float, correct: bool, params: BKTParams, *, weight: float = 1.0, learn: bool = False) -> float:
    """Evidence update. `weight` < 1 blends the posterior with the prior (rapid guesses count for little).

    The diagnostic measures a fixed state (`learn=False`); practice sessions pass `learn=True` to add the
    chance the student learned something from the attempt.
    """
    post = p_l + max(0.0, min(1.0, weight)) * (posterior(p_l, correct, params) - p_l)
    if learn:
        post = post + (1.0 - post) * params.p_transit
    return min(1.0, max(0.0, post))
