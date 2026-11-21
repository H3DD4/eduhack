from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.modules.explain_back import service
from thinkfirst.modules.identity.models import User

router = APIRouter(tags=["explain_back"])


@router.get("/tasks/{task_id}/explain")
def explain_state(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.state(db, user.id, task_id)


@router.post("/tasks/{task_id}/audio")
async def upload_audio(task_id: str, file: UploadFile = File(...), idempotency_key: str = Form(...),
                       retention: str = Form("delete_after_confirmation"), checksum: str | None = Form(None),
                       capture_ms: int | None = Form(None), user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    take, job = service.upload_audio(db, user.id, task_id, await file.read(), file.content_type or "", retention,
                                     idempotency_key, checksum, capture_ms)
    return {"take_id": take.id, "job": job, "receipt": {"checksum": take.checksum, "size_bytes": take.size_bytes}}


class TypedIn(BaseModel):
    text: str


@router.post("/tasks/{task_id}/typed")
def typed(task_id: str, body: TypedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = service.save_typed(db, user.id, task_id, body.text)
    return {"version_id": v.id}


class CorrectIn(BaseModel):
    base_version_id: str
    text: str
    resolved_span_ids: list[str] = []


@router.post("/tasks/{task_id}/corrections")
def correction(task_id: str, body: CorrectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = service.correct(db, user.id, task_id, body.base_version_id, body.text, body.resolved_span_ids)
    return {"version_id": v.id, "unresolved": service.unresolved_spans(v)}


class ConfirmIn(BaseModel):
    version_id: str
    supplement: str | None = None
    keep_unresolved: bool = False
    idempotency_key: str


@router.post("/tasks/{task_id}/confirm")
def confirm(task_id: str, body: ConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return service.confirm(db, user.id, task_id, body.version_id, body.supplement, body.keep_unresolved, body.idempotency_key)


@router.delete("/audio/{take_id}")
def delete_audio(take_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    take = service.delete_audio_now(db, user.id, take_id)
    return {"status": take.status, "message": "Audio deleted; transcript history remains."}


@router.get("/audio/{take_id}")
def play(take_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data, mime = service.playback(db, user.id, take_id)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "no-store"})
