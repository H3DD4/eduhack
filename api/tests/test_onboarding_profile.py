"""Onboarding form: who the learner is, and what it changes (suggestions, generators). Name and age never reach the AI."""

from __future__ import annotations

from thinkfirst.core import db as dbmod
from thinkfirst.modules.diagnostic import placement
from thinkfirst.platform.identity import service as identity


def _save(client, **kw):
    return client.patch("/api/me/onboarding", json={"goal": "understand", **kw})


def test_profile_is_saved_personalises_suggestions_and_keeps_name_and_age_private(student):
    before = [x["topic"] for x in student.get("/api/topics/suggestions").json()["suggestions"]]
    r = _save(student, display_name="  Sam ", birth_year=2004, status="university", field="Computer science", study_year="3rd year",
              interests=["Psychology", ""], hours_per_week=8)
    assert r.status_code == 200, r.text
    o = r.json()["onboarding"]["onboarding"]
    assert (o["status"], o["field"], o["study_year"]) == ("university", "Computer science", "3rd year")
    assert o["rhythm"]["hours_per_week"] == 8 and o["comfort"]["interests"] == ["Psychology"]
    assert student.get("/api/auth/me").json()["user"]["display_name"] == "Sam"
    after = [x["topic"] for x in student.get("/api/topics/suggestions").json()["suggestions"]]
    assert after != before and after[0] == "Data structures and algorithms" and "Psychology" in after
    sid = student.post("/api/subjects/start", data={"topic": "Optics", "goal": "explore", "prior_knowledge": "none"}).json()["subject"]["id"]
    with dbmod.session_factory()() as db:
        from thinkfirst.platform.workspaces.models import Subject

        owner = db.get(Subject, sid).owner_id
        ctx = placement.learner_context(db, owner, sid)
        assert ctx["field"] == "Computer science" and ctx["status"] == "university"
        assert "Sam" not in str(ctx) and "2004" not in str(ctx)
        assert set(identity.learner_profile(db, owner)) == {"status", "field", "interests"}


def test_bad_values_are_refused_and_skipping_still_works(student):
    assert _save(student, status="astronaut").status_code == 422
    assert _save(student, hours_per_week=200).status_code == 422
    assert _save(student, birth_year=1700).status_code == 422
    assert _save(student).status_code == 200


def test_unknown_or_short_fields_do_not_match_by_accident(student):
    from thinkfirst.platform.workspaces.router import TOPIC_SUGGESTIONS, suggestions_for

    assert suggestions_for("Gastronomy", [])[0]["topic"] == TOPIC_SUGGESTIONS[0]["topic"]
    assert suggestions_for("Nursing", [])[0]["area"] == "Medicine"
    assert suggestions_for("Génie civil", [])[0]["area"] == "Electronics"
