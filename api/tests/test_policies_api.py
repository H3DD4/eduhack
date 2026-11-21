"""API tests: transfer lock + conversion race, reveal, quota/Q01, isolation, leases, deletion, logging, ingestion recovery."""

from __future__ import annotations

import json

from sqlalchemy import select

from tests.conftest import concept_by_title, ready_subject, register


def _to_stage(client, stage):
    sid, road = ready_subject(client)
    c = concept_by_title(road, "distributive")
    s = client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": c["id"]}).json()["session"]
    view = client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "s"}).json()
    while view["session"]["stage"] != stage:
        cur = view["current_task"]
        if cur and cur["kind"] == "expand" and cur["status"] == "open":
            client.post(f"/api/tasks/{cur['id']}/submit", json={"answer": "2x+6", "expected_revision": cur["revision"], "idempotency_key": "q"})
        if cur and cur["kind"] == "explain" and not cur["last_assessment"]:
            v = client.post(f"/api/tasks/{cur['id']}/typed", json={"text": "Each term is multiplied."}).json()
            client.post(f"/api/tasks/{cur['id']}/confirm", json={"version_id": v["version_id"], "idempotency_key": cur["id"]})
        view = client.get(f"/api/sessions/{s['id']}").json()
        view = client.post(f"/api/sessions/{s['id']}/advance", json={"expected_revision": view["session"]["revision"]}).json()
    return sid, c, view


def test_reveal_requires_confirmation_and_never_counts_independent(student):
    sid, c, view = _to_stage(student, "practice")
    t = view["current_task"]
    for i in range(4):
        r = student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "idempotency_key": f"h{i}"})
        assert r.status_code == 200 and r.json()["revealed"] is False
    r = student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "idempotency_key": "h5"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "REVEAL_CONFIRMATION_REQUIRED"
    r = student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "confirm_reveal": True, "idempotency_key": "h6"}).json()
    assert r["revealed"] and "2x + 6" in r["content"] and r["fresh_task_id"]
    task = student.get(f"/api/tasks/{t['id']}").json()["task"]
    assert task["status"] == "ended_assisted"
    fresh = student.get(f"/api/tasks/{r['fresh_task_id']}").json()["task"]
    assert fresh["origin"] == "ai-generated" and fresh["prompt"] != t["prompt"] and fresh["solution"] is None


def test_help_before_typing_has_no_minimum(student):
    _, _, view = _to_stage(student, "practice")
    t = view["current_task"]
    r = student.post(f"/api/tasks/{t['id']}/help", json={"kind": "dont_know", "idempotency_key": "d"}).json()
    assert r["level"] == 1 and r["step"] == "clarify"


def test_conversion_is_irreversible_and_races_cannot_count_independent(student):
    sid, c, view = _to_stage(student, "transfer")
    t = view["current_task"]
    t = student.post(f"/api/tasks/{t['id']}/commit-mode", json={"mode": "independent", "expected_revision": t["revision"]}).json()["task"]
    stale_rev = t["revision"]
    conv = student.post(f"/api/tasks/{t['id']}/convert", json={"expected_revision": stale_rev})
    assert conv.status_code == 200 and conv.json()["task"]["mode"] == "guided-transfer"
    # a raced submission from another tab with the pre-conversion revision is rejected
    r = student.post(f"/api/tasks/{t['id']}/submit", json={"answer": "3(x+4) and 3x+12", "expected_revision": stale_rev, "idempotency_key": "race"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "STALE_REVISION"
    # help now available; result is assisted
    assert student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "idempotency_key": "hh"}).status_code == 200
    cur = student.get(f"/api/tasks/{t['id']}").json()["task"]
    r = student.post(f"/api/tasks/{t['id']}/submit", json={"answer": "3(x+4) and 3x+12", "expected_revision": cur["revision"], "idempotency_key": "ok"}).json()
    assert r["assessment"]["outcome"] == "demonstrated"
    ev = student.get(f"/api/subjects/{sid}/evidence").json()["evidence"]
    tr = [e for e in ev if e["stage"] == "transfer"]
    assert tr and all(e["label"] != "applied_independently" for e in tr)
    assert student.post(f"/api/tasks/{t['id']}/convert", json={"expected_revision": 99}).status_code == 409


def test_lock_survives_pause_and_other_tabs(student):
    sid, c, view = _to_stage(student, "transfer")
    t = view["current_task"]
    student.post(f"/api/tasks/{t['id']}/commit-mode", json={"mode": "independent", "expected_revision": t["revision"]})
    sess = view["session"]
    lease = student.post(f"/api/sessions/{sess['id']}/lease", json={"device_id": "tab-a"}).json()
    student.post(f"/api/sessions/{sess['id']}/pause", headers={"x-lease-token": lease["lease_token"]},
                 json={"expected_revision": lease["revision"], "checkpoint": {"phase": "transfer_answer"}})
    # deep link to an earlier practice task's help from a second tab is still denied
    practice = next(x for x in view["tasks"] if x["stage"] == "practice")
    assert student.post(f"/api/tasks/{practice['id']}/help", json={"kind": "next", "idempotency_key": "z"}).status_code == 423
    # prior feedback hidden while locked
    assert student.get(f"/api/tasks/{practice['id']}").json()["task"]["last_assessment"] is None


def test_quota_boundary_q01_and_no_double_charge(app_client, db_session):
    from thinkfirst.platform.identity.models import User

    register(app_client, "q@example.com")
    sid, road = ready_subject(app_client)
    c = concept_by_title(road, "distributive")
    user = db_session.scalar(select(User).where(User.email == "q@example.com"))
    user.is_demo = True
    db_session.commit()
    assert app_client.post("/api/billing/demo/usage", json={"used_units": 29}).status_code == 200
    s = app_client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": c["id"]}).json()["session"]
    r = app_client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "s"})
    assert r.status_code == 402
    err = r.json()["error"]
    assert err["code"] == "QUOTA_EXHAUSTED" and err["quota"]["available_units"] == 1 and "resets_at" in err["quota"]
    assert err["pending_intent"]["session_id"] == s["id"] and "price" not in json.dumps(err)
    assert app_client.get(f"/api/sessions/{s['id']}").json()["session"]["status"] == "draft"  # intent preserved
    app_client.post("/api/billing/demo/usage", json={"used_units": 0})
    ok = app_client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "s"})
    again = app_client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "s"})
    assert ok.status_code == again.status_code == 200
    q = app_client.get("/api/billing/quota").json()
    assert q["held_units"] == 3  # one reservation for the whole bundle, not two


def test_private_data_isolation(app_client):
    register(app_client, "a@example.com")
    sid, road = ready_subject(app_client)
    cid = concept_by_title(road, "distributive")["id"]
    app_client.post("/api/auth/logout")
    register(app_client, "b@example.com")
    for url in (f"/api/subjects/{sid}", f"/api/subjects/{sid}/roadmap", f"/api/subjects/{sid}/setup",
                f"/api/subjects/{sid}/concepts/{cid}", f"/api/subjects/{sid}/evidence"):
        assert app_client.get(url).status_code == 404, url
    assert app_client.get("/api/subjects").json()["subjects"] == []
    assert app_client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": cid}).status_code == 404


def test_lease_takeover_and_stale_revision(student):
    _, _, view = _to_stage(student, "practice")
    sid = view["session"]["id"]
    a = student.post(f"/api/sessions/{sid}/lease", json={"device_id": "A"}).json()
    held = student.post(f"/api/sessions/{sid}/lease", json={"device_id": "B"})
    assert held.status_code == 409 and held.json()["error"]["code"] == "LEASE_HELD"
    b = student.post(f"/api/sessions/{sid}/lease", json={"device_id": "B", "takeover": True}).json()
    old = student.put(f"/api/sessions/{sid}/checkpoint", headers={"x-lease-token": a["lease_token"]},
                      json={"expected_revision": a["revision"], "checkpoint": {"drafts": {"x": "old"}}})
    assert old.status_code == 409 and old.json()["error"]["code"] == "LEASE_LOST"
    ok = student.put(f"/api/sessions/{sid}/checkpoint", headers={"x-lease-token": b["lease_token"]},
                     json={"expected_revision": b["revision"], "checkpoint": {"drafts": {"x": "new"}}})
    assert ok.status_code == 200
    stale = student.put(f"/api/sessions/{sid}/checkpoint", headers={"x-lease-token": b["lease_token"]},
                        json={"expected_revision": b["revision"], "checkpoint": {"drafts": {"x": "older"}}})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_REVISION"  # no last-write-wins
    student.post(f"/api/sessions/{sid}/pause", headers={"x-lease-token": b["lease_token"]},
                 json={"expected_revision": ok.json()["revision"], "checkpoint": {"phase": "answer"}})
    today = student.get("/api/today").json()
    assert today["next_action"]["kind"] == "resume" and today["next_action"]["session_id"] == sid
    v = student.post(f"/api/sessions/{sid}/resume", headers={"x-lease-token": b["lease_token"]}).json()
    assert v["session"]["status"] == "active" and v["session"]["checkpoint"]["drafts"] == {"x": "new"}


def test_delete_attempt_removes_content_and_evidence(student):
    sid, c, view = _to_stage(student, "explanation")
    ev = [e for e in student.get(f"/api/subjects/{sid}/evidence").json()["evidence"] if e["stage"] == "practice"][0]
    r = student.delete(f"/api/evidence/{ev['id']}/attempt").json()
    assert r["status"] == "completed"
    left = student.get(f"/api/subjects/{sid}/evidence").json()["evidence"]
    assert all(e["id"] != ev["id"] for e in left)
    assert student.get(f"/api/evidence/{ev['id']}").json().get("deleted") is True


def test_metadata_only_llm_log_and_logs(student, db_session, capsys):
    from thinkfirst.modules.tutor.llm.models import LLMCallLog

    secret = "My secret explanation about every term inside the brackets."
    sid, c, view = _to_stage(student, "explanation")
    t = view["current_task"]
    v = student.post(f"/api/tasks/{t['id']}/typed", json={"text": secret}).json()
    student.post(f"/api/tasks/{t['id']}/confirm", json={"version_id": v["version_id"], "idempotency_key": "m"})
    rows = db_session.scalars(select(LLMCallLog)).all()
    assert rows
    for row in rows:
        dumped = json.dumps({k: str(getattr(row, k)) for k in row.__table__.columns.keys()})
        assert "secret" not in dumped
    out = capsys.readouterr()
    assert "secret" not in out.out and "secret" not in out.err


def test_ingestion_recovery_partial_success(student):
    from thinkfirst.fixtures import demo_course_pdf

    r = student.post("/api/subjects", data={"name": "Mixed", "role": "course", "rights_ack": "true"},
                     files=[("files", ("good.pdf", demo_course_pdf(), "application/pdf")),
                            ("files", ("bad.exe", b"MZ....", "application/octet-stream")),
                            ("files", ("broken.pdf", b"%PDF-1.4 garbage", "application/pdf"))])
    sid = r.json()["subject"]["id"]
    setup = student.get(f"/api/subjects/{sid}/setup").json()
    st = {s["filename"]: s for s in setup["sources"]}
    assert st["bad.exe"]["error_code"] == "UNSUPPORTED_TYPE"
    assert st["broken.pdf"]["status"] == "needs_attention"
    assert st["good.pdf"]["status"] == "awaiting_confirmation" and setup["proposal"]  # partial success retained
    ex = student.post(f"/api/sources/{st['broken.pdf']['id']}/exclude").json()
    assert ex["status"] == "excluded"
    student.post(f"/api/sources/{st['bad.exe']['id']}/retry")
    setup2 = student.get(f"/api/subjects/{sid}/setup").json()
    assert len(setup2["sources"]) == 3  # retries never duplicate sources


def test_rights_ack_required_and_limits_visible(student):
    r = student.post("/api/subjects", data={"name": "X", "rights_ack": "false", "paste_text": "1.1 Topic\nObjective: y"})
    assert r.status_code == 422
    lim = student.get("/api/limits").json()
    assert lim["max_files_per_batch"] == 5 and lim["max_pages_per_file"] == 200


def test_source_removal_creates_tombstone(student):
    sid, road = ready_subject(student)
    c = concept_by_title(road, "distributive")
    src = c["citations"][0]["source_id"]
    assert student.get(f"/api/sources/{src}/impact").json()["cited_concepts"] >= 1
    student.delete(f"/api/sources/{src}")
    page = student.get(f"/api/documents/{src}/pages/2").json()
    assert page["tombstone"] is True


def test_csrf_header_required(app_client):
    del app_client.headers["x-thinkfirst-client"]
    assert app_client.post("/api/auth/register", json={"email": "z@z.z", "password": "12345678"}).status_code == 403


def test_auth_errors_do_not_leak(app_client):
    register(app_client, "e@example.com")
    app_client.post("/api/auth/logout")
    r = app_client.post("/api/auth/login", json={"email": "e@example.com", "password": "wrong-password"})
    assert r.status_code == 401 and "wrong-password" not in r.text
    assert app_client.get("/api/today").status_code == 401
