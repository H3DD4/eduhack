"""memory service: records learning events from domain events (idempotent) and answers history queries.

Never stores audio; stores the confirmed answer text only for answers/errors (same privacy class as attempts) and
is wiped with "Delete attempt" for that task.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.data.memory.models import LearningEvent


def _add(db: Session, owner_id: str, key: str, **fields) -> None:
    if db.scalar(select(LearningEvent.id).where(LearningEvent.idempotency_key == key)):
        return
    db.add(LearningEvent(owner_id=owner_id, idempotency_key=key, **fields))
    db.flush()


@events.subscribe(events.ASSESSMENT_ACCEPTED)
def _on_assessment(db: Session, e: events.Event) -> None:
    p = e.payload
    base = {"subject_id": p["subject_id"], "concept_id": p.get("concept_id"), "task_id": p.get("task_id"), "stage": p["stage"]}
    outcome = p["outcome"]
    kind = {"demonstrated": "answer", "partial": "error", "not_demonstrated": "error", "unscored": "unscored"}.get(outcome, "answer")
    _add(db, e.owner_id, f"mem:assess:{p['assessment_id']}", kind=kind, summary=p.get("summary", "")[:500],
         detail={"outcome": outcome, "mode": p.get("mode"), "help": p.get("assistance", {}).get("help_steps", []),
                 "criteria": {c["criterion"]: c["status"] for c in p.get("criteria", []) if c["status"] != "na"}},
         outcome=ENGINE_OUTCOME.get(outcome, "unscored"), assistance=p.get("assistance_level", "none"),
         evidence=p.get("evidence", "sufficient"), is_fresh=bool(p.get("is_fresh", True)),
         misconception_id=p.get("misconception_id"), misconception_conf=0.9 if p.get("misconception_id") else None,
         **base)
    assist = p.get("assistance", {})
    if assist.get("revealed"):
        _add(db, e.owner_id, f"mem:reveal:{p['task_id']}", kind="reveal", summary="Viewed the worked solution", detail={}, **base)
    if assist.get("conversion"):
        _add(db, e.owner_id, f"mem:conv:{p['task_id']}", kind="conversion", summary="Switched to guided practice", detail={}, **base)


@events.subscribe("help.given")
def _on_help(db: Session, e: events.Event) -> None:
    p = e.payload
    remediation = p["step"] in ("worked_example", "reveal")
    _add(db, e.owner_id, f"mem:help:{p['task_id']}:{p['level']}", kind="worked_example" if remediation else "hint",
         subject_id=p["subject_id"], concept_id=p.get("concept_id"), task_id=p["task_id"], stage=p.get("stage"),
         summary=f"Help step {p['level']}: {p['step']}", detail={"step": p["step"], "level": p["level"]})


def log_recommendation(db: Session, owner_id: str, *, subject_id: str, concept_id: str, task_id: str | None,
                       action: str, context_key: str, propensity: float, key: str) -> None:
    _add(db, owner_id, f"mem:rec:{key}", kind="recommendation", subject_id=subject_id, concept_id=concept_id,
         task_id=task_id, stage="practice", summary=f"Suggested help: {action}", detail={},
         recommended_action=action, context_key=context_key, propensity=propensity)


STAGE_KIND = {"review": "review_check", "explanation": "explanation", "followup": "explanation"}
MEMORY_KIND = {"answer": None, "error": None, "unscored": None, "worked_example": "worked_example", "hint": "hint",
               "recommendation": "recommendation"}


def engine_events(db: Session, owner_id: str, subject_id: str) -> list[dict]:
    """This student's memory rows for a subject, as learner-engine LearningEvent JSON."""
    out = []
    for r in sorted(history(db, owner_id, subject_id, limit=5000), key=lambda r: r.created_at):
        if r.kind not in MEMORY_KIND or not r.concept_id:
            continue
        kind = MEMORY_KIND[r.kind] or STAGE_KIND.get(r.stage or "", "attempt")
        ev = {"event_id": r.id, "student_id": owner_id, "concept_id": r.concept_id, "ts": r.created_at.isoformat(),
              "kind": kind, "item_id": r.task_id, "is_fresh": bool(r.is_fresh) if r.is_fresh is not None else True,
              "assistance": r.assistance or "none", "evidence": r.evidence or "sufficient"}
        if kind in ("attempt", "review_check", "explanation"):
            ev.update(outcome=r.outcome or "unscored", misconception_id=r.misconception_id,
                      misconception_conf=r.misconception_conf)
        if kind == "recommendation":
            ev.update(recommended_action=r.recommended_action, context_key=r.context_key, propensity=r.propensity)
        out.append(ev)
    return out


ENGINE_OUTCOME = {"demonstrated": "correct", "partial": "partial", "not_demonstrated": "incorrect", "unscored": "unscored"}


@events.subscribe("misconception.detected")
def _on_misconception(db: Session, e: events.Event) -> None:
    p = e.payload
    _add(db, e.owner_id, f"mem:misc:{p['attempt_id']}", kind="misconception", subject_id=p["subject_id"],
         concept_id=p.get("concept_id"), task_id=p.get("task_id"), stage=p.get("stage"),
         summary=str(p.get("message", ""))[:500], detail={"code": p.get("code")})


@events.subscribe(events.ATTEMPT_DELETED)
def _on_deleted(db: Session, e: events.Event) -> None:
    for ev in db.scalars(select(LearningEvent).where(LearningEvent.owner_id == e.owner_id,
                                                     LearningEvent.task_id == e.payload["task_id"])).all():
        db.delete(ev)


def history(db: Session, owner_id: str, subject_id: str | None = None, concept_id: str | None = None,
            limit: int = 100) -> list[LearningEvent]:
    q = select(LearningEvent).where(LearningEvent.owner_id == owner_id)
    if subject_id:
        q = q.where(LearningEvent.subject_id == subject_id)
    if concept_id:
        q = q.where(LearningEvent.concept_id == concept_id)
    return list(db.scalars(q.order_by(LearningEvent.created_at.desc()).limit(limit)).all())


def recurring_misconceptions(db: Session, owner_id: str, subject_id: str) -> list[dict]:
    """Misconceptions seen more than once in this subject (observations, not traits)."""
    evs = [e for e in history(db, owner_id, subject_id, limit=500) if e.kind == "misconception"]
    counts = Counter((e.detail.get("code"), e.concept_id) for e in evs)
    return [{"code": code, "concept_id": cid, "count": n} for (code, cid), n in counts.items() if n >= 2]


def event_public(e: LearningEvent) -> dict:
    return {"id": e.id, "kind": e.kind, "stage": e.stage, "summary": e.summary, "detail": e.detail,
            "subject_id": e.subject_id, "concept_id": e.concept_id, "task_id": e.task_id, "created_at": e.created_at.isoformat()}
