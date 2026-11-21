"""Bayesian Knowledge Tracing (Corbett & Anderson, 1994), help-aware (Beck et al., 2008).

State: p = P(student knows the skill). Each scored answer is evidence:
    P(correct | known)   = 1 - slip
    P(correct | unknown) = guess            (guess_assisted when the student had help → help weakens the evidence)
Bayes gives the posterior; then the learning transition: p' = post + (1 - post) * learn.
Evidence weighting: post_w = w * post + (1 - w) * p   (w = 0 → the answer doesn't move belief).
"""

from __future__ import annotations

from thinkfirst.modules.adaptation.engine.schemas import BKTParams


def predict_correct(p: float, assisted: bool, prm: BKTParams) -> float:
    g = prm.guess_assisted if assisted else prm.guess
    return p * (1 - prm.slip) + (1 - p) * g


def posterior(p: float, correct: bool, assisted: bool, prm: BKTParams) -> float:
    g = prm.guess_assisted if assisted else prm.guess
    s = prm.slip
    if correct:
        return p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    return p * s / (p * s + (1 - p) * (1 - g))


def update(p: float, observation: float, assisted: bool, weight: float, prm: BKTParams) -> float:
    """observation: 1 = correct, 0 = incorrect, 0.5 = partial (mixture of both posteriors)."""
    post = observation * posterior(p, True, assisted, prm) + (1 - observation) * posterior(p, False, assisted, prm)
    post = weight * post + (1 - weight) * p
    return min(0.9999, max(0.0001, post + (1 - post) * prm.learn))
