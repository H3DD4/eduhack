"""Diagnostic, adaptation engine, memory and RAG modules."""

from __future__ import annotations

from datetime import date

from tests.conftest import concept_by_title, ready_subject
from thinkfirst.modules.adaptation import service as adaptation


def _practice(client, sid, cid):
    s = client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": cid}).json()["session"]
    v = client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "k"}).json()
    for _ in range(2):
        v = client.post(f"/api/sessions/{s['id']}/advance", json={"expected_revision": v["session"]["revision"]}).json()
    return s["id"], v["current_task"]


def test_misconception_flows_into_memory_and_nudges_next_session(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    _, t = _practice(student, sid, cid)
    student.post(f"/api/tasks/{t['id']}/submit", json={"answer": "2x + 3", "expected_revision": t["revision"], "idempotency_key": "m1"})
    mem = student.get(f"/api/me/memory?subject_id={sid}").json()
    kinds = [e["kind"] for e in mem["events"]]
    assert "misconception" in kinds and "error" in kinds
    assert any(e["detail"].get("code") == "distribution_first_term_only" for e in mem["events"])
    # a later session on the same concept is reminded of the student's own slip
    sess2, _ = _practice(student, sid, cid)
    view = student.get(f"/api/sessions/{sess2}").json()
    assert "multiplied only the first term" in (view["nudge"] or "")


def test_recurring_misconception_suggests_optional_foundation(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    for i in range(2):
        _, t = _practice(student, sid, cid)
        student.post(f"/api/tasks/{t['id']}/submit", json={"answer": "2x + 3", "expected_revision": t["revision"], "idempotency_key": f"r{i}"})
    road2 = student.get(f"/api/subjects/{sid}/roadmap").json()
    assert road2["suggestion"]["kind"] == "side_quest"
    assert "Order of operations" in road2["suggestion"]["reason"]


def test_diagnostic_baseline_check_and_skip(student):
    sid, _ = ready_subject(student)
    items = student.get(f"/api/subjects/{sid}/diagnostic").json()["items"]
    assert items and items[0]["prompt"].startswith("Expand")
    r = student.post(f"/api/subjects/{sid}/diagnostic/check", json={"item_id": items[0]["id"], "answer": "2x+6"}).json()
    assert r["outcome"] == "demonstrated"
    skip = student.post(f"/api/subjects/{sid}/diagnostic/skip").json()["evidence"]
    assert skip["label"] == "insufficient_evidence" and skip["outcome"] == "unscored"


def test_adaptive_review_interval_is_explained():
    d, why = adaptation.review_interval({"applied_independently", "explained"}, today=date(2026, 1, 1))
    assert d == date(2026, 1, 5) and "hypothesis" in why
    assert adaptation.review_interval(set(), today=date(2026, 1, 1))[0] == date(2026, 1, 2)


def test_rag_retrieves_cited_course_chunks(student, db_session):
    from thinkfirst.modules.identity.models import User
    from thinkfirst.modules.rag import service as rag

    sid, _ = ready_subject(student)
    uid = db_session.query(User).filter(User.email == "student@example.com").one().id
    text, cites = rag.ground(db_session, uid, sid, "distributive property multiplies every term inside the brackets")
    assert cites and cites[0]["kind"] == "course" and "brackets" in text
    assert rag.search_course(db_session, "someone-else", sid, "brackets") == []  # isolation


def test_hybrid_retrieval_local_then_library_then_live_fetch(app_client, db_session, monkeypatch):
    """Local course first; else the shared library; only on a miss does the agent fetch — and the fetched open
    content is reused for the next student without fetching again."""
    from thinkfirst.modules.knowledge_library.models import LicensedContent
    from thinkfirst.modules.rag import service as rag
    from thinkfirst.modules.resource_discovery import service as resources

    calls = []

    def fake_discover(db, owner_id, subject_id, topic, limit=3):
        calls.append(topic)
        item = LicensedContent(title="Ohm's law", source_url="https://en.wikipedia.org/wiki/Ohm%27s_law",
                               license_id="CC-BY-SA-4.0", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                               attribution="Wikipedia contributors", permits_storage=True, permits_redistribution=True,
                               body="Ohm's law states that the current through a conductor between two points is directly "
                                    "proportional to the voltage across the two points. Resistance is the constant.",
                               provider="wikipedia")
        db.add(item)
        db.flush()
        resources.index_item(db, item)
        resources.link(db, owner_id, subject_id, item, topic)
        return [item]

    monkeypatch.setattr(resources, "discover", fake_discover)
    q = "Ohm's law current voltage resistance"
    first = rag.hybrid(db_session, "student-a", "subject-a", q, fetch_query="Ohm's law")
    assert first["route"] == "live-fetch" and first["citations"][0]["license"] == "CC-BY-SA-4.0"
    second = rag.hybrid(db_session, "student-b", "subject-b", q, fetch_query="Ohm's law")
    assert second["route"] == "library" and calls == ["Ohm's law"]  # reused, not fetched again
    assert resources.for_subject(db_session, "student-b", "subject-b")  # linked privately to the second student


def test_hybrid_prefers_the_students_own_course(student, db_session):
    from thinkfirst.modules.identity.models import User
    from thinkfirst.modules.rag import service as rag

    sid, _ = ready_subject(student)
    uid = db_session.query(User).filter(User.email == "student@example.com").one().id
    g = rag.hybrid(db_session, uid, sid, "distributive property every term inside the brackets", fetch_query="Distributive property")
    assert g["route"] == "course" and g["citations"][0]["page"] == 2


def test_long_topic_label_fits_postgres_column_and_failed_job_is_reported(student):
    """Regression: a long topic overflowed extraction_label VARCHAR(200) on Postgres and the UI waited forever."""
    long_topic = "algebra " + "and expanding brackets with many words " * 6
    sid = student.post("/api/subjects/topic", json={"topic": long_topic}).json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    assert setup["proposal"] and len(setup["proposal"]["label"]) <= 200


def test_failed_topic_job_moves_subject_out_of_processing(student, monkeypatch):
    from thinkfirst.modules.ingestion import service as ingestion

    def boom(db, job):
        raise RuntimeError("simulated failure")

    monkeypatch.setitem(__import__("thinkfirst.core.jobs", fromlist=["_registry"])._registry, "ingestion.topic_scope", boom)
    sid = student.post("/api/subjects/topic", json={"topic": "algebra basics"}).json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    assert setup["topic_job"]["status"] == "failed" and setup["subject"]["status"] == "needs_attention"
    _ = ingestion
