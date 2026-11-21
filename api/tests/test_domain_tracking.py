"""Pure domain: tracking schema, redaction by consent, derived indicators."""

from __future__ import annotations

import pytest

from thinkfirst.domain.consent.tiers import ConsentState, Tier
from thinkfirst.domain.tracking import indicators as ind
from thinkfirst.domain.tracking.events import EventError, TrackingEvent, Verb
from thinkfirst.domain.tracking.signals import SIGNAL_CATALOG, redact

SAMPLE = {
    "event_id": "evt_8f2c", "actor": "stu_42", "verb": "answered",
    "object": {"type": "item", "id": "maths_eq_017", "skills": ["isolate_unknown"]},
    "result": {"correct": False, "response": "x = 25/3", "misconception": "forgot_to_subtract", "duration_ms": 41200,
               "edits": 3},
    "context": {"session": "ses_91", "phase": "diagnostic", "help_level": 0, "confidence": 4, "device": "mobile",
                "locale": "fr", "focus_switches": 2},
    "timestamp": "2026-11-21T18:40:12Z",
}


def test_event_round_trip_matches_the_xapi_pattern():
    ev = TrackingEvent.from_dict(SAMPLE)
    assert ev.verb is Verb.ANSWERED and ev.actor == "stu_42"
    assert ev.to_dict() == SAMPLE


def test_event_validation_and_never_tracked():
    with pytest.raises(EventError, match="verb"):
        TrackingEvent.from_dict({**SAMPLE, "verb": "teleported"})
    with pytest.raises(EventError, match="pseudonymous"):
        TrackingEvent.from_dict({**SAMPLE, "actor": "me@example.com"})
    with pytest.raises(EventError, match="type"):
        TrackingEvent.from_dict({**SAMPLE, "object": {}})
    with pytest.raises(EventError, match="never tracked"):
        TrackingEvent.from_dict({**SAMPLE, "context": {**SAMPLE["context"], "location": {"lat": 1}}})
    with pytest.raises(EventError, match="never tracked"):
        TrackingEvent.from_dict({**SAMPLE, "result": {"nested": {"Keystrokes": "abc"}}})


def test_redaction_follows_consent_tiers():
    ev = TrackingEvent.from_dict(SAMPLE)
    base = ConsentState.default(birth_year=2000, current_year=2026)
    essential = redact(ev, base)
    assert essential is not None
    assert "edits" not in essential.result and "focus_switches" not in essential.context
    assert essential.result["correct"] is False and essential.context["confidence"] == 4

    full = redact(ev, base.grant(Tier.LEARNING_BEHAVIOR))
    assert full is not None and full.result["edits"] == 3 and full.context["focus_switches"] == 2

    edited = TrackingEvent.from_dict({**SAMPLE, "verb": "edited"})
    assert redact(edited, base) is None                                   # behavior verb needs the behavior tier
    assert redact(edited, base.grant(Tier.LEARNING_BEHAVIOR)) is not None

    minor = ConsentState.default(birth_year=2012, current_year=2026)
    assert redact(ev, minor) is None                                      # no personal data before guardian consent
    assert redact(ev, minor.with_guardian_consent()) is not None


def test_signal_catalog_covers_each_tier_used_by_redaction():
    assert len(SIGNAL_CATALOG) == 9
    assert {s.tier for s in SIGNAL_CATALOG} == {Tier.ESSENTIAL, Tier.LEARNING_BEHAVIOR}


def O(**kw):  # noqa: N802
    return ind.Observation(**kw)


def test_rapid_guessing():
    assert ind.is_rapid_guess(O(duration_ms=3_000, typical_ms=60_000))
    assert not ind.is_rapid_guess(O(duration_ms=20_000, typical_ms=60_000))
    assert not ind.is_rapid_guess(O(duration_ms=0))
    assert ind.rapid_guessing(O(duration_ms=1_000, typical_ms=60_000)).active


def test_gaming_help_avoidance_wheel_spinning_productive_struggle():
    quick_help = [O(help_requests=1, duration_ms=5_000)] * 3
    assert ind.gaming_the_system(quick_help).active
    assert not ind.gaming_the_system([O(correct=True, duration_ms=30_000)] * 5).active

    struggle = [O(correct=False, duration_ms=90_000)] * 3
    assert ind.help_avoidance(struggle).active
    assert not ind.help_avoidance([O(correct=False, duration_ms=90_000, help_requests=1)] * 3).active

    assert ind.wheel_spinning(10, 0.30, 0.33).active
    assert not ind.wheel_spinning(10, 0.30, 0.60).active
    assert not ind.wheel_spinning(4, 0.30, 0.30).active

    assert ind.productive_struggle(O(correct=True, duration_ms=100_000, edits=3)).active
    assert not ind.productive_struggle(O(correct=True, duration_ms=100_000, edits=0)).active


def test_frustration_and_disengagement():
    rough = [O(correct=False, response_len=40), O(correct=False, response_len=20),
             O(correct=False, response_len=5, negative_words=1)]
    assert ind.frustration_risk(rough).active
    assert not ind.frustration_risk([O(correct=False), O(correct=True), O(correct=False)]).active

    drifting = [O(correct=True), O(correct=True, pause_ms=90_000, focus_switches=2),
                O(correct=False, pause_ms=80_000, focus_switches=2), O(correct=False)]
    assert ind.disengagement(drifting).active
    assert not ind.disengagement([O(correct=True)] * 4).active


def test_calibration_and_best_hours():
    over = [O(correct=False, confidence=5)] * 2 + [O(correct=True, confidence=5)] * 2
    cal = ind.calibration(over)
    assert cal.active and cal.value == pytest.approx(50.0) and "over-confident" in cal.reason
    assert not ind.calibration([O(correct=True, confidence=5)]).active  # too little data

    obs = [O(correct=True, hour=18)] * 5 + [O(correct=False, hour=8)] * 5 + [O(correct=True, hour=22)] * 2
    assert ind.best_study_hours(obs) == [(18, 1.0, 5), (8, 0.0, 5)]
