"""Planner (deadlines + calendar events + priorities) and progress metrics."""

from __future__ import annotations

from datetime import date, timedelta

from tests.test_learning_path import _start


def test_deadlines_crud_calendar_events_and_priorities(student):
    sid = _start(student, "none")  # exam wizard path (exam_date 2030-06-01)
    due = (date.today() + timedelta(days=14)).isoformat()
    bad = student.post("/api/deadlines", json={"title": "", "due_on": due})
    assert bad.status_code == 422
    r = student.post("/api/deadlines", json={"title": "Partiel circuits", "kind": "exam", "due_on": due,
                                             "importance": 3, "subject_id": sid})
    assert r.status_code == 200, r.text
    did = r.json()["deadline"]["id"]
    student.post("/api/deadlines", json={"title": "AWS certificate", "kind": "certificate",
                                         "due_on": (date.today() + timedelta(days=40)).isoformat(), "importance": 1})
    p = student.get("/api/planner").json()
    kinds = {e["type"] for e in p["events"]}
    assert {"exam", "certificate"} <= kinds
    assert [d["title"] for d in p["deadlines"]] == ["Partiel circuits", "AWS certificate"]
    top = p["priorities"][0]
    assert top["subject_id"] == sid and top["deadline"] == "Partiel circuits" and top["to_learn"] == 3
    assert top["days_left"] == 14 and "per week" in top["pace"]
    assert student.patch(f"/api/deadlines/{did}", json={"done": True}).json()["deadline"]["done"] is True
    assert all(x["deadline"] != "Partiel circuits" for x in student.get("/api/planner").json()["priorities"])
    assert student.delete(f"/api/deadlines/{did}").status_code == 200
    assert student.patch(f"/api/deadlines/{did}", json={"done": False}).status_code == 404
    # exam date from the wizard can be changed
    r = student.patch(f"/api/subjects/{sid}/intent", json={"exam_date": "2031-01-15"})
    assert r.json()["subject"]["exam_date"] == "2031-01-15"


def test_deadline_cannot_point_to_another_students_subject(app_client):
    from tests.conftest import register

    register(app_client, "a@example.com")
    sid = _start(app_client, "none")
    app_client.post("/api/auth/logout")
    register(app_client, "b@example.com")
    r = app_client.post("/api/deadlines", json={"title": "x", "due_on": "2031-01-01", "subject_id": sid})
    assert r.status_code == 404


def test_progress_metrics_overview_graph_and_activity(student):
    sid = _start(student, "none")
    m = student.get("/api/me/progress-metrics").json()
    assert m["overview"]["subjects"] == 1 and m["overview"]["concepts_total"] == 3
    assert len(m["activity"]) == 84 and m["activity"][-1]["date"] == date.today().isoformat()
    sub = m["subjects"][0]
    assert sub["id"] == sid and sub["ready"] and sub["level"] == "Beginner"
    assert {n["key"] for n in sub["nodes"]} == {"3.1", "3.2", "3.3"}
    assert next(n for n in sub["nodes"] if n["key"] == "3.2")["prerequisites"] == ["3.1"]
    assert sum(x["count"] for x in m["level_distribution"]) == 3
