"""workspaces service interface."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.deps import get_owned
from thinkfirst.core.errors import ValidationFailed
from thinkfirst.platform.workspaces.models import Subject


def create_subject(db: Session, owner_id: str, name: str, origin: str = "upload", goal: str | None = None,
                   exam_date: date | None = None) -> Subject:
    name = (name or "").strip()
    if not name:
        raise ValidationFailed("Name your subject.", field="name")
    subject = Subject(owner_id=owner_id, name=name[:200], origin=origin, goal=goal, exam_date=exam_date)
    db.add(subject)
    db.flush()
    events.publish(db, events.Event(events.WORKSPACE_CREATED, owner_id, {
        "subject_id": subject.id, "name": subject.name, "origin": origin, "goal": goal,
        "exam_date": exam_date.isoformat() if exam_date else None,
    }))
    return subject


def get_subject(db: Session, owner_id: str, subject_id: str) -> Subject:
    return get_owned(db, Subject, subject_id, owner_id)


def list_subjects(db: Session, owner_id: str) -> list[Subject]:
    return list(db.scalars(select(Subject).where(Subject.owner_id == owner_id, Subject.archived_at.is_(None))
                           .order_by(Subject.created_at.desc())).all())


def set_status(db: Session, owner_id: str, subject_id: str, status: str, graph_revision_id: str | None = None) -> None:
    s = get_subject(db, owner_id, subject_id)
    s.status = status
    if graph_revision_id:
        s.active_graph_revision_id = graph_revision_id


def set_last_concept(db: Session, owner_id: str, subject_id: str, concept_id: str) -> None:
    get_subject(db, owner_id, subject_id).last_concept_id = concept_id


def archive(db: Session, owner_id: str, subject_id: str) -> None:
    get_subject(db, owner_id, subject_id).archived_at = utcnow()


def subject_public(s: Subject) -> dict:
    return {"id": s.id, "name": s.name, "origin": s.origin, "status": s.status, "goal": s.goal,
            "exam_date": s.exam_date.isoformat() if s.exam_date else None,
            "active_graph_revision_id": s.active_graph_revision_id, "last_concept_id": s.last_concept_id,
            "created_at": s.created_at.isoformat()}
