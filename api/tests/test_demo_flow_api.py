"""API integration: the 8-state demo storyboard end to end (text path; voice path via demo STT)."""

from __future__ import annotations

from tests.conftest import concept_by_title, ready_subject


def _start(client, sid, cid):
    s = client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": cid, "kind": "learn"}).json()["session"]
    v = client.post(f"/api/sessions/{s['id']}/start", json={"config": {"input_mode": "text"}, "idempotency_key": "k1"})
    assert v.status_code == 200, v.text
    return v.json()


def _advance(client, view):
    r = client.post(f"/api/sessions/{view['session']['id']}/advance", json={"expected_revision": view["session"]["revision"]})
    assert r.status_code == 200, r.text
    return r.json()


def test_states_1_to_4_upload_scope_roadmap(student):
    today = student.get("/api/today").json()
    assert today["next_action"]["kind"] == "add_subject"  # state 1: G01 empty, one CTA
    sid, road = ready_subject(student)  # states 2-3
    titles = [c["title"] for u in road["units"] for c in u["concepts"]]
    assert "The distributive property" in titles
    foundations = [c["title"] for u in road["units"] for c in u["foundations"]]
    assert "Order of operations" in foundations  # optional foundation branch
    c = concept_by_title(road, "distributive")
    assert c["citations"][0]["page"] == 2
    assert c["evidence"]["highest_text"] == "Not checked yet"
    detail = student.get(f"/api/subjects/{sid}/concepts/{c['id']}").json()
    assert any(p["is_foundation"] for p in detail["prerequisites"])


def test_full_validation_loop_text(student):
    sid, road = ready_subject(student)
    c = concept_by_title(road, "distributive")
    view = _start(student, sid, c["id"])
    assert view["session"]["stage"] == "recall"
    view = _advance(student, view)  # -> learn
    assert view["lesson"]["excerpt"]["page"] == 2
    assert "every term" in view["lesson"]["excerpt"]["text"]
    view = _advance(student, view)  # -> practice (introduced evidence recorded)
    task = view["current_task"]
    assert task["prompt"] == "Expand 2(x + 3)."
    assert task["origin"] == "unverified-source"
    assert task["solution"] is None and "hints" not in task  # never preloaded
    # state 1 of demo: 2x + 3 -> misconception flagged with one targeted question
    r = student.post(f"/api/tasks/{task['id']}/submit", json={"answer": "2x + 3", "expected_revision": task["revision"],
                                                             "idempotency_key": "a1"}).json()
    a = r["assessment"]
    assert a["outcome"] == "not_demonstrated"
    assert a["misconception"]["code"] == "distribution_first_term_only"
    assert "2 × 3" in a["misconception"]["targeted_question"]
    # duplicate submit with same key => same attempt (idempotent)
    r2 = student.post(f"/api/tasks/{task['id']}/submit", json={"answer": "2x + 3", "expected_revision": task["revision"],
                                                              "idempotency_key": "a1"}).json()
    assert r2["replayed"] is True
    rev = r["task"]["revision"]
    r = student.post(f"/api/tasks/{task['id']}/submit", json={"answer": "2x + 6", "expected_revision": rev,
                                                             "idempotency_key": "a2"}).json()
    assert r["assessment"]["outcome"] == "demonstrated"
    view = student.get(f"/api/sessions/{view['session']['id']}").json()
    view = _advance(student, view)  # -> explanation
    et = view["current_task"]
    assert et["kind"] == "explain"
    # typed explanation (identical rubric to voice)
    v = student.post(f"/api/tasks/{et['id']}/typed", json={"text": (
        "The 2 multiplies every term inside the brackets. So 2(x + 3) = 2x + 6. "
        "It works because 2(x + 3) means two groups of x + 3. "
        "It does not work over a product: 2(x · 3) is 6x, not 2x · 6.")}).json()
    conf = student.post(f"/api/tasks/{et['id']}/confirm", json={"version_id": v["version_id"], "idempotency_key": "e1"}).json()
    assert conf["job"]["status"] == "succeeded"
    view = student.get(f"/api/sessions/{view['session']['id']}").json()
    ea = view["current_task"]["last_assessment"]
    assert ea["simulated"] is True and "Simulated" in ea["method_label"]
    crit = {x["criterion"]: x for x in ea["criteria"]}
    assert crit["correctness"]["status"] == "demonstrated"
    assert crit["correctness"]["quotes"], "positive judgment must quote the confirmed text"
    for x in ea["criteria"]:
        for q in x["quotes"]:
            assert q["text"] in ("The 2 multiplies every term inside the brackets. So 2(x + 3) = 2x + 6. "
                                 "It works because 2(x + 3) means two groups of x + 3. "
                                 "It does not work over a product: 2(x · 3) is 6x, not 2x · 6.")
    ex = crit["example_application"]
    assert ex["status"] == "absent" and ex["quotes"] == []
    assert ex["missing"][0]["status"] == "not demonstrated" and ex["missing"][0]["source"]["page"] == 2
    view = _advance(student, view)  # -> followup (one persisted question)
    fu = view["current_task"]
    assert fu["stage"] == "followup" and fu["targets_criterion"] == "example_application"
    v = student.post(f"/api/tasks/{fu['id']}/typed", json={"text": "For example, 4(y + 2) = 4y + 8 because 4 multiplies both terms."}).json()
    student.post(f"/api/tasks/{fu['id']}/confirm", json={"version_id": v["version_id"], "idempotency_key": "f1"})
    view = student.get(f"/api/sessions/{view['session']['id']}").json()
    view = _advance(student, view)  # -> transfer
    tt = view["current_task"]
    assert tt["stage"] == "transfer" and tt["mode"] == "pending-commit" and tt["prompt"] is None  # mode before reveal
    r = student.post(f"/api/tasks/{tt['id']}/commit-mode", json={"mode": "independent", "expected_revision": tt["revision"]}).json()
    tt = r["task"]
    assert "3 packs of (x + 4) pens" in tt["prompt"]  # new expression and context, not 2(x + 3)
    # lock: help, professor and sources denied
    h = student.post(f"/api/tasks/{tt['id']}/help", json={"kind": "next", "idempotency_key": "h1"})
    assert h.status_code == 423 and h.json()["error"]["code"] == "TRANSFER_LOCKED"
    p = student.post("/api/professor/ask", json={"subject_id": sid, "question": "how to distribute?", "idempotency_key": "p1"})
    assert p.status_code == 423
    page = student.get(f"/api/documents/{c['citations'][0]['source_id']}/pages/2")
    assert page.status_code == 423
    r = student.post(f"/api/tasks/{tt['id']}/submit", json={"answer": "3(x + 4) and 3x + 12", "expected_revision": tt["revision"],
                                                           "idempotency_key": "t1"}).json()
    assert r["assessment"]["outcome"] == "demonstrated"
    assert student.get(f"/api/documents/{c['citations'][0]['source_id']}/pages/2").status_code == 200  # unlocked
    view = student.get(f"/api/sessions/{view['session']['id']}").json()
    view = _advance(student, view)  # -> summary
    summ = student.get(f"/api/sessions/{view['session']['id']}/summary").json()
    labels = {e["label"] for evs in summ["evidence_by_stage"].values() for e in evs}
    assert "applied_independently" in labels and "practised_with_support" in labels and "introduced" in labels
    assert summ["application"] == "Applied independently (no in-app help)"
    tr = summ["evidence_by_stage"]["transfer"][0]
    assert tr["label_text"] == "Applied independently (no in-app help)"
    # S03 reflection + persisted review date
    student.post(f"/api/sessions/{view['session']['id']}/reflection", json={"text": "Draw the groups first."})
    rv = student.post(f"/api/sessions/{view['session']['id']}/review", json={}).json()["review"]
    assert rv["due_on"] == summ["default_review_on"]
    student.post(f"/api/sessions/{view['session']['id']}/complete")
    assert student.get("/api/reviews").json()["reviews"][0]["due_on"] == rv["due_on"]
    road = student.get(f"/api/subjects/{sid}/roadmap").json()
    c2 = concept_by_title(road, "distributive")
    assert "applied_independently" in c2["evidence"]["states"]
    assert c2["evidence"]["review_due_on"] == rv["due_on"]
    receipt = student.get(f"/api/evidence/{tr['id']}").json()
    assert receipt["task"]["novelty"]["different_context"] is True
    quota = student.get("/api/billing/quota").json()
    assert quota["used_units"] == 3 and quota["held_units"] == 0  # one bundle charge, no double charges


def test_voice_path_demo_stt_requires_confirmation(student):
    sid, road = ready_subject(student)
    c = concept_by_title(road, "distributive")
    view = _start(student, sid, c["id"])
    for _ in range(2):
        view = _advance(student, view)
    task = view["current_task"]
    student.post(f"/api/tasks/{task['id']}/submit", json={"answer": "2x+6", "expected_revision": task["revision"], "idempotency_key": "x"})
    view = _advance(student, student.get(f"/api/sessions/{view['session']['id']}").json())
    et = view["current_task"]
    up = student.post(f"/api/tasks/{et['id']}/audio", data={"idempotency_key": "take1"},
                      files={"file": ("take.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")})
    assert up.status_code == 200, up.text
    assert up.json()["job"]["status"] == "succeeded"
    # retry after a dropped response: reconciles to the same take
    up2 = student.post(f"/api/tasks/{et['id']}/audio", data={"idempotency_key": "take1"},
                       files={"file": ("take.webm", b"\x1aE\xdf\xa3fake-webm-bytes", "audio/webm")})
    assert up2.json()["take_id"] == up.json()["take_id"]
    st = student.get(f"/api/tasks/{et['id']}/explain").json()
    orig = st["versions"][0]
    assert orig["kind"] == "original_asr" and "Demo transcription" in orig["source_label"]
    assert orig["unresolved"][0]["text"] == "brackets"
    # no assessment before confirmation; unresolved spans must be handled explicitly
    r = student.post(f"/api/tasks/{et['id']}/confirm", json={"version_id": orig["id"], "idempotency_key": "c1"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "UNRESOLVED_SPANS"
    corr = student.post(f"/api/tasks/{et['id']}/corrections", json={"base_version_id": orig["id"], "text": orig["text"],
                                                                     "resolved_span_ids": ["u1"]}).json()
    assert corr["unresolved"] == []
    r = student.post(f"/api/tasks/{et['id']}/confirm", json={"version_id": corr["version_id"], "idempotency_key": "c2",
                                                             "supplement": "For example, 4(y + 2) = 4y + 8."}).json()
    assert r["audio_deleted"] is True  # default retention
    st = student.get(f"/api/tasks/{et['id']}/explain").json()
    assert st["takes"][0]["playable"] is False
    assert student.get(f"/api/audio/{st['takes'][0]['id']}").status_code == 404
    assert any(v["kind"] == "original_asr" for v in st["versions"])  # transcript history remains
