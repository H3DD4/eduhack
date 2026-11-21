"""W05/W08/G04 (basic) evidence reads, review list (G03 basic), and UC37 delete-attempt."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.data.student_profile import service as learner
from thinkfirst.modules.diagnostic.grading import service as assessment
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.identity.models import User
from thinkfirst.platform.workspaces import service as workspaces

router = APIRouter(tags=["learner_model"])


@router.get("/subjects/{subject_id}/evidence")
def subject_evidence(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    concepts = {c.id: c.title for c in ingestion.active_concepts(db, user.id, subject_id)}
    rows = [learner.evidence_public(e) | {"concept_title": concepts.get(e.concept_id or "", "")}
            for e in learner.evidence_for_subject(db, user.id, subject_id) if e.status != "deleted"]
    return {"evidence": rows, "summaries": {k: {**v} for k, v in learner.concept_summaries(db, user.id, subject_id).items()}}


@router.get("/evidence/{evidence_id}")
def receipt(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """W08 minimal receipt: task, date, origin, mode, answer, help, criteria with quotes, source, method label."""
    from thinkfirst.modules.tutor import service as tutor

    ev = learner.get_evidence(db, user.id, evidence_id)
    out = {"evidence": learner.evidence_public(ev), "task": None, "attempt": None, "assessment": None, "concept": None}
    if ev.status == "deleted":
        return out | {"deleted": True}
    if ev.task_id:
        t = tutor.get_task(db, user.id, ev.task_id)
        out["task"] = {"id": t.id, "prompt": t.prompt if t.mode != "pending-commit" else None, "stage": t.stage,
                       "origin": t.origin, "origin_detail": t.origin_detail, "mode": t.mode, "novelty": t.novelty}
    if ev.attempt_id:
        at = assessment.get_attempt(db, user.id, ev.attempt_id)
        out["attempt"] = {"id": at.id, "response_kind": at.response_kind, "response_text": at.response_text,
                          "supplement_text": at.supplement_text, "created_at": at.created_at.isoformat()}
        out["assessment"] = assessment.assessment_public(assessment.assessment_for_attempt(db, at.id))
    if ev.concept_id:
        out["concept"] = ingestion.concept_public(ingestion.get_concept(db, user.id, ev.concept_id))
    return out


@router.delete("/evidence/{evidence_id}/attempt")
def delete_attempt(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """UC37: removes response content + derived evidence for this task; audio-only deletion lives in explain_back."""
    from thinkfirst.modules.tutor.explain_back import service as explain_back

    ev = learner.get_evidence(db, user.id, evidence_id)
    if not ev.task_id:
        return {"status": "nothing_to_delete"}
    explain_back.delete_for_task(db, user.id, ev.task_id)
    n = assessment.delete_task_attempts(db, user.id, ev.task_id)
    return {"status": "completed", "attempts_deleted": n,
            "note": "Response content and derived evidence were removed; content-free deletion metadata is kept. "
                    "Backups are not covered in this build (see OPEN_QUESTIONS)."}


@router.get("/reviews")
def reviews(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"reviews": [learner.review_public(r) for r in learner.reviews(db, user.id)]}


@router.get("/progress")
def overall(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """G04 basic: per-subject counts by state. No percentages, no traits."""
    out = []
    for s in workspaces.list_subjects(db, user.id):
        sums = learner.concept_summaries(db, user.id, s.id)
        counts: dict[str, int] = {}
        for v in sums.values():
            for st in v["states"]:
                counts[st] = counts.get(st, 0) + 1
        out.append({"subject": workspaces.subject_public(s), "concepts_with_evidence": len(sums), "state_counts": counts})
    return {"subjects": out, "profile_note": "Learning-profile observations arrive in M3."}


@router.get("/me/memory")
def my_memory(subject_id: str | None = None, concept_id: str | None = None, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    """Historique & mémoire: the student's own learning timeline (answers, errors, misconceptions, help)."""
    from thinkfirst.data.memory import service as memory

    return {"events": [memory.event_public(e) for e in memory.history(db, user.id, subject_id, concept_id)],
            "recurring": memory.recurring_misconceptions(db, user.id, subject_id) if subject_id else []}


class TrackingEventIn(BaseModel):
    verb: str
    object: dict
    result: dict = {}
    context: dict = {}
    event_id: str | None = None
    timestamp: str | None = None
    subject_id: str | None = None


@router.post("/tracking/events")
def post_tracking_event(body: TrackingEventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Layer 1 -> Layer 2 -> Layer 3 behavioral tracking ingestion (xAPI schema, consent-redacted)."""
    from thinkfirst.data.memory import service as memory

    raw = {"verb": body.verb, "object": body.object, "result": body.result, "context": body.context}
    if body.event_id:
        raw["event_id"] = body.event_id
    if body.timestamp:
        raw["timestamp"] = body.timestamp
    return memory.ingest_tracking_event(db, user.id, raw, subject_id=body.subject_id)


@router.get("/me/tracking/indicators")
def get_tracking_indicators(subject_id: str | None = None, user: User = Depends(current_user),
                            db: Session = Depends(get_db)):
    from thinkfirst.data.memory import service as memory

    return memory.get_indicators(db, user.id, subject_id)


@router.get("/subjects/{subject_id}/mastery")
def subject_mastery(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    return {
        "mastery": learner.skill_mastery_for_subject(db, user.id, subject_id),
        "initial_profile": learner.initial_profile_for_subject(db, user.id, subject_id),
    }
