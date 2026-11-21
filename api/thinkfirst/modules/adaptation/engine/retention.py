"""Retention, FSRS-style (simplified, documented). Stability S = days until recall probability falls to 90%.

    R(t) = (1 + t / (9 S))^-1                       — FSRS power forgetting curve (R(S) = 0.9)
    review due when R < threshold (default 0.85)    → due after t* = 9 S (1/threshold - 1) days
    unaided success after a real delay:  S' = S * (1 + g * (0.5 + 2 (1 - R)))   — harder recall grows S more
    unaided failure (lapse):             S' = max(S_min, S * lapse_factor)
Same-day repeats and assisted successes don't grow S (spacing effect; help isn't retention evidence).
py-fsrs can replace this module later without changing the JSON contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from thinkfirst.modules.adaptation.engine.schemas import EngineConfig


def days_between(a: datetime, b: datetime) -> float:
    return max(0.0, (b - a).total_seconds() / 86400)


def retrievability(stability: float, elapsed_days: float) -> float:
    return (1 + elapsed_days / (9 * stability)) ** -1


def after_success(stability: float, r: float, cfg: EngineConfig) -> float:
    return stability * (1 + cfg.stability_growth * (0.5 + 2 * (1 - r)))


def after_lapse(stability: float, cfg: EngineConfig) -> float:
    return max(cfg.min_stability_days, stability * cfg.lapse_factor)


def due_at(last_success: datetime, stability: float, cfg: EngineConfig) -> datetime:
    return last_success + timedelta(days=9 * stability * (1 / cfg.review_threshold_R - 1))
