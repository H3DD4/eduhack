"""S01/S02/S03, P01, F01, G01 HTTP API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.identity.models import User
from thinkfirst.modules.tutor import service

router = APIRouter(tags=["tutor"])


class NewSession(BaseModel):
    concept_id: str
    kind: str = "learn"
    parent_session_id: str | None = None


@router.post("/subjects/{subject_id}/sessions")
def new_session(subject_id: str, body: NewSession, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = service.create_session(db, user.id, subject_id, body.concept_id, body.kind, body.parent_session_id)
    return {"session": service.session_public(s)}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.session_view(db, user.id, session_id)


class StartIn(BaseModel):
    config: dict = {}
    idempotency_key: str


@router.post("/sessions/{session_id}/start")
def start(session_id: str, body: StartIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.start_session(db, user.id, session_id, body.config, body.idempotency_key)
    return service.session_view(db, user.id, session_id)


class LeaseIn(BaseModel):
    device_id: str
    takeover: bool = False


@router.post("/sessions/{session_id}/lease")
def lease(session_id: str, body: LeaseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = service.acquire_lease(db, user.id, session_id, body.device_id, body.takeover)
    return {"lease_token": s.lease_token, "revision": s.revision,
            "lease_expires_at": s.lease_expires_at.isoformat() if s.lease_expires_at else None}


class CheckpointIn(BaseModel):
    expected_revision: int
    checkpoint: dict = {}


@router.put("/sessions/{session_id}/checkpoint")
def checkpoint(session_id: str, body: CheckpointIn, x_lease_token: str | None = Header(default=None),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = service.save_checkpoint(db, user.id, session_id, body.expected_revision, x_lease_token, body.checkpoint)
    return {"revision": s.revision, "saved_at": s.updated_at.isoformat() if s.updated_at else None}


@router.post("/sessions/{session_id}/pause")
def pause(session_id: str, body: CheckpointIn, x_lease_token: str | None = Header(default=None),
          user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = service.pause(db, user.id, session_id, body.expected_revision, x_lease_token, body.checkpoint)
    return {"status": s.status, "revision": s.revision}


@router.post("/sessions/{session_id}/resume")
def resume(session_id: str, x_lease_token: str | None = Header(default=None), user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    service.resume(db, user.id, session_id, x_lease_token)
    return service.session_view(db, user.id, session_id)


class AdvanceIn(BaseModel):
    expected_revision: int


@router.post("/sessions/{session_id}/advance")
def advance(session_id: str, body: AdvanceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service.advance(db, user.id, session_id, body.expected_revision)
    return service.session_view(db, user.id, session_id)


class SubmitIn(BaseModel):
    answer: str
    expected_revision: int
    idempotency_key: str


@router.post("/tasks/{task_id}/submit")
def submit(task_id: str, body: SubmitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.submit_answer(db, user.id, task_id, body.answer, body.expected_revision, body.idempotency_key)


class HelpIn(BaseModel):
    kind: str = "next"  # next | dont_know
    confirm_reveal: bool = False
    idempotency_key: str


@router.post("/tasks/{task_id}/help")
def help_step(task_id: str, body: HelpIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.help_step(db, user.id, task_id, body.kind, body.confirm_reveal, body.idempotency_key)


class ModeIn(BaseModel):
    mode: str
    expected_revision: int


@router.post("/tasks/{task_id}/commit-mode")
def commit_mode(task_id: str, body: ModeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = service.commit_mode(db, user.id, task_id, body.mode, body.expected_revision)
    return {"task": service.task_public(db, t)}


class RevIn(BaseModel):
    expected_revision: int


@router.post("/tasks/{task_id}/convert")
def convert(task_id: str, body: RevIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = service.convert_to_guided(db, user.id, task_id, body.expected_revision)
    return {"task": service.task_public(db, t)}


@router.post("/tasks/{task_id}/abandon")
def abandon(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"task": service.task_public(db, service.abandon(db, user.id, task_id))}


@router.post("/tasks/{task_id}/keep-unscored")
def keep_unscored(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"task": service.task_public(db, service.keep_unscored(db, user.id, task_id))}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from thinkfirst.modules.tutor import policy

    t = service.get_task(db, user.id, task_id)
    lock = policy.active_lock(db, user.id, t.subject_id)
    return {"task": service.task_public(db, t, hide_feedback=lock is not None and lock.id != t.id)}


class AskIn(BaseModel):
    subject_id: str
    question: str
    task_id: str | None = None
    idempotency_key: str


@router.post("/professor/ask")
def professor(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.professor_ask(db, user.id, body.subject_id, body.question, body.task_id, body.idempotency_key)


@router.get("/sessions/{session_id}/summary")
def summary(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.summary(db, user.id, session_id)


class ReflectionIn(BaseModel):
    text: str = ""
    skipped: bool = False


@router.post("/sessions/{session_id}/reflection")
def reflection(session_id: str, body: ReflectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = service.save_reflection(db, user.id, session_id, body.text, body.skipped)
    return {"text": r.text, "skipped": r.skipped}


class ReviewIn(BaseModel):
    due_on: date | None = None


@router.post("/sessions/{session_id}/review")
def review(session_id: str, body: ReviewIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"review": service.book_review(db, user.id, session_id, body.due_on)}


@router.post("/sessions/{session_id}/complete")
def complete(session_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"session": service.session_public(service.complete(db, user.id, session_id))}


@router.get("/today")
def today(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.today(db, user.id)
