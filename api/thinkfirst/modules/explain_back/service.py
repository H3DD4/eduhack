"""explain_back service (UC21 + parts of UC37): upload -> transcribe -> confirm/correct -> hand to tutor for grading.

Privacy defaults (override §3.3, blueprint): only the transcription processor receives audio; grading receives
confirmed text; raw audio is deleted after confirmation unless the student chose 7-day replay; deleted audio has
no playable link; "Audio deleted; transcript history remains."
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core import events, jobs
from thinkfirst.core.db import utcnow
from thinkfirst.core.deps import get_owned
from thinkfirst.core.errors import AppError, Conflict, NotFound, ValidationFailed
from thinkfirst.core.storage import get_storage, sha256
from thinkfirst.modules.explain_back import stt
from thinkfirst.modules.explain_back.models import AudioTake, TranscriptVersion
from thinkfirst.modules.tutor import service as tutor

RETENTIONS = {"delete_after_confirmation", "replay_7_days"}


def _task(db: Session, owner_id: str, task_id: str):
    t = tutor.get_task(db, owner_id, task_id)
    if t.kind != "explain":
        raise ValidationFailed("This task does not take an explanation.")
    return t


def upload_audio(db: Session, owner_id: str, task_id: str, data: bytes, mime: str, retention: str,
                 idempotency_key: str, client_checksum: str | None, capture_ms: int | None) -> tuple[AudioTake, dict]:
    t = _task(db, owner_id, task_id)
    key = f"take:{t.id}:{idempotency_key}"
    existing = db.scalar(select(AudioTake).where(AudioTake.idempotency_key == key))
    if existing:  # dropped response + retry => receipt reconciliation, not a duplicate take
        job = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"transcribe:{existing.id}"))
        return existing, jobs.job_public(job) if job else {}
    if t.status in ("committed", "abandoned"):
        raise Conflict("This explanation is already confirmed.", code="TASK_FINISHED")
    if not mime.startswith("audio/"):
        raise ValidationFailed("Unsupported recording format.", field="file")
    if not data:
        raise AppError("No playable audio was captured. Record another take or use text.", code="EMPTY_AUDIO", status=422)
    if len(data) > get_settings().max_audio_bytes:
        raise ValidationFailed("This recording is too large to upload.", field="file")
    digest = sha256(data)
    if client_checksum and client_checksum != digest:
        raise AppError("The upload was incomplete. Retry from this device.", code="CHECKSUM_MISMATCH", status=422)
    if retention not in RETENTIONS:
        retention = "delete_after_confirmation"
    n = (db.scalar(select(func.count(AudioTake.id)).where(AudioTake.task_id == t.id)) or 0) + 1
    take = AudioTake(owner_id=owner_id, task_id=t.id, take_no=n, mime=mime[:100], size_bytes=len(data), checksum=digest,
                     capture_ms=capture_ms, retention=retention, idempotency_key=key,
                     expires_at=utcnow() + timedelta(days=7))  # unconfirmed uploads share the 7-day cap
    db.add(take)
    db.flush()
    take.storage_key = f"private/{owner_id}/audio/{take.id}"
    get_storage().put(take.storage_key, data, take.mime)
    job = jobs.enqueue(db, "explain_back.transcribe", owner_id, {"take_id": take.id}, idempotency_key=f"transcribe:{take.id}")
    return take, jobs.job_public(job)


@jobs.job_handler("explain_back.transcribe")
def _transcribe_job(db: Session, job: jobs.Job) -> dict:
    take = db.get(AudioTake, job.payload["take_id"])
    if take is None or take.status == "deleted" or not take.storage_key:
        return {"stale": True}  # e.g. "Delete audio now" cancelled it
    take.status = "transcribing"
    result = stt.transcribe(get_storage().get(take.storage_key), take.mime)
    if result.error_code:
        take.status = "uploaded"
        raise jobs.JobError(result.error_code)
    if not result.text.strip():
        take.status = "uploaded"
        raise jobs.JobError("EMPTY_TRANSCRIPT")
    v = TranscriptVersion(owner_id=take.owner_id, task_id=take.task_id, take_id=take.id, kind="original_asr",
                          text=result.text, uncertain_spans=result.uncertain, source_label=result.label)
    db.add(v)
    take.status = "transcribed"
    db.flush()
    return {"transcript_version_id": v.id, "simulated": result.simulated}


def save_typed(db: Session, owner_id: str, task_id: str, text: str) -> TranscriptVersion:
    t = _task(db, owner_id, task_id)
    text = (text or "").strip()
    if not text:
        raise ValidationFailed("Add text to review it.", field="text")
    v = TranscriptVersion(owner_id=owner_id, task_id=t.id, kind="typed", text=text[:6000], source_label="Typed by you")
    db.add(v)
    db.flush()
    return v


def correct(db: Session, owner_id: str, task_id: str, base_version_id: str, text: str,
            resolved_span_ids: list[str]) -> TranscriptVersion:
    base = get_owned(db, TranscriptVersion, base_version_id, owner_id)
    if base.task_id != task_id or base.kind == "supplement":
        raise NotFound()
    if base.confirmed:
        raise Conflict("This version is confirmed. Later edits create a new version.", code="VERSION_FROZEN")
    text = (text or "").strip()
    if not text:
        raise ValidationFailed("Add text to review it.", field="text")
    remaining = [s for s in base.uncertain_spans if s["text"] in text]  # spans edited away are resolved
    v = TranscriptVersion(owner_id=owner_id, task_id=task_id, take_id=base.take_id,
                          kind="corrected" if base.kind in ("original_asr", "corrected") else "typed",
                          text=text[:6000], uncertain_spans=remaining,
                          resolved_span_ids=[s for s in resolved_span_ids if any(r["id"] == s for r in remaining)],
                          based_on_id=base.id, source_label="Corrected by you")
    db.add(v)
    db.flush()
    return v


def unresolved_spans(v: TranscriptVersion) -> list[dict]:
    return [s for s in v.uncertain_spans if s["id"] not in (v.resolved_span_ids or []) and s["text"] in v.text]


def confirm(db: Session, owner_id: str, task_id: str, version_id: str, supplement: str | None,
            keep_unresolved: bool, idempotency_key: str) -> dict:
    t = _task(db, owner_id, task_id)
    v = get_owned(db, TranscriptVersion, version_id, owner_id)
    if v.task_id != t.id or v.kind == "supplement":
        raise NotFound()
    if not v.text.strip():
        raise ValidationFailed("Add text to review it.")
    open_spans = unresolved_spans(v)
    if open_spans and not keep_unresolved:
        raise AppError("Resolve or explicitly keep the unclear words before assessment.", code="UNRESOLVED_SPANS",
                       status=409, spans=open_spans)
    if not v.confirmed:
        v.confirmed, v.confirmed_at = True, utcnow()
    supp = (supplement or "").strip()
    if supp:
        db.add(TranscriptVersion(owner_id=owner_id, task_id=t.id, kind="supplement", text=supp[:3000],
                                 based_on_id=v.id, confirmed=True, confirmed_at=utcnow(),
                                 source_label="Added reasoning (typed supplement, not part of the recording)"))
    deleted_audio = False
    if v.take_id:
        take = db.get(AudioTake, v.take_id)
        if take and take.status != "deleted":
            if take.retention == "delete_after_confirmation":
                _delete_take(db, take, "deleted_after_confirmation")
                deleted_audio = True
            else:
                take.expires_at = take.created_at + timedelta(days=7)
    events.publish(db, events.Event(events.TRANSCRIPT_CONFIRMED, owner_id, {"task_id": t.id, "version_id": v.id}))
    result = tutor.submit_confirmed_explanation(
        db, owner_id, t.id, text=v.text, supplement=supp or None, transcript_version_id=v.id,
        unresolved_spans=open_spans, response_kind="audio" if v.take_id else "text", idempotency_key=idempotency_key)
    return {**result, "audio_deleted": deleted_audio, "version_id": v.id}


def _delete_take(db: Session, take: AudioTake, reason: str) -> None:
    if take.storage_key:
        get_storage().delete(take.storage_key)
    take.storage_key, take.status, take.deleted_at, take.deletion_reason = None, "deleted", utcnow(), reason
    events.publish(db, events.Event(events.DELETION_ACKNOWLEDGED, take.owner_id, {"take_id": take.id, "reason": reason}))


def delete_audio_now(db: Session, owner_id: str, take_id: str) -> AudioTake:
    take = get_owned(db, AudioTake, take_id, owner_id)
    job = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"transcribe:{take.id}"))
    if job is not None:
        jobs.cancel(db, job)  # cancels unfinished transcription
    if take.status != "deleted":
        _delete_take(db, take, "deleted_by_student")
    return take


def playback(db: Session, owner_id: str, take_id: str) -> tuple[bytes, str]:
    take = get_owned(db, AudioTake, take_id, owner_id)
    if take.status == "deleted" or not take.storage_key:
        raise NotFound("Audio deleted; transcript history remains.")
    if take.expires_at and take.expires_at <= utcnow():
        _delete_take(db, take, "retention_expired")
        raise NotFound("Audio deleted; transcript history remains.")
    return get_storage().get(take.storage_key), take.mime


def purge_expired(db: Session) -> int:
    n = 0
    for take in db.scalars(select(AudioTake).where(AudioTake.status != "deleted", AudioTake.expires_at <= utcnow())).all():
        _delete_take(db, take, "retention_expired")
        n += 1
    return n


def delete_for_task(db: Session, owner_id: str, task_id: str) -> None:
    """Full 'Delete attempt': audio + transcript content for this task."""
    for take in db.scalars(select(AudioTake).where(AudioTake.owner_id == owner_id, AudioTake.task_id == task_id)).all():
        if take.status != "deleted":
            _delete_take(db, take, "attempt_deleted")
    for v in db.scalars(select(TranscriptVersion).where(TranscriptVersion.owner_id == owner_id,
                                                        TranscriptVersion.task_id == task_id)).all():
        v.text, v.uncertain_spans = "", []


def state(db: Session, owner_id: str, task_id: str) -> dict:
    t = _task(db, owner_id, task_id)
    takes = db.scalars(select(AudioTake).where(AudioTake.task_id == t.id).order_by(AudioTake.take_no)).all()
    versions = db.scalars(select(TranscriptVersion).where(TranscriptVersion.task_id == t.id)
                          .order_by(TranscriptVersion.created_at)).all()
    tjobs = {}
    for take in takes:
        j = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"transcribe:{take.id}"))
        if j:
            tjobs[take.id] = jobs.job_public(j)
    return {
        "task_id": t.id,
        "takes": [{"id": k.id, "take_no": k.take_no, "mime": k.mime, "size_bytes": k.size_bytes, "status": k.status,
                   "retention": k.retention, "playable": k.status != "deleted" and bool(k.storage_key),
                   "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                   "deleted_at": k.deleted_at.isoformat() if k.deleted_at else None,
                   "deletion_reason": k.deletion_reason, "job": tjobs.get(k.id)} for k in takes],
        "versions": [{"id": v.id, "kind": v.kind, "text": v.text, "take_id": v.take_id, "based_on_id": v.based_on_id,
                      "uncertain_spans": v.uncertain_spans, "unresolved": unresolved_spans(v),
                      "source_label": v.source_label, "confirmed": v.confirmed,
                      "created_at": v.created_at.isoformat()} for v in versions],
    }
