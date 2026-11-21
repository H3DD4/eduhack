"""Section 4 in the app: level-matched questions, trigger questions, fresh retests, question/hint quality."""

from __future__ import annotations

from tests.conftest import concept_by_title, ready_subject
from tests.test_modules import _correct
from thinkfirst.core import db as dbmod
from thinkfirst.modules.adaptation.models import HintStat, ItemStat


def _start_practice(client, sid, cid):
    s = client.post(f"/api/subjects/{sid}/sessions", json={"concept_id": cid}).json()["session"]
    v = client.post(f"/api/sessions/{s['id']}/start", json={"idempotency_key": "k"}).json()
    for _ in range(2):
        v = client.post(f"/api/sessions/{s['id']}/advance", json={"expected_revision": v["session"]["revision"]}).json()
    return v


def _next(client, view):
    r = client.post(f"/api/sessions/{view['session']['id']}/practice/next", json={"expected_revision": view["session"]["revision"]})
    return r


def test_questions_get_harder_as_mastery_grows_and_never_repeat(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    view = _start_practice(student, sid, cid)
    first = view["current_task"]
    assert first["prompt"] == "Expand 2(x + 3)." and first["context"]["difficulty"] == "easy"  # new student: easy
    seen, difficulties = {first["context"]["item_key"]}, []
    t = first
    for i in range(6):
        student.post(f"/api/tasks/{t['id']}/submit", json={"answer": _correct(t["prompt"]), "expected_revision": t["revision"],
                                                           "idempotency_key": f"c{i}"})
        view = student.get(f"/api/sessions/{view['session']['id']}").json()
        r = _next(student, view)
        assert r.status_code == 200, r.text
        view = r.json()
        t = view["current_task"]
        assert t["context"]["item_key"] not in seen  # always a fresh question
        seen.add(t["context"]["item_key"])
        difficulties.append(t["context"]["difficulty"])
    assert "hard" in difficulties and difficulties[-1] != "easy"  # mastery up -> harder questions
    assert "closest to" in t["context"]["selection_reason"]


def test_after_help_the_retest_is_a_different_question(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    view = _start_practice(student, sid, cid)
    t = view["current_task"]
    for i in range(2):
        student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "idempotency_key": f"h{i}"})
    nxt = _next(student, view).json()["current_task"]
    assert nxt["context"]["item_key"] != t["context"]["item_key"]


def test_item_and_hint_statistics_and_quality_report(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    view = _start_practice(student, sid, cid)
    t = view["current_task"]
    student.post(f"/api/tasks/{t['id']}/help", json={"kind": "next", "idempotency_key": "h1"})  # hint shown
    student.post(f"/api/tasks/{t['id']}/submit", json={"answer": "2x + 6", "expected_revision": t["revision"],
                                                       "idempotency_key": "a"})  # assisted answer -> hint stat
    view = student.get(f"/api/sessions/{view['session']['id']}").json()
    t2 = _next(student, view).json()["current_task"]
    student.post(f"/api/tasks/{t2['id']}/submit", json={"answer": _correct(t2["prompt"]), "expected_revision": t2["revision"],
                                                        "idempotency_key": "b"})  # fresh unaided -> item stat
    with dbmod.session_factory()() as db:
        items = {(s.item_key, s.band): (s.attempts, s.correct) for s in db.query(ItemStat).all()}
        hints = db.query(HintStat).all()
    assert items == {(t2["context"]["item_key"], "low"): (1, 1.0)}  # helped item NOT counted as a fresh measure
    assert len(hints) == 1 and hints[0].shown == 1 and hints[0].followed_by_correct == 1.0
    rep = student.get("/api/quality").json()
    assert rep["items"][0]["status"] == "new" or rep["items"][0]["attempts"] == 1
    assert rep["hints"][0]["status"] == "ok"


def test_retired_question_is_never_served(student):
    with dbmod.session_factory()() as db:  # anonymous aggregates say strong students keep failing this item
        db.add_all([ItemStat(item_key="expand:2(x+3)", band="low", attempts=10, correct=9.0),
                    ItemStat(item_key="expand:2(x+3)", band="high", attempts=10, correct=2.0)])
        db.commit()
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    t = _start_practice(student, sid, cid)["current_task"]
    assert t["context"]["item_key"] != "expand:2(x+3)"
    rep = student.get("/api/quality").json()
    assert next(i for i in rep["items"] if i["item_id"] == "expand:2(x+3)")["status"] == "retire"


def test_running_out_of_fresh_questions_is_explicit(student):
    sid, road = ready_subject(student)
    cid = concept_by_title(road, "distributive")["id"]
    view = _start_practice(student, sid, cid)
    codes = []
    for _ in range(12):
        r = _next(student, view)
        if r.status_code != 200:
            codes.append(r.json()["error"]["code"])
            break
        view = r.json()
    assert codes == ["NO_MORE_ITEMS"]
