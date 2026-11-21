"""Pure domain: mastery (Elo, BKT), skill graph, Q-matrix / item bank rules, consent."""

from __future__ import annotations

import pytest

from thinkfirst.domain.consent.tiers import ConsentError, ConsentState, Tier
from thinkfirst.domain.knowledge.graph import GraphError, Skill, SkillGraph
from thinkfirst.domain.knowledge.qmatrix import Item, ItemBank
from thinkfirst.domain.mastery import bkt, elo


def test_elo_expected_success_and_information():
    assert elo.expected_success(1000, 1000) == pytest.approx(0.5)
    assert elo.expected_success(1400, 1000) == pytest.approx(10 / 11)
    assert elo.item_information(0.5) > elo.item_information(0.9)
    assert elo.prior_theta("university", "mastery") == 1150
    assert elo.prior_theta(None) == elo.DEFAULT_THETA


def test_elo_updates_move_in_the_right_direction():
    assert elo.update_theta(1000, 1000, True) > 1000
    assert elo.update_theta(1000, 1000, False) < 1000
    assert elo.update_theta(1000, 1000, True, weight=0.2) < elo.update_theta(1000, 1000, True)
    assert elo.update_difficulty(1000, 1000, True) < 1000   # answered right: easier than thought
    assert elo.calibration_weight(0) == 0.5 and elo.calibration_weight(60) == 1.0


def test_bkt_posterior_and_weights():
    p = bkt.BKTParams()
    assert bkt.update(0.3, True, p) > 0.3 > bkt.update(0.3, False, p)
    full, light = bkt.update(0.3, True, p), bkt.update(0.3, True, p, weight=0.2)
    assert 0.3 < light < full
    assert bkt.update(0.3, True, p, learn=True) > full
    assert bkt.update(0.3, False, p, weight=0.0) == pytest.approx(0.3)


def _graph() -> SkillGraph:
    return SkillGraph(
        [Skill("fractions"), Skill("order_ops"), Skill("equations"), Skill("systems"), Skill("exponents")],
        [("fractions", "order_ops"), ("order_ops", "equations"), ("equations", "systems"), ("exponents", "systems")])


def test_graph_traversal_and_frontier():
    g = _graph()
    assert g.prerequisites("systems") == {"equations", "exponents"}
    assert g.ancestors("systems") == {"equations", "order_ops", "fractions", "exponents"}
    assert g.descendants_with_distance("fractions") == {"order_ops": 1, "equations": 2, "systems": 3}
    order = [s.id for s in g.skills]
    assert order.index("fractions") < order.index("order_ops") < order.index("equations") < order.index("systems")
    assert g.frontier({"fractions"}) == ["exponents", "order_ops"] or g.frontier({"fractions"}) == ["order_ops", "exponents"]
    assert g.frontier(set()) == [s for s in order if s in ("fractions", "exponents")]
    assert g.importance("fractions") > g.importance("systems")  # more skills depend on it


def test_graph_rejects_cycles_unknowns_and_duplicates():
    with pytest.raises(GraphError, match="cycle"):
        SkillGraph([Skill("a"), Skill("b")], [("a", "b"), ("b", "a")])
    with pytest.raises(GraphError, match="unknown"):
        SkillGraph([Skill("a")], [("a", "z")])
    with pytest.raises(GraphError, match="itself|own"):
        SkillGraph([Skill("a")], [("a", "a")])
    with pytest.raises(GraphError, match="duplicate"):
        SkillGraph([Skill("a"), Skill("a")])


def test_item_bank_quality_rules():
    g = SkillGraph([Skill("a"), Skill("b")], [("a", "b")])
    good = [Item("a1", ("a",), diagnostic=True, verified=True), Item("a2", ("a",), diagnostic=True, verified=True),
            Item("b1", ("b",), diagnostic=True, verified=True), Item("b2", ("b",), diagnostic=True, verified=True)]
    assert ItemBank(good).validate(g) == []

    bad = [Item("a1", ("a",), diagnostic=True, verified=True),
           Item("a2", ("a",), diagnostic=True, verified=False),
           Item("b1", ("b",), diagnostic=True, verified=True, generated=True),
           Item("b2", ("b",), diagnostic=True, verified=True, typical_ms=120_000),
           Item("x1", ("ghost",))]
    rules = {(i.rule, i.item_id or i.skill_id) for i in ItemBank(bad).validate(g)}
    assert ("verified_key", "a2") in rules
    assert ("generated_uncalibrated", "b1") in rules
    assert ("answer_time", "b2") in rules
    assert ("q_matrix", "x1") in rules
    assert ("min_items_per_key_skill", "a") in rules and ("min_items_per_key_skill", "b") in rules
    with pytest.raises(GraphError):
        ItemBank([Item("empty", ())])


def test_consent_tiers_and_minors():
    adult = ConsentState.default(birth_year=2000, current_year=2026)
    assert adult.allows(Tier.ESSENTIAL) and not adult.allows(Tier.LEARNING_BEHAVIOR) and not adult.allows(Tier.RESEARCH)
    adult = adult.grant(Tier.LEARNING_BEHAVIOR)
    assert adult.allows(Tier.LEARNING_BEHAVIOR) and not adult.revoke(Tier.LEARNING_BEHAVIOR).allows(Tier.LEARNING_BEHAVIOR)
    with pytest.raises(ConsentError):
        adult.revoke(Tier.ESSENTIAL)

    teen = ConsentState.default(birth_year=2011, current_year=2026)
    assert teen.is_minor and teen.demo_only and not teen.allows(Tier.ESSENTIAL)  # nothing stored until guardian ok
    with pytest.raises(ConsentError):
        teen.grant(Tier.RESEARCH)
    ok = teen.with_guardian_consent()
    assert not ok.demo_only and ok.allows(Tier.ESSENTIAL) and not ok.allows(Tier.RESEARCH)
    assert ok.grant(Tier.RESEARCH).allows(Tier.RESEARCH)
