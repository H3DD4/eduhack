from __future__ import annotations

from sqlalchemy import select

from tests.conftest import register
from thinkfirst.config import get_settings
from thinkfirst.modules.accessibility.matching import likely_spelling_variation, normalize_answer


def test_profile_routes_are_hidden_when_feature_flag_is_off(app_client):
    register(app_client)
    assert app_client.get("/api/me/accessibility").status_code == 404


def test_profile_requires_consent_and_can_be_exported_and_deleted(app_client, monkeypatch, db_session):
    monkeypatch.setenv("ENABLE_ACCESSIBILITY_MODULE", "true")
    get_settings.cache_clear()
    try:
        register(app_client)
        assert app_client.patch("/api/me/accessibility", json={"changes": {"font_size": 18}}).status_code == 422
        denied = app_client.post("/api/me/accessibility/consent", json={"accepted": False})
        assert denied.status_code == 422
        accepted = app_client.post("/api/me/accessibility/consent", json={"accepted": True})
        assert accepted.status_code == 200
        profile = accepted.json()["profile"]
        assert profile["enabled"] is True
        assert profile["consent_given_at"]
        updated = app_client.patch("/api/me/accessibility", json={"changes": {"font_size": 18, "theme": "cream"}})
        assert updated.status_code == 200
        assert updated.json()["profile"]["font_size"] == 18
        assert app_client.patch("/api/me/accessibility", json={"changes": {"font_size": 30}}).status_code == 422
        assert app_client.patch("/api/me/accessibility", json={"changes": {"language_subject_ids": ["unknown"]}}).status_code == 422

        from thinkfirst.modules.tutor.llm import service as llm
        from thinkfirst.platform.identity.models import User
        from thinkfirst.platform.workspaces.models import Subject

        user = db_session.scalar(select(User).where(User.email == "student@example.com"))
        language_subject = Subject(owner_id=user.id, name="French", status="ready")
        db_session.add(language_subject)
        db_session.commit()
        assert app_client.patch("/api/me/accessibility", json={
            "changes": {"language_subject_ids": [language_subject.id]}
        }).status_code == 200

        captured_systems = []
        def capture(template, _prompt):
            captured_systems.append(template.system)
            return {"message": "A sourced answer.", "citations": [], "on_topic": True}, 0, 0

        monkeypatch.setitem(llm._CALLERS, "capture", capture)
        monkeypatch.setitem(llm.PROVIDER_LABELS, "capture", "Test provider")
        generated = llm.run(db_session, "professor_scaffold", {}, owner_id=user.id, purpose="test", provider="capture")
        assert generated.status == "ok" and "three-point summary" in captured_systems[-1]
        llm.run(db_session, "grade_short_answer", {}, owner_id=user.id, purpose="test", provider="capture",
                subject_id=language_subject.id)
        assert "minor spelling" not in captured_systems[-1]
        llm.run(db_session, "grade_short_answer", {}, owner_id=user.id, purpose="test", provider="capture",
                subject_id="non-language-subject")
        assert "minor spelling" in captured_systems[-1]
        db_session.commit()

        assert app_client.get("/api/me/accessibility/export").json()["profile"]["theme"] == "cream"
        assert app_client.delete("/api/me/accessibility").json() == {"deleted": True}
        assert app_client.get("/api/me/accessibility").json()["profile"] is None
    finally:
        get_settings.cache_clear()


def test_normalization_and_typo_detection_cover_english_french_and_arabic():
    assert normalize_answer("  ÉTÉ  ") == "ete"
    assert likely_spelling_variation("croisance", "croissance")
    assert likely_spelling_variation("distributon", "distribution")
    assert normalize_answer("مُعَلِّم") == normalize_answer("معلم")
    assert not likely_spelling_variation("x + 2", "x + 3")
    assert not likely_spelling_variation("explication", "application")
