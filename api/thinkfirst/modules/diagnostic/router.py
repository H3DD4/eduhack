from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.diagnostic import service
from thinkfirst.modules.identity.models import User
from thinkfirst.modules.workspaces import service as workspaces

router = APIRouter(tags=["diagnostic"])


@router.get("/subjects/{subject_id}/diagnostic")
def items(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return {"items": service.baseline_items(db, user.id, subject_id)}


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
