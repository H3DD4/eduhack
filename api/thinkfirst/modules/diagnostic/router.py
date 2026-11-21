from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.diagnostic import service
from thinkfirst.platform.identity.models import User
from thinkfirst.platform.workspaces import service as workspaces

router = APIRouter(tags=["diagnostic"])


@router.get("/subjects/{subject_id}/diagnostic")
def items(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.diagnostic_overview(db, user.id, subject_id)


@router.get("/subjects/{subject_id}/knowledge-space")
def knowledge_space(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.knowledge_space_public(db, user.id, subject_id)


class StartDiagnosticIn(BaseModel):
    restart: bool = False


@router.post("/subjects/{subject_id}/diagnostic/start")
def start_adaptive(subject_id: str, body: StartDiagnosticIn | None = None, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.start_diagnostic(db, user.id, subject_id, restart=bool(body and body.restart))


class AdaptiveAnswerIn(BaseModel):
    item_id: str
    answer: str = ""
    option_id: str | None = None
    confidence: int | None = None
    dont_know: bool = False
    duration_ms: int = 30_000
    edits: int = 0
    focus_switches: int = 0
    pause_ms: int = 0


@router.post("/subjects/{subject_id}/diagnostic/answer")
def answer_adaptive(subject_id: str, body: AdaptiveAnswerIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.submit_diagnostic_answer(
        db, user.id, subject_id, item_id=body.item_id, answer=body.answer, option_id=body.option_id,
        confidence=body.confidence, dont_know=body.dont_know, duration_ms=body.duration_ms,
        edits=body.edits, focus_switches=body.focus_switches, pause_ms=body.pause_ms,
    )


@router.post("/subjects/{subject_id}/diagnostic/stop")
def stop_adaptive(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.stop_diagnostic(db, user.id, subject_id)


class CheckIn(BaseModel):
    item_id: str
    answer: str


@router.post("/subjects/{subject_id}/diagnostic/check")
def check(subject_id: str, body: CheckIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return service.check_baseline(db, user.id, subject_id, body.item_id, body.answer)


@router.post("/subjects/{subject_id}/diagnostic/skip")
def skip(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """C03/UC07: skipping records insufficient evidence — never zero ability, never locks concepts."""
    workspaces.get_subject(db, user.id, subject_id)
    return {"evidence": service.skip_baseline(db, user.id, subject_id)}
