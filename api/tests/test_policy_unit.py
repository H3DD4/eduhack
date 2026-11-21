"""Unit tests for policy logic: grading, null scoring, quote/missing-idea citations, help ladder, follow-up choice."""

from __future__ import annotations

import pytest

from thinkfirst.modules.assessment import mathcheck
from thinkfirst.modules.assessment.explanation import (
    choose_followup,
    split_sentences,
    validate_explanation_output,
)
from thinkfirst.modules.assessment.rubrics import DISTRIBUTIVE
from thinkfirst.modules.student_profile.service import label_for
from thinkfirst.modules.tutor import policy
from thinkfirst.modules.tutor.generators import expand_hints, transfer_task
from thinkfirst.modules.tutor.models import Task

RUBRIC = {"criteria": DISTRIBUTIVE["criteria"], "source_citation": {"page": 2, "filename": "course.pdf"}}


# ---------------- symbolic grading ----------------

@pytest.mark.parametrize("answer,outcome", [("2x + 6", "demonstrated"), ("6 + 2x", "demonstrated"), ("2*x+6", "demonstrated"),
                                            ("2(x + 3)", "partial"), ("2x + 3", "not_demonstrated"), ("2x - 6", "not_demonstrated")])
def test_grade_expand(answer, outcome):
    assert mathcheck.grade_expand(answer, "2(x + 3)").outcome == outcome


def test_distribution_misconception_flagged_with_one_question():
    r = mathcheck.grade_expand("2x + 3", "2(x + 3)")
    assert r.misconception["code"] == "distribution_first_term_only"
    assert r.misconception["targeted_question"].count("?") == 1


def test_unreadable_answer_is_unscored_not_zero():
    r = mathcheck.grade_expand("two x plus six!!", "2(x + 3)")
    assert r.outcome == "unscored"
    corr = next(c for c in r.criteria if c.criterion == "correctness")
    assert corr.score is None and corr.status == "unscored"


def test_parser_rejects_code_injection():
    assert mathcheck.parse("__import__('os').system('echo hi')") is None
    assert mathcheck.parse("x" * 500) is None


def test_equivalent_forms_transfer():
    ok = mathcheck.grade_equivalent_forms("3(x + 4) and 3x + 12", "3(x + 4)")
    assert ok.outcome == "demonstrated"
    one = mathcheck.grade_equivalent_forms("3x + 12", "3(x + 4)")
    cov = next(c for c in one.criteria if c.criterion == "essential_coverage")
    assert cov.status == "partial" and cov.missing[0]["status"] == "not demonstrated"
    wrong = mathcheck.grade_equivalent_forms("3x + 4", "3(x + 4)")
    assert next(c for c in wrong.criteria if c.criterion == "correctness").status == "absent"
    assert mathcheck.grade_equivalent_forms("I am not sure", "3(x + 4)").outcome == "unscored"


# ---------------- explanation validation ----------------

TEXT = "The 2 multiplies every term inside the brackets. So 2(x + 3) = 2x + 6."


def test_invented_quote_is_dropped_and_judgment_becomes_unscored():
    sents = split_sentences(TEXT)
    fake = {"criteria": [{"criterion": "why_relationships", "status": "demonstrated",
                          "quotes": [{"sentence_id": "s1", "text": "because it is two groups"}],  # never said
                          "covered_essentials": ["groups"], "missing_essentials": [], "rationale": "x"}],
            "sufficiency": "sufficient", "reason": ""}
    out = validate_explanation_output(fake, sents, RUBRIC)
    why = next(c for c in out["criteria"] if c["criterion"] == "why_relationships")
    assert why["status"] == "unscored" and why["score"] is None and why["quotes"] == []
    assert out["total"] is None  # no total hides uncertainty


def test_missing_idea_cites_criterion_and_source_without_quote():
    sents = split_sentences(TEXT)
    model = {"criteria": [{"criterion": "limits", "status": "absent", "quotes": [], "covered_essentials": [],
                           "missing_essentials": ["not_products"], "rationale": ""}], "sufficiency": "sufficient", "reason": ""}
    out = validate_explanation_output(model, sents, RUBRIC)
    lim = next(c for c in out["criteria"] if c["criterion"] == "limits")
    assert lim["status"] == "absent" and lim["quotes"] == []
    m = lim["missing"][0]
    assert m["status"] == "not demonstrated" and m["criterion"] == "limits" and m["source"]["page"] == 2


def test_null_output_means_all_unscored():
    out = validate_explanation_output(None, split_sentences(TEXT), RUBRIC)
    assert {c["status"] for c in out["criteria"]} == {"unscored"} and out["outcome"] == "unscored"


def test_unresolved_unclear_word_makes_criterion_unscored():
    sents = split_sentences(TEXT)
    model = {"criteria": [{"criterion": "correctness", "status": "demonstrated", "quotes": [{"sentence_id": "s1", "text": sents[0]["text"]}],
                           "covered_essentials": ["each_term"], "missing_essentials": [], "rationale": ""}],
             "sufficiency": "sufficient", "reason": ""}
    out = validate_explanation_output(model, sents, RUBRIC, unresolved_spans=[{"id": "u1", "text": "brackets"}])
    assert next(c for c in out["criteria"] if c["criterion"] == "correctness")["status"] == "unscored"


def test_na_criteria_excluded():
    rub = {"criteria": [{**c, "applicable": c["criterion"] != "limits"} for c in DISTRIBUTIVE["criteria"]]}
    out = validate_explanation_output({"criteria": [], "sufficiency": "limited", "reason": ""}, split_sentences(TEXT), rub)
    assert next(c for c in out["criteria"] if c["criterion"] == "limits")["status"] == "na"


def test_followup_targets_weakest_and_is_deterministic():
    crit = [{"criterion": "limits", "status": "demonstrated"}, {"criterion": "example_application", "status": "absent"},
            {"criterion": "why_relationships", "status": "partial"}]
    a = choose_followup(crit, DISTRIBUTIVE["followup_bank"])
    assert a == choose_followup(crit, DISTRIBUTIVE["followup_bank"])
    assert a["targets_criterion"] == "example_application"


# ---------------- help ladder + capabilities ----------------

def _task(**kw) -> Task:
    base = {"kind": "expand", "help_level": 0, "mode": "practice", "status": "open", "stage": "practice", "hints": ["h"] * 5}
    base.update(kw)
    return Task(**base)


def test_ladder_order_and_confirmed_reveal():
    t = _task()
    assert policy.next_level(t, "dont_know", False) == 1  # "I don't know" opens orientation immediately
    t.help_level = 3
    assert policy.next_level(t, "next", False) == 4
    t.help_level = 4
    with pytest.raises(policy.RevealConfirmationRequired):
        policy.next_level(t, "next", False)
    assert policy.next_level(t, "next", True) == 5


def test_hints_never_include_solution_before_reveal_level():
    hints, sol = expand_hints("2(x + 3)")
    assert all("2x + 6" not in h for h in hints[:4])
    assert "2x + 6" in hints[4] and sol["expanded"] == "2x + 6"
    assert "4(y − 2)" in hints[3]  # different worked example


def test_capabilities_during_independent_transfer():
    t = _task(kind="equivalent_forms", stage="transfer", mode="independent-transfer", hints=[])
    caps = policy.capabilities(t, lock=t)
    assert not caps["canTutor"] and not caps["canReadSources"] and caps["canSubmit"]


def test_transfer_task_is_novel():
    spec = transfer_task(["2(x + 3)", "3(x + 4)"])
    assert spec is not None and "3(x + 4)" not in spec["prompt"] and spec["novelty"]["different_context"]


# ---------------- evidence labels ----------------

def test_labels():
    full = [{"criterion": c, "status": "demonstrated"} for c in ("correctness", "essential_coverage", "example_application")]
    assert label_for("transfer", "independent-transfer", "demonstrated", full, {}) == "applied_independently"
    assert label_for("transfer", "guided-transfer", "demonstrated", full, {"conversion": True}) == "practised_with_support"
    assert label_for("transfer", "independent-transfer", "unscored", [], {}) == "insufficient_evidence"
    assert label_for("practice", "practice", "demonstrated", full, {}) == "practised_with_support"
    assert label_for("transfer", "independent-transfer", "demonstrated", full, {"revealed": True}) == "practised_with_support"
