"""Layer 3: derived indicators. Simple first rules from learning analytics, refined with real data later.

Indicators are probabilities with a confidence, never labels shown to the student: the student sees the effect
("let's try a shorter one"), not "you are frustrated". Nothing here infers health or mental-health state.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean

RAPID_GUESS_RATIO = 0.10   # answer faster than ~10% of the item's typical time (Wise & Kong: response-time effort)


@dataclass(frozen=True)
class Observation:
    """One item as seen by the tracking layer (built from events: answered, edited, requested_help, ...)."""

    correct: bool | None = None
    duration_ms: int = 0
    typical_ms: int = 60_000
    help_requests: int = 0
    edits: int = 0
    skipped: bool = False
    confidence: int | None = None      # 1-5, rated before seeing the result
    response_len: int | None = None
    negative_words: int = 0            # "I'm stupid", "I give up" in chat
    focus_switches: int = 0
    pause_ms: int = 0
    hour: int | None = None


@dataclass(frozen=True)
class Indicator:
    name: str
    active: bool
    score: float            # 0..1
    confidence: float       # 0..1: how much evidence backs the score
    reason: str = ""
    value: float | None = None


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def is_rapid_guess(obs: Observation, ratio: float = RAPID_GUESS_RATIO) -> bool:
    return obs.duration_ms > 0 and not obs.skipped and obs.duration_ms < ratio * obs.typical_ms


def rapid_guessing(obs: Observation, ratio: float = RAPID_GUESS_RATIO) -> Indicator:
    active = is_rapid_guess(obs, ratio)
    score = _clip(1.0 - obs.duration_ms / (ratio * obs.typical_ms)) if active else 0.0
    return Indicator("rapid_guessing", active, score, 0.6,
                     "answered in under 10% of the typical time" if active else "")


def gaming_the_system(recent: Sequence[Observation], window: int = 5, threshold: int = 3) -> Indicator:
    tail = list(recent)[-window:]
    help_no_attempt = sum(1 for o in tail if o.help_requests >= 1 and o.edits == 0 and o.duration_ms < 0.25 * o.typical_ms)
    rapid = sum(1 for o in tail if is_rapid_guess(o))
    hits = max(help_no_attempt, rapid)
    return Indicator("gaming_the_system", hits >= threshold, _clip(hits / window), _clip(len(tail) / window),
                     "help requested without real attempts, or answers cycled quickly" if hits >= threshold else "")


def help_avoidance(recent: Sequence[Observation], streak: int = 3) -> Indicator:
    tail = list(recent)[-streak:]
    active = len(tail) == streak and all(
        o.correct is False and o.help_requests == 0 and o.duration_ms > o.typical_ms for o in tail)
    return Indicator("help_avoidance", active, 1.0 if active else 0.0, _clip(len(tail) / streak),
                     "long struggle, several errors, never asked for help" if active else "")


def wheel_spinning(attempts: int, mastery_start: float, mastery_now: float, *, min_attempts: int = 10,
                   min_gain: float = 0.10) -> Indicator:
    gain = mastery_now - mastery_start
    active = attempts >= min_attempts and gain < min_gain
    return Indicator("wheel_spinning", active, _clip(1.0 - gain / min_gain) if active else 0.0,
                     _clip(attempts / (2 * min_attempts)),
                     f"{attempts} attempts without mastery rising: switch strategy or revisit a prerequisite" if active else "",
                     value=gain)


def productive_struggle(obs: Observation) -> Indicator:
    active = obs.correct is True and obs.duration_ms > 1.5 * obs.typical_ms and obs.edits >= 2
    return Indicator("productive_struggle", active, 1.0 if active else 0.0, 0.5,
                     "slow, several edits, then correct: raises the struggle-tolerance estimate" if active else "")


def frustration_risk(recent: Sequence[Observation], window: int = 5, threshold: float = 0.7) -> Indicator:
    tail = list(recent)[-window:]
    streak = 0
    for o in reversed(tail):
        if o.correct is False:
            streak += 1
        else:
            break
    score = 0.4 * min(streak, 3) / 3 + (0.3 if sum(o.negative_words for o in tail) > 0 else 0.0)
    lens = [o.response_len for o in tail if o.response_len is not None]
    if len(lens) >= 3 and lens[-1] < lens[0]:
        score += 0.3
    score = _clip(score)
    # Strongest evidence of all three: errors in a row + negative words + shorter answers.
    return Indicator("frustration_risk", score >= threshold, score, _clip(len(tail) / window),
                     "errors in a row, negative wording and shorter answers" if score >= threshold else "")


def disengagement(recent: Sequence[Observation], window: int = 6, threshold: float = 0.7) -> Indicator:
    tail = list(recent)[-window:]
    long_pauses = sum(1 for o in tail if o.pause_ms >= 60_000)
    switches = sum(o.focus_switches for o in tail)
    graded = [o.correct for o in tail if o.correct is not None]
    declining = False
    if len(graded) >= 4:
        half = len(graded) // 2
        declining = fmean(map(float, graded[half:])) < fmean(map(float, graded[:half]))
    score = _clip(0.4 * (long_pauses >= 2) + 0.3 * (switches >= 3) + 0.3 * declining)
    return Indicator("disengagement", score >= threshold, score, _clip(len(tail) / window),
                     "long pauses, focus switches and falling response quality" if score >= threshold else "")


def calibration(recent: Sequence[Observation], *, min_items: int = 3, gap_points: float = 20.0) -> Indicator:
    """Confidence vs. result gap in percentage points; positive means over-confident."""
    rated = [o for o in recent if o.confidence is not None and o.correct is not None]
    if len(rated) < min_items:
        return Indicator("calibration", False, 0.0, _clip(len(rated) / min_items), "not enough rated answers", value=None)
    confidence_pct = fmean((o.confidence - 1) / 4 * 100 for o in rated)  # type: ignore[operator]
    accuracy_pct = fmean(100.0 if o.correct else 0.0 for o in rated)
    gap = confidence_pct - accuracy_pct
    kind = "over-confident" if gap > 0 else "under-confident"
    return Indicator("calibration", abs(gap) >= gap_points, _clip(abs(gap) / 100), _clip(len(rated) / 10),
                     f"{kind} ({gap:+.0f} points)" if abs(gap) >= gap_points else "well calibrated", value=gap)


def best_study_hours(recent: Sequence[Observation], *, min_samples: int = 5, top: int = 2) -> list[tuple[int, float, int]]:
    """(hour, accuracy, samples) for the best hours with enough data; the Plan brain schedules key sessions there."""
    by_hour: dict[int, list[bool]] = defaultdict(list)
    for o in recent:
        if o.hour is not None and o.correct is not None:
            by_hour[o.hour].append(o.correct)
    scored = [(h, sum(v) / len(v), len(v)) for h, v in by_hour.items() if len(v) >= min_samples]
    return sorted(scored, key=lambda t: (-t[1], -t[2], t[0]))[:top]
