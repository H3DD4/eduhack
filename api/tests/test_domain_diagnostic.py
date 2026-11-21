"""Adaptive diagnostic engine: selection, inference, stopping, profile, and a simulated-student validation."""

from __future__ import annotations

import random

import pytest

from thinkfirst.domain.diagnostic.engine import Answer, DiagnosticConfig, DiagnosticEngine
from thinkfirst.domain.diagnostic.inference import SkillState, spread
from thinkfirst.domain.diagnostic.stopping import StopConfig, StopReason
from thinkfirst.domain.knowledge.graph import Skill, SkillGraph
from thinkfirst.domain.knowledge.qmatrix import Item, ItemBank
from thinkfirst.domain.mastery import elo

# Two chapters; algebra depends on arithmetic; systems need equations and exponents.
SKILLS = [
    Skill("fractions", chapter="arithmetic"), Skill("order_ops", chapter="arithmetic"),
    Skill("exponents", chapter="arithmetic"), Skill("equations", chapter="algebra"),
    Skill("systems", chapter="algebra"), Skill("quadratics", chapter="algebra"),
]
EDGES = [("fractions", "order_ops"), ("order_ops", "equations"), ("equations", "systems"),
         ("exponents", "systems"), ("equations", "quadratics"), ("exponents", "quadratics")]
LEVEL = {"fractions": 900, "exponents": 950, "order_ops": 1000, "equations": 1100, "systems": 1250, "quadratics": 1300}


def graph() -> SkillGraph:
    return SkillGraph(SKILLS, EDGES)


def bank(*, calibrated: bool = True) -> ItemBank:
    items = []
    for sid, d in LEVEL.items():
        for n, delta in enumerate((-60, 0, 60), start=1):
            items.append(Item(f"{sid}_{n}", (sid,), difficulty=d + delta, diagnostic=True, verified=True,
                              calibrated=calibrated,
                              misconceptions={"opt_b": "forgot_to_subtract"} if sid == "equations" else {}))
    return ItemBank(items)


def simulate(mastered: set[str], seed: int, *, slip: float = 0.1, guess: float = 0.2) -> tuple[DiagnosticEngine, int]:
    rng = random.Random(seed)
    eng = DiagnosticEngine(graph(), bank(), theta=elo.prior_theta("university", "exam"))
    n = 0
    while (item := eng.next_item()) is not None:
        knows = all(s in mastered for s in item.skills)
        correct = rng.random() > slip if knows else rng.random() < guess
        eng.submit(Answer(item.id, correct, duration_ms=30_000, confidence=4 if knows else 3))
        n += 1
        assert n <= 12
    return eng, n


def test_graph_inference_directions():
    g = graph()
    start = {s.id: SkillState(s.id, 0.3) for s in g.skills}
    up = spread(g, start, "equations", True)
    assert up["order_ops"].p_l > 0.3 and up["fractions"].p_l > 0.3 and up["order_ops"].inferred
    assert up["order_ops"].p_l > up["fractions"].p_l            # closer prerequisites move more
    assert up["systems"].p_l == 0.3                              # dependents untouched by a correct answer
    down = spread(g, start, "order_ops", False)
    assert down["systems"].p_l < 0.3 and down["equations"].p_l < down["systems"].p_l   # closer dependents move more
    assert down["fractions"].p_l == 0.3
    measured = {**start, "order_ops": SkillState("order_ops", 0.6, n=4)}
    assert spread(g, measured, "equations", True)["order_ops"].p_l - 0.6 < up["order_ops"].p_l - 0.3  # damped


def test_first_item_is_easy_then_adapts_up_and_down():
    eng = DiagnosticEngine(graph(), bank(), theta=1100)
    first = eng.next_item()
    assert first is not None and first.id == "fractions_1"           # easiest item: an early win
    assert eng.next_item() is first                                   # idempotent until answered
    eng.submit(Answer(first.id, True, 30_000, confidence=4))
    nxt = eng.next_item()
    assert nxt is not None and LEVEL[nxt.skills[0]] >= 900


def test_wrong_answer_goes_down_to_the_prerequisite():
    eng = DiagnosticEngine(graph(), bank(), theta=1200)
    seen: list[str] = []
    for _ in range(3):
        item = eng.next_item()
        assert item is not None
        seen.append(item.skills[0])
        eng.submit(Answer(item.id, False, 30_000, confidence=3))
    # failing never pushes the student up to harder dependents: unmeasured dependents get lowered instead
    assert eng.states["quadratics"].p_l < 0.3 and eng.states["systems"].p_l < 0.3
    assert not any(s in ("systems", "quadratics") for s in seen[1:])


def test_rapid_guess_counts_for_little_and_is_reported():
    eng = DiagnosticEngine(graph(), bank(), theta=1000)
    item = eng.next_item()
    assert item is not None
    out = eng.submit(Answer(item.id, True, duration_ms=1_000, confidence=5))
    assert out.rapid_guess and out.weight == pytest.approx(0.2)
    st = eng.states[item.skills[0]]
    assert st.n == 0 and st.rapid == 1 and st.p_l < 0.45        # one rapid correct answer barely moves P(L)


def test_dont_know_counts_as_not_mastered():
    eng = DiagnosticEngine(graph(), bank(), theta=1000)
    item = eng.next_item()
    assert item is not None
    eng.submit(Answer(item.id, True, 30_000, dont_know=True))   # even if "correct" by chance
    assert eng.states[item.skills[0]].p_l < 0.1


def test_uncalibrated_items_count_for_less():
    a = DiagnosticEngine(graph(), bank(calibrated=True), theta=1000)
    b = DiagnosticEngine(graph(), bank(calibrated=False), theta=1000)
    ia, ib = a.next_item(), b.next_item()
    assert ia is not None and ib is not None
    a.submit(Answer(ia.id, True, 30_000))
    b.submit(Answer(ib.id, True, 30_000))
    assert b.states[ib.skills[0]].p_l < a.states[ia.skills[0]].p_l


def test_misconception_triggers_one_confirming_follow_up():
    eng = DiagnosticEngine(graph(), bank(), theta=1100)
    first = eng.next_item()
    assert first is not None
    eng.submit(Answer(first.id, True, 30_000))                     # the easy first item
    eng.states["equations"] = SkillState("equations", 0.5)         # make equations the most uncertain skill
    for sid in ("fractions", "order_ops", "exponents"):
        eng.states[sid] = SkillState(sid, 0.95, n=2)
    item = eng.next_item()
    assert item is not None and item.skills == ("equations",)
    out = eng.submit(Answer(item.id, False, 30_000, misconception="forgot_to_subtract"))
    assert out.followup_scheduled
    follow = eng.next_item()
    assert follow is not None and follow.skills == ("equations",) and follow.id != item.id
    out2 = eng.submit(Answer(follow.id, False, 30_000, misconception="forgot_to_subtract"))
    assert not out2.followup_scheduled                              # asked once, not forever
    profile = eng.finish()
    assert [(m.code, m.skill_id, m.count) for m in profile.misconceptions] == [("forgot_to_subtract", "equations", 2)]


def test_stops_on_max_items_and_time():
    cfg = DiagnosticConfig(stop=StopConfig(max_items=3, min_items=99))
    eng = DiagnosticEngine(graph(), bank(), theta=1100, config=cfg)
    for _ in range(3):
        item = eng.next_item()
        assert item is not None
        eng.submit(Answer(item.id, True, 30_000))
    assert eng.stop_reason is StopReason.MAX_ITEMS and eng.next_item() is None
    with pytest.raises(RuntimeError):
        eng.submit(Answer("fractions_2", True, 1))

    slow = DiagnosticEngine(graph(), bank(), theta=1100, config=DiagnosticConfig(stop=StopConfig(max_ms=50_000,
                                                                                                 min_items=99)))
    item = slow.next_item()
    assert item is not None
    out = slow.submit(Answer(item.id, True, 60_000))
    assert out.stop_reason is StopReason.MAX_TIME


def test_frustration_stops_early_and_marks_low_confidence():
    eng = DiagnosticEngine(graph(), bank(), theta=1100)
    for i in range(3):
        item = eng.next_item()
        assert item is not None
        out = eng.submit(Answer(item.id, False, 30_000, response_len=40 - 15 * i, negative_words=1 if i == 2 else 0))
    assert out.stop_reason is StopReason.FATIGUE
    profile = eng.finish()
    assert profile.low_confidence and profile.stop_reason is StopReason.FATIGUE and profile.notes


def test_no_items_left_and_manual_stop():
    tiny = ItemBank([Item("only", ("fractions",), diagnostic=True, verified=True, calibrated=True)])
    eng = DiagnosticEngine(graph(), tiny)
    item = eng.next_item()
    assert item is not None
    eng.submit(Answer(item.id, True, 30_000))
    assert eng.next_item() is None and eng.stop_reason is StopReason.NO_ITEMS

    quitter = DiagnosticEngine(graph(), bank())
    quitter.next_item()
    quitter.stop()
    assert quitter.finish().low_confidence


def test_ends_on_a_success_when_the_last_answer_was_wrong():
    # Student masters the first skills and fails the rest: the final item shown should be one they get right.
    ended_wrong = 0
    for seed in range(40):
        eng, _ = simulate({"fractions", "order_ops", "exponents"}, seed)
        if eng.stop_reason is StopReason.ALL_CLASSIFIED and eng._records and not eng._records[-1].correct:
            ended_wrong += 1
    assert ended_wrong <= 10   # the closing item makes ending on a failure the exception, not the rule


def test_simulated_students_are_classified_accurately_within_the_budget():
    profiles = [
        ({"fractions"}, 0), ({"fractions", "order_ops", "exponents"}, 0),
        ({"fractions", "order_ops", "exponents", "equations"}, 0), (set(), 0),
        ({"fractions", "order_ops", "exponents", "equations", "systems", "quadratics"}, 0),
    ]
    agree = total = 0
    lengths: list[int] = []
    for mastered, _ in profiles:
        for seed in range(30):
            eng, n = simulate(mastered, seed)
            lengths.append(n)
            prof = eng.finish()
            for sid, m in prof.mastery.items():
                if m.status == "uncertain":
                    continue
                total += 1
                agree += (m.status == "mastered") == (sid in mastered)
    assert max(lengths) <= 12 and sum(lengths) / len(lengths) <= 11
    assert total > 0 and agree / total >= 0.80    # design target: >= 80% agreement on mastered vs. not mastered


def test_profile_contents():
    eng, n = simulate({"fractions", "order_ops", "exponents"}, seed=3)
    p = eng.finish()
    assert p.n_items == n and p.evidence_note.startswith(f"Based on {n} answers")
    assert set(p.mastery) == {s.id for s in SKILLS}
    assert set(p.expertise) == {"arithmetic", "algebra"} and p.expertise["arithmetic"] != "novice"
    assert "equations" in p.frontier
    assert p.data_quality["answers"] == n and 0 <= p.behavior_priors["response_time_ratio"] <= 1
    d = p.to_dict()
    assert d["stop_reason"] == p.stop_reason.value and "mastery" in d and isinstance(d["theta"], float)


def test_calibration_gap_in_profile():
    eng = DiagnosticEngine(graph(), bank(), theta=1100)
    for _ in range(4):
        item = eng.next_item()
        if item is None:
            break
        eng.submit(Answer(item.id, False, 30_000, confidence=5))
        if eng.finished:
            break
    p = eng.finish()
    assert p.calibration_gap is None or p.calibration_gap > 0     # over-confident, never negative here
