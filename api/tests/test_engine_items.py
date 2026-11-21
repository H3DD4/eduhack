"""Question selection + question/hint quality (pure engine)."""

from __future__ import annotations

import pytest

from thinkfirst.modules.adaptation.engine import quality_json, select_item_json

POOL = [
    {"item_id": "easy1", "concept_id": "c", "difficulty": "easy", "triggers": ["first_term_only"], "order": 0},
    {"item_id": "easy2", "concept_id": "c", "difficulty": "easy", "order": 1},
    {"item_id": "med1", "concept_id": "c", "difficulty": "medium", "triggers": ["first_term_only"], "order": 2},
    {"item_id": "hard1", "concept_id": "c", "difficulty": "hard", "triggers": ["sign_error"], "order": 3},
    {"item_id": "other", "concept_id": "d", "difficulty": "easy"},
]


def sel(**kw):
    return select_item_json({"concept_id": "c", "candidates": POOL, **kw})


def band(n, c):
    return {"attempts": n, "correct": c}


def test_difficulty_matches_mastery():
    assert sel(p_mastery=0.05)["item_id"] == "easy1"          # target 0.23 -> easy
    assert sel(p_mastery=0.5)["item_id"] == "med1"            # target 0.50 -> medium
    r = sel(p_mastery=0.95)
    assert r["item_id"] == "hard1" and r["target_difficulty"] == pytest.approx(0.77)


def test_trigger_items_win_while_a_misconception_is_active():
    r = sel(p_mastery=0.95, active_misconceptions=["first_term_only"])
    assert r["is_trigger"] and r["item_id"] in ("easy1", "med1") and "first_term_only" in r["reason"]
    assert sel(p_mastery=0.95, active_misconceptions=["sign_error"])["item_id"] == "hard1"


def test_never_repeats_a_seen_or_helped_item_and_reports_exclusions():
    r = sel(p_mastery=0.05, seen_item_ids=["easy1"])
    assert r["item_id"] == "easy2" and r["excluded"]["seen"] == 1
    none = sel(p_mastery=0.05, seen_item_ids=["easy1", "easy2", "med1", "hard1"])
    assert none["item_id"] is None


def test_retired_items_are_never_selected():
    stats = [{"item_id": "easy1", "low": band(10, 9), "high": band(10, 2)}]  # strong students fail: suspect, 20 answers
    r = sel(p_mastery=0.05, item_stats=stats)
    assert r["item_id"] == "easy2" and r["excluded"]["retired"] == 1


def test_empirical_difficulty_overrides_declared_level():
    stats = [{"item_id": "hard1", "mid": band(12, 9)}]  # declared hard but 75% succeed -> empirical 0.25
    assert sel(p_mastery=0.05, item_stats=stats, seen_item_ids=["easy1", "easy2"])["item_id"] == "hard1"


def test_item_quality_flags_and_statuses():
    rep = quality_json({"items": [
        {"item_id": "fine", "low": band(10, 3), "high": band(10, 9)},
        {"item_id": "easy", "low": band(10, 10), "high": band(10, 10)},
        {"item_id": "hard", "mid": band(12, 1)},
        {"item_id": "bad", "low": band(10, 8), "high": band(10, 2)},
        {"item_id": "badsmall", "low": band(5, 4), "high": band(5, 1)},
        {"item_id": "new"},
    ]})
    q = {i["item_id"]: i for i in rep["items"]}
    assert q["fine"]["status"] == "ok" and q["fine"]["discrimination"] == pytest.approx(0.6)
    assert q["easy"]["flags"] == ["too_easy"] and q["easy"]["status"] == "watch"
    assert q["hard"]["flags"] == ["too_hard"]
    assert q["bad"]["status"] == "retire" and q["bad"]["discrimination"] == pytest.approx(-0.6)
    assert q["badsmall"]["status"] == "watch"  # suspect but not enough data to retire
    assert q["new"]["status"] == "new"


def test_hint_quality():
    rep = quality_json({"hints": [{"hint_id": "h1", "shown": 12, "followed_by_correct": 1},
                                  {"hint_id": "h2", "shown": 12, "followed_by_correct": 8},
                                  {"hint_id": "h3", "shown": 3, "followed_by_correct": 0}]})
    q = {h["hint_id"]: h["status"] for h in rep["hints"]}
    assert q == {"h1": "rewrite", "h2": "ok", "h3": "watch"}
