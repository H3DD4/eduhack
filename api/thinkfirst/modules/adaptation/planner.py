"""Planner = calendar + priorities.

Events on the calendar:
  * deadlines the student creates (exam, certificate, assignment, goal; importance 1-3), optionally tied to a subject
  * the exam date given in the start wizard (subject.exam_date)
  * booked reviews (end-of-session review dates) and the learner engine's memory-based review dates

Priorities ("what to study this week"): every open deadline with a subject gets
    pressure = importance x concepts still to learn / max(1, days left)
and a concrete pace ("about N concepts per week until <date>"). Concepts still to learn come from the learner engine
(level < 4 Proficient, foundations excluded), so the plan shrinks as the student masters concepts.
Read-only except the deadline CRUD helpers.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core.errors import NotFound, ValidationFailed
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.workspaces import service as workspaces
from thinkfirst.platform.workspaces.models import Deadline

KINDS = {"exam": "Exam", "certificate": "Certificate", "assignment": "Assignment", "goal": "Goal"}


def deadline_public(d: Deadline, names: dict[str, str]) -> dict:
    return {"id": d.id, "subject_id": d.subject_id, "subject_name": names.get(d.subject_id or ""), "title": d.title,
            "kind": d.kind, "kind_label": KINDS.get(d.kind, d.kind), "due_on": d.due_on.isoformat(),
            "importance": d.importance, "done": d.done, "notes": d.notes}


def _validate(db: Session, owner_id: str, data: dict) -> dict:
    out = {}
    if "title" in data:
        title = str(data["title"] or "").strip()
        if not title:
            raise ValidationFailed("Give the deadline a name.", field="title")
        out["title"] = title[:200]
    if "kind" in data:
        if data["kind"] not in KINDS:
            raise ValidationFailed("Choose exam, certificate, assignment or goal.", field="kind")
        out["kind"] = data["kind"]
    if "due_on" in data:
        try:
            out["due_on"] = date.fromisoformat(str(data["due_on"]))
        except ValueError as exc:
            raise ValidationFailed("Use a valid date.", field="due_on") from exc
    if "importance" in data:
        imp = int(data["importance"] or 2)
        if imp not in (1, 2, 3):
            raise ValidationFailed("Importance is 1, 2 or 3.", field="importance")
        out["importance"] = imp
    if "subject_id" in data:
        sid = data["subject_id"] or None
        if sid:
            workspaces.get_subject(db, owner_id, sid)  # ownership check
        out["subject_id"] = sid
    for k in ("done", "notes"):
        if k in data:
            out[k] = bool(data[k]) if k == "done" else str(data[k] or "")[:2000]
    return out


def create_deadline(db: Session, owner_id: str, data: dict) -> Deadline:
    vals = _validate(db, owner_id, data)
    if not {"title", "due_on"} <= set(vals):
        raise ValidationFailed("A deadline needs a name and a date.")
    d = Deadline(owner_id=owner_id, **vals)
    db.add(d)
    db.flush()
    return d


def _get(db: Session, owner_id: str, deadline_id: str) -> Deadline:
    d = db.get(Deadline, deadline_id)
    if d is None or d.owner_id != owner_id:
        raise NotFound("Deadline not found.")
    return d


def update_deadline(db: Session, owner_id: str, deadline_id: str, data: dict) -> Deadline:
    d = _get(db, owner_id, deadline_id)
    for k, v in _validate(db, owner_id, data).items():
        setattr(d, k, v)
    db.flush()
    return d


def delete_deadline(db: Session, owner_id: str, deadline_id: str) -> None:
    db.delete(_get(db, owner_id, deadline_id))
    db.flush()


def _remaining(db: Session, owner_id: str, subject) -> tuple[int, int]:
    """(concepts still to learn, total core concepts) from the learner engine."""
    if subject.status != "ready":
        return 0, 0
    from thinkfirst.modules.adaptation import service as adaptation

    concepts = [c for c in ingestion.active_concepts(db, owner_id, subject.id) if not c.is_foundation]
    state = adaptation.learner_state(db, owner_id, subject.id)["concepts"]
    left = sum(1 for c in concepts if (state.get(c.id) or {}).get("level", 0) < 4)
    return left, len(concepts)


def planner(db: Session, owner_id: str, start: date | None = None, end: date | None = None) -> dict:
    from thinkfirst.data.student_profile import service as profile
    from thinkfirst.modules.adaptation import service as adaptation

    today = date.today()
    start = start or today.replace(day=1) - timedelta(days=7)
    end = end or start + timedelta(days=70)
    subjects = workspaces.list_subjects(db, owner_id)
    names = {s.id: s.name for s in subjects}
    by_id = {s.id: s for s in subjects}
    deadlines = db.scalars(select(Deadline).where(Deadline.owner_id == owner_id).order_by(Deadline.due_on)).all()
    events: list[dict] = []
    for d in deadlines:
        events.append({"type": d.kind, "date": d.due_on.isoformat(), "title": d.title, "subject_id": d.subject_id,
                       "subject_name": names.get(d.subject_id or ""), "deadline_id": d.id, "importance": d.importance,
                       "done": d.done})
    for s in subjects:
        if s.exam_date:
            events.append({"type": "exam", "date": s.exam_date.isoformat(), "title": f"Exam · {s.name}", "subject_id": s.id,
                           "subject_name": s.name, "deadline_id": None, "importance": 3, "done": False, "from_wizard": True})
    for r in profile.reviews(db, owner_id):
        if r.status == "scheduled":
            events.append({"type": "review", "date": r.due_on.isoformat(), "title": f"Review · {names.get(r.subject_id, '')}",
                           "subject_id": r.subject_id, "subject_name": names.get(r.subject_id), "concept_id": r.concept_id})
    for s in subjects:  # memory-based review dates from the learner engine (when recall drops below 85 %)
        if s.status != "ready":
            continue
        titles = {c.id: c.title for c in ingestion.active_concepts(db, owner_id, s.id)}
        for cid, st in adaptation.learner_state(db, owner_id, s.id)["concepts"].items():
            if st.get("review_due_at") and cid in titles:
                due = max(datetime.fromisoformat(st["review_due_at"]).date(), today)
                events.append({"type": "memory_review", "date": due.isoformat(), "title": f"Refresh “{titles[cid]}”",
                               "subject_id": s.id, "subject_name": s.name, "concept_id": cid})
    events = [e for e in events if start.isoformat() <= e["date"] <= end.isoformat()]
    events.sort(key=lambda e: (e["date"], e["type"]))

    targets: list[tuple[str, date, int, str]] = []  # (subject_id, due, importance, label)
    for d in deadlines:
        if d.subject_id and not d.done and d.due_on >= today:
            targets.append((d.subject_id, d.due_on, d.importance, d.title))
    for s in subjects:
        if s.exam_date and s.exam_date >= today:
            targets.append((s.id, s.exam_date, 3, f"Exam · {s.name}"))
    priorities = []
    for sid, due, imp, label in targets:
        subject = by_id.get(sid)
        if subject is None:
            continue
        left, total = _remaining(db, owner_id, subject)
        days = max(1, (due - today).days)
        weeks = max(1.0, days / 7)
        pace = math.ceil(left / weeks) if left else 0
        priorities.append({
            "subject_id": sid, "subject_name": subject.name, "deadline": label, "due_on": due.isoformat(), "days_left": days,
            "importance": imp, "to_learn": left, "total": total, "pressure": round(imp * left / days, 3),
            "pace": (f"about {pace} concept(s) per week until {due.isoformat()}" if left
                     else "everything is at Proficient or above: review and mock questions"),
            "reason": (f"{left} of {total} concepts still below Proficient, {days} day(s) left"
                       + (", high importance" if imp == 3 else "")),
            "next_href": f"/subjects/{sid}/start",
        })
    priorities.sort(key=lambda p: (-p["pressure"], p["days_left"]))
    return {"from": start.isoformat(), "to": end.isoformat(), "today": today.isoformat(), "events": events,
            "deadlines": [deadline_public(d, names) for d in deadlines], "priorities": priorities,
            "subjects": [{"id": s.id, "name": s.name} for s in subjects]}
