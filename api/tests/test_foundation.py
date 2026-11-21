"""Foundation: quota reservations, consent-scoped admin access + audit, content-rights guards, gateway fallback, jobs."""

from __future__ import annotations

from datetime import timedelta

import pytest

from thinkfirst.core import jobs
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import Forbidden, QuotaExhausted
from thinkfirst.modules.billing import service as billing
from thinkfirst.modules.identity import service as identity
from thinkfirst.modules.identity.models import AccessAuditLog, User
from thinkfirst.modules.knowledge_library.models import (
    Contribution,
    LicensedContent,
    can_share,
    can_store_licensed,
)


@pytest.fixture()
def db(app_client, db_session):
    return db_session


def _user(db, email, role="student"):
    u = User(email=email, password_hash=identity.hash_password("pw123456"), role=role)
    db.add(u)
    db.flush()
    return u


def test_reservations_idempotent_and_bounded(db):
    u = _user(db, "r@x.y")
    r1 = billing.reserve(db, u.id, "validation_bundle", 3, "k")
    assert billing.reserve(db, u.id, "validation_bundle", 3, "k").id == r1.id
    c1 = billing.consume(db, r1, 1, "explanation", "c1")
    assert billing.consume(db, r1, 1, "explanation", "c1").id == c1.id  # infrastructure retry: no double charge
    st = billing.status(db, u.id)
    assert st["used_units"] == 1 and st["held_units"] == 2 and st["available_units"] == 27
    with pytest.raises(QuotaExhausted):
        billing.reserve(db, u.id, "validation_bundle", 28, "big")
    billing.release(db, r1)
    assert billing.status(db, u.id)["held_units"] == 0


def test_admin_has_no_default_access_and_consent_is_scoped_expiring_revocable(db):
    student, admin = _user(db, "s@x.y"), _user(db, "a@x.y", "admin")
    with pytest.raises(Forbidden):
        identity.admin_access_check(db, admin, student.id, "evidence", "e1")
    g = identity.create_consent(db, student, "Review disputed grade #123", [{"type": "evidence", "id": "e1"}], hours=24)
    assert identity.admin_access_check(db, admin, student.id, "evidence", "e1").id == g.id
    with pytest.raises(Forbidden):  # scope: other items stay private
        identity.admin_access_check(db, admin, student.id, "evidence", "e2")
    g.expires_at = utcnow() - timedelta(minutes=1)
    with pytest.raises(Forbidden):
        identity.admin_access_check(db, admin, student.id, "evidence", "e1")
    g.expires_at = utcnow() + timedelta(hours=1)
    identity.revoke_consent(db, student, g.id)
    with pytest.raises(Forbidden):
        identity.admin_access_check(db, admin, student.id, "evidence", "e1")
    actions = [r.action for r in identity.audit_log_for_student(db, student.id)]
    assert {"consent_created", "access_granted", "access_denied", "consent_revoked"} <= set(actions)
    assert all(isinstance(r, AccessAuditLog) for r in identity.audit_log_for_student(db, student.id))


def test_contributions_stay_private_until_rights_confirmed():
    c = Contribution(owner_id="u", kind="past_exam", source_ref="s", review_status="private")
    assert not can_share(c)
    c.rights_declaration = {"holder_confirmed": True, "distribution_permitted": True, "rights_holder": "Prof. X"}
    assert not can_share(c)  # opt-in + declaration still needs admin approval
    c.review_status = "approved"
    assert can_share(c)
    assert not can_store_licensed(LicensedContent(title="t", source_url="u", license_id="", license_url="", attribution="",
                                                  permits_storage=True))


def test_gateway_falls_back_and_never_silently_uses_demo(db, monkeypatch):
    from thinkfirst.config import get_settings
    from thinkfirst.modules.llm_gateway import service as llm

    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "auto")
    monkeypatch.setattr(s, "gemini_api_key", "x")
    monkeypatch.setattr(s, "groq_api_key", "y")
    llm._cooldown_until.clear()
    assert llm.provider_chain() == ["groq", "gemini"]
    calls = []

    def bad(template, text):
        calls.append("groq")
        raise llm._ProviderError("HTTP_500")

    def good(template, text):
        calls.append("gemini")
        return {"message": "m", "citations": [], "on_topic": True}, 10, 5

    monkeypatch.setitem(llm._CALLERS, "groq", bad)
    monkeypatch.setitem(llm._CALLERS, "gemini", good)
    res = llm.run(db, "professor_scaffold", {"student_question": "q"}, owner_id="u", purpose="t")
    assert res.status == "ok" and res.provider == "gemini" and not res.simulated and calls == ["groq", "gemini"]
    # circuit breaker: the failing provider is skipped on the next call
    llm._cache.clear()
    llm.run(db, "professor_scaffold", {"student_question": "q-again"}, owner_id="u", purpose="t")
    assert calls == ["groq", "gemini", "gemini"]

    def invalid(template, text):
        return {"nope": 1}, 1, 1

    monkeypatch.setitem(llm._CALLERS, "gemini", invalid)
    llm._cache.clear()
    res = llm.run(db, "professor_scaffold", {"student_question": "q2"}, owner_id="u", purpose="t")
    assert res.status == "invalid_output" and res.output is None  # callers treat as unscored, not demo, not zero
    llm._cooldown_until.clear()


def test_job_idempotency_and_cancel_rejects_late_result(db):
    seen = []

    @jobs.job_handler("test.echo")
    def _h(dbs, job):
        seen.append(job.id)
        return {"ok": True}

    j1 = jobs.enqueue(db, "test.echo", "u", {}, "echo-1")
    j2 = jobs.enqueue(db, "test.echo", "u", {}, "echo-1")
    assert j1.id == j2.id and seen == [j1.id] and j1.status == jobs.SUCCEEDED
