"""End-to-end integration tests for the diagnostic.md system track across all 6 SysBrains:
Core -> Student -> Subject -> Evidence -> Session -> Plan.

Uses `db_session` directly so tests execute in < 2 seconds without opening loopback sockets.
"""

from __future__ import annotations

import pytest

from thinkfirst.core import db as dbmod
from thinkfirst.core import events
from thinkfirst.core.errors import ValidationFailed
from thinkfirst.core.storage import LocalStorage, set_storage
from thinkfirst.data.memory import service as memory
from thinkfirst.data.student_profile import service as student_profile
from thinkfirst.modules.adaptation import service as adaptation
from thinkfirst.modules.diagnostic import service as diagnostic
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.identity import service as identity
from thinkfirst.platform.workspaces import service as workspaces


@pytest.fixture()
def db_session(tmp_path):
    engine = dbmod.configure(f"sqlite:///{tmp_path / 'test.db'}")
    dbmod.create_all_for_tests(engine)
    set_storage(LocalStorage(str(tmp_path / "storage")))
    with dbmod.session_factory()() as s:
        yield s
    engine.dispose()


def _ready_algebra_subject(db, owner_id: str) -> str:
    sub = workspaces.create_subject(db, owner_id, "Algebra 101", origin="guided_topic", goal="exam")
    rev = ingestion.create_guided_scope(db, owner_id, sub.id, "algebra")
    ingestion.confirm_scope(db, owner_id, sub.id, rev.id, edits=[])
    return sub.id


def test_onboarding_age_gate_consent_tiers_and_minors_gating(db_session):
    recorded_events: list[str] = []
    for ev_name in (events.USER_CREATED, events.AGE_GATED, events.CONSENT_UPDATED,
                    events.PROFILE_SEEDED, events.GOAL_SET):
        events.subscribe(ev_name)(lambda db, e, n=ev_name: recorded_events.append(n))

    user = identity.register(db_session, "sara@example.com", "password123", "Sara")
    assert events.USER_CREATED in recorded_events

    # Minor (Sara, 15, born 2011): demo_only until guardian consents; cannot enable research tier
    age_info = identity.apply_age_gate(db_session, user.id, 2011, guardian_email="parent@example.com", current_year=2026)
    assert age_info["is_minor"] is True and age_info["demo_only"] is True
    assert events.AGE_GATED in recorded_events

    with pytest.raises(ValidationFailed, match="guardian consent"):
        identity.update_tracking_consent(db_session, user.id, grant=["research"])

    # While demo_only (before guardian consent), behavioral tracking stores no personal data
    dropped = memory.ingest_tracking_event(db_session, user.id, {
        "verb": "answered",
        "object": {"type": "item", "id": "F1_1", "skills": ["F1"]},
        "result": {"correct": True, "duration_ms": 20_000, "edits": 2},
        "context": {"confidence": 4},
    })
    assert dropped["stored"] is False and dropped["reason"] == "consent_tier_off"

    # Guardian consent arrives -> essential works; learning_behavior still off until granted
    c_info = identity.update_tracking_consent(
        db_session, user.id, guardian_consented=True, deal_accepted=True,
    )
    assert c_info["demo_only"] is False and c_info["deal_accepted"] is True
    assert events.CONSENT_UPDATED in recorded_events

    # Essential tier cannot be turned off
    with pytest.raises(ValidationFailed, match="Essential"):
        identity.update_tracking_consent(db_session, user.id, revoke=["essential"])

    # Complete 10-step onboarding flow -> seeds starting Elo prior theta & goal/rhythm
    onb = identity.complete_onboarding(
        db_session, user, goal="exam", level="high_school", field="mathematics",
        exam_date="2026-12-15", prior_confidence=4, study_times=["18:00"],
        hours_per_week=6, first_session_slot="Tomorrow at 18:00", interests=["football"],
        grant_tiers=["learning_behavior"],
    )
    assert "learning_behavior" in onb["granted_tiers"]
    assert onb["onboarding"]["prior_theta"] == 1000.0
    assert events.PROFILE_SEEDED in recorded_events and events.GOAL_SET in recorded_events


def test_behavioral_tracking_pseudonymity_redaction_and_indicators(db_session):
    user = identity.register(db_session, "amine@example.com", "password123", "Amine")
    identity.apply_age_gate(db_session, user.id, 2005, current_year=2026)

    # Rejects NEVER_TRACKED fields (camera, location, keystrokes, health, etc.)
    with pytest.raises(ValidationFailed, match="never tracked"):
        memory.ingest_tracking_event(db_session, user.id, {
            "verb": "answered",
            "object": {"type": "item", "id": "1.2_1"},
            "context": {"location": "Tunis"},
        })

    # With only essential tier active, `edits` and `focus_switches` are stripped, and `edited` verb is dropped
    r1 = memory.ingest_tracking_event(db_session, user.id, {
        "verb": "answered",
        "object": {"type": "item", "id": "1.2_1", "skills": ["1.2"]},
        "result": {"correct": False, "duration_ms": 2_000, "typical_ms": 40_000, "edits": 4},
        "context": {"confidence": 5, "focus_switches": 3},
    })
    assert r1["stored"] is True
    assert r1["event"]["actor"].startswith("stu_") and user.id not in r1["event"]["actor"]
    assert "edits" not in r1["event"]["result"] and "focus_switches" not in r1["event"]["context"]
    # Rapid guess (2s < 10% of 40s) is flagged live
    rg = next(i for i in r1["indicators"] if i["name"] == "rapid_guessing")
    assert rg["active"] is True

    dropped_edit = memory.ingest_tracking_event(db_session, user.id, {
        "verb": "edited",
        "object": {"type": "item", "id": "1.2_1"},
    })
    assert dropped_edit["stored"] is False

    # Grant learning_behavior -> `edited` and `edits` are now retained
    identity.update_tracking_consent(db_session, user.id, grant=["learning_behavior"])
    kept_edit = memory.ingest_tracking_event(db_session, user.id, {
        "verb": "edited",
        "object": {"type": "item", "id": "1.2_1"},
        "result": {"edits": 2},
    })
    assert kept_edit["stored"] is True and kept_edit["event"]["result"]["edits"] == 2


def test_full_adaptive_diagnostic_pipeline_to_initial_profile_and_first_plan(db_session):
    fired: list[str] = []
    for ev_name in (events.WORKSPACE_CREATED, events.GRAPH_BUILT, events.ITEMS_READY,
                    events.ANSWER_GRADED, events.DIAGNOSTIC_COMPLETED,
                    events.MASTERY_UPDATED, events.PROFILE_READY, events.PLAN_UPDATED):
        events.subscribe(ev_name)(lambda db, e, n=ev_name: fired.append(n))

    user = identity.register(db_session, "lina@example.com", "password123", "Lina")
    identity.complete_onboarding(
        db_session, user, birth_year=1999, deal_accepted=True, goal="certification",
        level="university", field="engineering", prior_confidence=4,
        first_session_slot="Tomorrow at 19:00", grant_tiers=["learning_behavior"],
    )

    subject_id = _ready_algebra_subject(db_session, user.id)
    assert events.WORKSPACE_CREATED in fired
    assert events.GRAPH_BUILT in fired
    assert events.ITEMS_READY in fired

    ks = diagnostic.knowledge_space_public(db_session, user.id, subject_id)
    assert ks["ready_for_diagnostic"] is True and ks["quality_issues"] == []
    assert ks["item_count"] >= 12

    state = diagnostic.start_diagnostic(db_session, user.id, subject_id)
    assert state["status"] == "active" and state["current_item"] is not None
    # First item is deliberately easy (F1 Order of operations)
    assert state["current_item"]["skills"] == ["F1"]

    # Student masters F1 and 1.1, but has the distribution_first_term_only misconception on 1.2
    steps = 0
    while state["status"] == "active" and state["current_item"] is not None:
        item = state["current_item"]
        skill = item["skills"][0]
        if skill in ("F1", "1.1"):
            # Pick the correct option "a"
            state = diagnostic.submit_diagnostic_answer(
                db_session, user.id, subject_id, item_id=item["id"],
                option_id="a", confidence=4, duration_ms=25_000,
            )
        elif skill == "1.2":
            # Pick option "b" (distribution_first_term_only misconception) with high confidence (over-confident)
            state = diagnostic.submit_diagnostic_answer(
                db_session, user.id, subject_id, item_id=item["id"],
                option_id="b", confidence=5, duration_ms=30_000,
            )
        else:
            # Uses "I don't know" on advanced skills (1.3)
            state = diagnostic.submit_diagnostic_answer(
                db_session, user.id, subject_id, item_id=item["id"],
                dont_know=True, confidence=2, duration_ms=15_000,
            )
        steps += 1
        assert steps <= 12

    assert state["status"] == "completed"
    prof = state["profile"]
    assert prof is not None and 5 <= prof["n_items"] <= 12
    assert events.ANSWER_GRADED in fired
    assert events.DIAGNOSTIC_COMPLETED in fired
    assert events.MASTERY_UPDATED in fired
    assert events.PROFILE_READY in fired
    assert events.PLAN_UPDATED in fired

    # Verify knowledge space inference & frontier: F1 and 1.1 mastered -> 1.2 is on the frontier!
    assert prof["mastery"]["F1"]["status"] == "mastered"
    assert prof["mastery"]["1.1"]["status"] == "mastered"
    assert prof["mastery"]["1.2"]["status"] == "not_mastered"
    assert "1.2" in prof["frontier"]
    assert any(m["code"] == "distribution_first_term_only" for m in prof["misconceptions"])

    # Verify motivating student result screen (6 required elements from diagnostic.md)
    view = prof["student_view"]
    assert view["headline"] == "Here's where we start"
    assert any(w["skill_id"] == "1.2" for w in view["where_we_start"])
    assert view["strength"]["skill_id"] in ("F1", "1.1")
    assert "multiplying every term inside the brackets" in view["real_gap"]
    assert view["first_session_booked"]["slot"] == "Tomorrow at 19:00"
    assert view["transparency"].startswith(f"Based on {prof['n_items']} answers.")

    # Verify Evidence Brain persisted SkillMasteryRow & InitialProfileRow, and Plan Brain wrote first_plan
    mastery_rows = student_profile.skill_mastery_for_subject(db_session, user.id, subject_id)
    assert len(mastery_rows) == 4
    saved_prof = student_profile.initial_profile_for_subject(db_session, user.id, subject_id)
    assert saved_prof is not None
    assert saved_prof["first_plan"]["first_session_slot"] == "Tomorrow at 19:00"
    assert saved_prof["first_plan"]["recommended_steps"][0]["skill_key"] == "1.2"

    # Adaptation engine now uses the knowledge frontier / misconception evidence
    suggestion = adaptation.suggest_concept(db_session, user.id, subject_id)
    assert suggestion is not None
    # And the diagnostic misconception flows into session_nudge for the frontier concept!
    concepts = {c.key: c for c in ingestion.active_concepts(db_session, user.id, subject_id)}
    nudge = adaptation.session_nudge(db_session, user.id, subject_id, concepts["1.2"].id)
    assert nudge is not None and "first term" in nudge
    # And PROFILE_READY prefetched the concept pack for the frontier skill ("1.2")!
    from thinkfirst.modules.tutor import packs

    assert packs.get_pack(db_session, user.id, concepts["1.2"].id) is not None


def test_diagnostic_item_bank_integrates_with_uploaded_course_and_rag_grounding(db_session):
    """Coherence with the Qdrant/HF RAG stack and uploaded course ingestion:
    extracted exercises and RAG-grounded custom concepts get verified diagnostic items with page citations."""
    from thinkfirst.fixtures import DEMO_COURSE_FILENAME, demo_course_pdf

    user = identity.register(db_session, "upload-diag@example.com", "password123")
    sub = workspaces.create_subject(db_session, user.id, "MATH 101 Upload")
    ingestion.add_source(db_session, user.id, sub.id, DEMO_COURSE_FILENAME, "application/pdf",
                         demo_course_pdf(), role="course", rights_ack=True)
    prop = ingestion.proposed_revision(db_session, user.id, sub.id)
    assert prop is not None
    # Rename one concept key to a custom key so _generic_items_for_concept (RAG grounding + extracted SourceItem) runs
    custom_c = next(c for c in ingestion.concepts_of(db_session, prop.id) if c.key == "1.2")
    custom_c.key = "CUSTOM_1_2"
    for item in ingestion.all_items(db_session, user.id, sub.id):
        if item.concept_key == "1.2":
            item.concept_key = "CUSTOM_1_2"
    db_session.flush()

    ingestion.confirm_scope(db_session, user.id, sub.id, prop.id, edits=[])
    ks = diagnostic.knowledge_space_public(db_session, user.id, sub.id)
    assert ks["ready_for_diagnostic"] is True and ks["quality_issues"] == []
    _, _, rows = diagnostic.ensure_knowledge_space(db_session, user.id, sub.id)
    custom_rows = [r for r in rows if "CUSTOM_1_2" in (r.skills or [])]
    assert len(custom_rows) >= 2
    # The extracted exercise 'Expand 2(x + 3).' was SymPy-verified with answer_key '2x + 6' and page 2 citation
    src_row = next((r for r in custom_rows if r.kind == "expand"), None)
    assert src_row is not None
    assert src_row.answer_key == "2x + 6" and src_row.source_page == 2
