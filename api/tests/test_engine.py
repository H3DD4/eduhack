"""Learner engine: math, state machine, fold invariants, policy, bandit, metrics, simulator recovery, JSON contract."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from thinkfirst.modules.adaptation.engine import (
    bkt,
    evaluate_json,
    fold_json,
    json_schemas,
    recommend_json,
    retention,
)
from thinkfirst.modules.adaptation.engine.metrics import auc
from thinkfirst.modules.adaptation.engine.policy import choose_action, priors
from thinkfirst.modules.adaptation.engine.schemas import BKTParams, EngineConfig
from thinkfirst.modules.adaptation.engine.simulator import simulate

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
P = BKTParams()
CONCEPTS = [
    {"concept_id": "F1", "order": 0, "is_foundation": True},
    {"concept_id": "c1", "order": 1},
    {"concept_id": "c2", "order": 2, "prerequisites": ["c1", "F1"],
     "misconceptions": [{"id": "first_term_only", "prerequisite_id": "F1"}]},
    {"concept_id": "c3", "order": 3, "prerequisites": ["c2"]},
]


def ev(i, concept, kind="attempt", hours=0.0, **kw):
    return {"event_id": f"e{i}", "student_id": "s1", "concept_id": concept, "kind": kind,
            "ts": (T0 + timedelta(hours=hours)).isoformat(), **kw}


def fold(events, **kw):
    return fold_json({"student_id": "s1", "concepts": CONCEPTS, "events": events, **kw})


# ---------------- BKT math ----------------

def test_bkt_posterior_matches_hand_computation():
    # p=0.1, correct, unaided: 0.1*0.9 / (0.1*0.9 + 0.9*0.15) = 0.4
    assert bkt.posterior(0.1, True, False, P) == pytest.approx(0.4)
    # then learning transition: 0.4 + 0.6*0.15 = 0.49
    assert bkt.update(0.1, 1.0, False, 1.0, P) == pytest.approx(0.49)
    # wrong: 0.1*0.1 / (0.1*0.1 + 0.9*0.85) = 0.012903...
    assert bkt.posterior(0.1, False, False, P) == pytest.approx(0.01 / 0.775)


def test_help_makes_a_correct_answer_weaker_evidence():
    unaided = bkt.update(0.3, 1.0, False, 1.0, P)
    assisted = bkt.update(0.3, 1.0, True, 1.0, P)
    assert unaided > assisted > 0.3


def test_zero_weight_moves_only_by_learning_transition():
    assert bkt.update(0.3, 1.0, False, 0.0, P) == pytest.approx(0.3 + 0.7 * P.learn)


# ---------------- retention ----------------

def test_forgetting_curve_and_due_date():
    assert retention.retrievability(5.0, 5.0) == pytest.approx(0.9)  # by definition R(S) = 0.9
    cfg = EngineConfig()
    due = retention.due_at(T0, 2.0, cfg)
    assert retention.retrievability(2.0, (due - T0).total_seconds() / 86400) == pytest.approx(cfg.review_threshold_R)
    assert retention.after_success(2.0, 0.6, cfg) > retention.after_success(2.0, 0.95, cfg)  # harder recall grows more


def test_stability_grows_only_with_delayed_unaided_success():
    base = [ev(1, "c1", outcome="correct", evidence="symbolic")]
    same_day = fold(base + [ev(2, "c1", hours=3, outcome="correct", evidence="symbolic")])["concepts"]["c1"]
    delayed = fold(base + [ev(2, "c1", hours=72, outcome="correct", evidence="symbolic")])["concepts"]["c1"]
    assisted = fold(base + [ev(2, "c1", hours=72, outcome="correct", assistance="hint_l1")])["concepts"]["c1"]
    assert same_day["stability_days"] == 1.0 and assisted["stability_days"] == 1.0
    assert delayed["stability_days"] > 1.0 and delayed["delayed_successes"] == 1
    lapse = fold(base + [ev(2, "c1", hours=72, outcome="incorrect")])["concepts"]["c1"]
    assert lapse["stability_days"] < 1.0


def test_review_due_after_time_passes():
    s = fold([ev(1, "c1", outcome="correct")], as_of=(T0 + timedelta(days=10)).isoformat())["concepts"]["c1"]
    assert s["review_due"] is True and s["retrievability"] < 0.85


# ---------------- fold invariants ----------------

def test_fold_is_idempotent_order_independent_and_dedupes():
    evs = [ev(i, "c1", hours=i, outcome="correct" if i % 2 else "incorrect") for i in range(1, 7)]
    a = fold(evs)
    b = fold(list(reversed(evs)) + evs[:3])  # shuffled + duplicated retries
    assert a["concepts"] == b["concepts"] and b["events_ignored"] == 3


def test_unscored_never_moves_anything_and_other_students_are_ignored():
    evs = [ev(1, "c1", outcome="correct"), ev(2, "c1", hours=1, outcome="unscored")]
    other = {**ev(3, "c1", hours=2, outcome="incorrect"), "student_id": "someone-else"}
    s = fold(evs + [other])
    assert s["concepts"]["c1"]["scored_events"] == 1 and s["events_ignored"] == 1


def test_deleting_an_event_replays_to_a_different_state():
    evs = [ev(1, "c1", outcome="incorrect"), ev(2, "c1", hours=1, outcome="correct")]
    assert fold(evs)["concepts"]["c1"] != fold(evs[1:])["concepts"]["c1"]


def test_levels_progress_and_need_unaided_and_delayed_evidence():
    assert fold([])["concepts"]["c1"]["level"] == 0
    assisted_only = [ev(i, "c1", hours=i, outcome="correct", assistance="hint_l2") for i in range(1, 9)]
    assert fold(assisted_only)["concepts"]["c1"]["level"] <= 3  # help alone never reaches Proficient
    strong = [ev(i, "c1", hours=i, outcome="correct", evidence="symbolic") for i in range(1, 5)]
    s = fold(strong)["concepts"]["c1"]
    assert s["level"] == 4 and s["level_label"] == "Proficient"
    s5 = fold(strong + [ev(9, "c1", kind="review_check", hours=24 * 5, outcome="correct")])["concepts"]["c1"]
    assert s5["level"] == 5 and s5["level_label"] == "Mastered"


# ---------------- misconception state machine ----------------

def test_misconception_full_lifecycle_and_relapse():
    mk = dict(outcome="incorrect", misconception_id="first_term_only")
    evs = [ev(1, "c2", **mk), ev(2, "c2", hours=1, **mk), ev(3, "c2", "worked_example", hours=2,
                                                         misconception_id="first_term_only"),
           ev(4, "c2", hours=3, outcome="correct"), ev(5, "c2", hours=4, outcome="correct"),
           ev(6, "c2", "review_check", hours=24 * 4, outcome="correct")]
    s = fold(evs)
    m = s["concepts"]["c2"]["misconceptions"][0]
    assert m["status"] == "resolved" and [h.split("@")[0] for h in m["history"]] == [
        "new->suspected", "suspected->active", "active->remediating", "remediating->monitoring", "monitoring->resolved"]
    assert m["events_to_resolve"] == 3  # e4, e5, e6 after activation at e2
    relapse = fold(evs + [ev(7, "c2", hours=24 * 5, **mk)])["concepts"]["c2"]["misconceptions"][0]
    assert relapse["status"] == "active" and relapse["relapses"] == 1 and len(relapse["history"]) == 6


def test_high_confidence_activates_immediately_and_softens_prerequisite():
    s = fold([ev(1, "c2", outcome="incorrect", misconception_id="first_term_only", misconception_conf=0.9)])
    assert s["concepts"]["c2"]["misconceptions"][0]["status"] == "active"
    f1 = s["concepts"]["F1"]
    assert f1["needs_diagnostic_check"] and f1["p_mastery"] == pytest.approx(0.1 * 0.85, abs=1e-4)
    assert s["concepts"]["c2"]["level"] <= 3


# ---------------- policy ----------------

def test_frontier_respects_prerequisites_but_not_foundations():
    rec = recommend_json({"student_id": "s1", "concepts": CONCEPTS, "events": [], "as_of": T0.isoformat()})
    kinds = {c["concept_id"]: c["kind"] for c in rec["next_concepts"]}
    assert kinds.get("c1") == "frontier" and "c3" not in kinds and "F1" not in kinds
    strong = [ev(i, "c1", hours=i, outcome="correct") for i in range(1, 6)]
    rec2 = recommend_json({"student_id": "s1", "concepts": CONCEPTS, "events": strong, "as_of": (T0 + timedelta(hours=6)).isoformat()})
    assert rec2["next_concepts"][0] == {"concept_id": "c2", "kind": "frontier",
                                        "reason": "Its prerequisites are in place and it isn't proficient yet."}


def test_active_misconception_and_due_review_come_first():
    evs = [ev(1, "c1", outcome="correct"),
           ev(2, "c2", hours=1, outcome="incorrect", misconception_id="first_term_only", misconception_conf=0.95)]
    rec = recommend_json({"student_id": "s1", "concepts": CONCEPTS, "events": evs,
                          "as_of": (T0 + timedelta(days=12)).isoformat()})
    order = [(c["concept_id"], c["kind"]) for c in rec["next_concepts"]]
    assert order[0] == ("c2", "remediate") and ("c1", "review") in order and ("F1", "diagnostic_check") in order


def test_bandit_priors_choice_is_reproducible_and_propensity_valid():
    cfg = EngineConfig()
    t = priors("first_term_only|low", cfg)
    assert t["worked_example"][0] > t["guided_retry"][0] and t["refutation"][0] > 1
    a1 = choose_action("first_term_only|low", t, seed=42)
    a2 = choose_action("first_term_only|low", t, seed=42)
    assert a1 == a2 and 0 < a1.propensity <= 1


def test_bandit_learns_from_logged_rewards():
    evs = []
    for k in range(40):  # refutation keeps working, worked_example keeps failing
        h = k * 3
        evs.append(ev(f"r{k}", "c2", "recommendation", hours=h, recommended_action="refutation" if k % 2 else "worked_example",
                      context_key="first_term_only|low", propensity=0.5))
        evs.append(ev(f"a{k}", "c2", hours=h + 1, outcome="correct" if k % 2 else "incorrect"))
    picks = [recommend_json({"student_id": "s1", "concepts": CONCEPTS, "events": [], "population_events": evs,
                             "focus_concept_id": "c2", "error_class": "first_term_only", "seed": s,
                             "as_of": T0.isoformat()})["action"]["action"] for s in range(30)]
    assert picks.count("refutation") >= 25


# ---------------- metrics ----------------

def test_auc_known_values():
    assert auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == pytest.approx(0.75)
    assert auc([0.5, 0.5], [0, 1]) == pytest.approx(0.5)
    assert auc([0.2, 0.3], [1, 1]) is None


def test_ips_offline_policy_value():
    evs = [ev("r1", "c2", "recommendation", hours=0, recommended_action="refutation", context_key="x|low", propensity=0.5),
           ev("a1", "c2", hours=1, outcome="correct"),
           ev("r2", "c2", "recommendation", hours=2, recommended_action="worked_example", context_key="x|low", propensity=0.5),
           ev("a2", "c2", hours=3, outcome="incorrect")]
    m = evaluate_json({"student_events": {"s1": evs}, "concepts": CONCEPTS, "target_policy": {"x|low": "refutation"}})
    assert m["logged_policy_value"] == 0.5 and m["ips_value"] == pytest.approx(1.0)  # (1/0.5 + 0)/2


# ---------------- simulator: the engine recovers hidden truth ----------------

def test_engine_recovers_hidden_states_of_virtual_students():
    sim = simulate(150, seed=11)
    ok = tot = 0
    for sid, evs in sim["students"].items():
        st = fold_json({"student_id": sid, "concepts": sim["concepts"], "events": evs})
        for cid, known in sim["truth"][sid]["known"].items():
            tot += 1
            ok += (st["concepts"][cid]["p_mastery"] >= 0.8) == known
    assert ok / tot >= 0.85, ok / tot


def test_prediction_quality_close_to_the_oracle_ceiling():
    sim = simulate(150, seed=5)
    m = evaluate_json({"student_events": sim["students"], "concepts": sim["concepts"]})
    ps, ys = [], []
    for sid, evs in sim["students"].items():
        for e in evs:
            if e["kind"] in ("attempt", "review_check"):
                ps.append(sim["truth"][sid]["oracle_p_correct"][e["event_id"]])
                ys.append(1 if e["outcome"] == "correct" else 0)
    ceiling = auc(ps, ys)
    assert m["auc"] >= 0.85 * ceiling and m["brier"] < 0.22
    assert m["misconceptions_activated"] > 0 and m["misconceptions_resolved"] > 0


# ---------------- JSON contract ----------------

def test_json_schema_and_invalid_input_rejected():
    schemas = json_schemas()
    assert set(schemas["inputs"]) == {"FoldRequest", "RecommendRequest", "EvaluateRequest", "SelectRequest", "QualityRequest"}
    assert schemas["outputs"]["LearnerState"]["properties"]["engine_version"]
    with pytest.raises(ValidationError):
        fold_json({"student_id": "s1", "concepts": [], "events": [{"event_id": "x", "kind": "attempt"}]})


def test_cli_json_in_json_out():
    payload = {"student_id": "s1", "concepts": CONCEPTS, "events": [ev(1, "c1", outcome="correct")]}
    r = subprocess.run([sys.executable, "-m", "thinkfirst.modules.adaptation.engine", "fold"], input=json.dumps(payload),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["engine_version"] == "1.0" and out["concepts"]["c1"]["scored_events"] == 1
    bad = subprocess.run([sys.executable, "-m", "thinkfirst.modules.adaptation.engine", "fold"], input="{}",
                         capture_output=True, text=True, timeout=60)
    assert bad.returncode == 1 and json.loads(bad.stdout)["error"] == "INVALID_INPUT"


def test_aggregated_bandit_stats_equivalent_input():
    req = {"student_id": "s1", "concepts": CONCEPTS, "events": [], "focus_concept_id": "c2", "error_class": "first_term_only",
           "as_of": T0.isoformat(), "bandit_stats": {"first_term_only|low": {"refutation": [30, 0], "worked_example": [0, 30]}}}
    picks = [recommend_json({**req, "seed": s})["action"]["action"] for s in range(20)]
    assert picks.count("refutation") >= 16 and "worked_example" not in picks  # untried actions are still explored
