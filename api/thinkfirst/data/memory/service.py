"""memory service: records learning events from domain events (idempotent) and answers history queries.

Never stores audio; stores the confirmed answer text only for answers/errors (same privacy class as attempts) and
is wiped with "Delete attempt" for that task.
"""

from __future__ import annotations

import hashlib
from collections import Counter

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import ValidationFailed
from thinkfirst.data.memory.models import BehavioralEvent, BehaviorIndicator, LearningEvent
from thinkfirst.domain.tracking import indicators as ind
from thinkfirst.domain.tracking.events import EventError, TrackingEvent
from thinkfirst.domain.tracking.signals import SIGNAL_CATALOG, redact
from thinkfirst.platform.identity import service as identity


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
                 "criteria": {c["criterion"]: c["status"] for c in p.get("criteria", []) if c["status"] != "na"},
                 "item_key": p.get("item_key")},
         outcome=ENGINE_OUTCOME.get(outcome, "unscored"), assistance=p.get("assistance_level", "none"),
         evidence=p.get("evidence", "sufficient"), is_fresh=bool(p.get("is_fresh", True)),
         misconception_id=p.get("misconception_id"), misconception_conf=0.9 if p.get("misconception_id") else None,
         **base)
    assist = p.get("assistance", {})
    if assist.get("revealed"):
        _add(db, e.owner_id, f"mem:reveal:{p['task_id']}", kind="reveal", summary="Viewed the worked solution", detail={}, **base)
    if assist.get("conversion"):
        _add(db, e.owner_id, f"mem:conv:{p['task_id']}", kind="conversion", summary="Switched to guided practice", detail={}, **base)


@events.subscribe(events.HELP_GIVEN)
def _on_help(db: Session, e: events.Event) -> None:
    p = e.payload
    remediation = p["step"] in ("worked_example", "reveal")
    _add(db, e.owner_id, f"mem:help:{p['task_id']}:{p['level']}", kind="worked_example" if remediation else "hint",
         subject_id=p["subject_id"], concept_id=p.get("concept_id"), task_id=p["task_id"], stage=p.get("stage"),
         summary=f"Help step {p['level']}: {p['step']}",
         detail={"step": p["step"], "level": p["level"], "item_key": p.get("item_key"), "hint_key": p.get("hint_key"),
                 "counted": False})


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
              "kind": kind, "item_id": (r.detail or {}).get("item_key") or r.task_id, "is_fresh": bool(r.is_fresh) if r.is_fresh is not None else True,
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


# ---- Behavioral tracking layer (Layer 1 xAPI events -> Layer 2 signal redaction -> Layer 3 derived indicators) ----

NEGATIVE_MARKERS = ("stupid", "give up", "can't do this", "hate this", "useless", "lost", "impossible")


def pseudonymous_actor(owner_id: str) -> str:
    """Pseudonymous ID in all learning events; real identity is kept only in the Identity service."""
    digest = hashlib.sha256(f"thinkfirst-actor:{owner_id}".encode()).hexdigest()[:10]
    return f"stu_{digest}"


def count_negative_words(text: str | None) -> int:
    if not text:
        return 0
    low = text.lower()
    return sum(1 for marker in NEGATIVE_MARKERS if marker in low)


def ingest_tracking_event(db: Session, owner_id: str, raw: dict, *, subject_id: str | None = None) -> dict:
    """Validate an xAPI event, enforce NEVER_TRACKED, redact by the student's consent tiers, and update indicators."""
    payload = dict(raw)
    payload["actor"] = pseudonymous_actor(owner_id)
    try:
        ev = TrackingEvent.from_dict(payload)
    except EventError as exc:
        raise ValidationFailed(str(exc), field="event") from exc

    consent = identity.consent_state(db, owner_id)
    redacted = redact(ev, consent)
    if redacted is None:
        return {"stored": False, "reason": "consent_tier_off", "event_id": ev.event_id}

    existing = db.scalar(select(BehavioralEvent).where(
        BehavioralEvent.owner_id == owner_id, BehavioralEvent.event_id == redacted.event_id
    ))
    sid = subject_id or redacted.context.get("subject_id") or redacted.object.get("subject_id")
    if existing is None:
        row = BehavioralEvent(
            owner_id=owner_id,
            event_id=redacted.event_id,
            actor=redacted.actor,
            verb=redacted.verb.value,
            object_type=str(redacted.object.get("type", "item"))[:32],
            object_id=str(redacted.object.get("id", ""))[:120],
            subject_id=str(sid)[:36] if sid else None,
            session_id=str(redacted.context.get("session"))[:36] if redacted.context.get("session") else None,
            skills=list(redacted.object.get("skills") or []),
            result=dict(redacted.result),
            context=dict(redacted.context),
            event_ts=redacted.timestamp,
        )
        db.add(row)
        db.flush()

    summary = refresh_indicators(db, owner_id, str(sid) if sid else None)
    return {"stored": True, "event": redacted.to_dict(), "indicators": summary["indicators"]}


def _observations_from_events(rows: list[BehavioralEvent]) -> list[ind.Observation]:
    obs: list[ind.Observation] = []
    for r in rows:
        if r.verb not in ("answered", "skipped", "abandoned"):
            continue
        res = r.result or {}
        ctx = r.context or {}
        resp_text = str(res.get("response") or "")
        obs.append(ind.Observation(
            correct=res.get("correct") if isinstance(res.get("correct"), bool) else None,
            duration_ms=int(res.get("duration_ms") or 0),
            typical_ms=int(res.get("typical_ms") or 60_000),
            help_requests=int(ctx.get("help_level") or res.get("help_requests") or 0),
            edits=int(res.get("edits") or 0),
            skipped=r.verb in ("skipped", "abandoned") or bool(res.get("skipped")),
            confidence=int(ctx["confidence"]) if ctx.get("confidence") is not None else None,
            response_len=len(resp_text) if resp_text else res.get("response_len"),
            negative_words=int(res.get("negative_words") or count_negative_words(resp_text)),
            focus_switches=int(ctx.get("focus_switches") or 0),
            pause_ms=int(ctx.get("pause_ms") or 0),
            hour=r.event_ts.hour if r.event_ts else None,
        ))
    return obs


def refresh_indicators(db: Session, owner_id: str, subject_id: str | None = None) -> dict:
    """Recompute Layer 3 derived indicators and publish `indicator.updated`."""
    q = select(BehavioralEvent).where(BehavioralEvent.owner_id == owner_id)
    if subject_id:
        q = q.where(BehavioralEvent.subject_id == subject_id)
    rows = list(db.scalars(q.order_by(BehavioralEvent.event_ts.asc()).limit(200)).all())
    obs = _observations_from_events(rows)
    last = obs[-1] if obs else ind.Observation()

    computed = [
        ind.rapid_guessing(last),
        ind.gaming_the_system(obs),
        ind.help_avoidance(obs),
        ind.productive_struggle(last),
        ind.frustration_risk(obs),
        ind.disengagement(obs),
        ind.calibration(obs),
    ]
    db.execute(delete(BehaviorIndicator).where(
        BehaviorIndicator.owner_id == owner_id,
        BehaviorIndicator.subject_id == subject_id,
    ))
    out_list = []
    for item in computed:
        db.add(BehaviorIndicator(
            owner_id=owner_id, subject_id=subject_id, name=item.name, active=item.active,
            score=round(item.score, 3), confidence=round(item.confidence, 3),
            reason=item.reason, value=round(item.value, 2) if item.value is not None else None,
            updated_at=utcnow(),
        ))
        out_list.append({
            "name": item.name, "active": item.active, "score": round(item.score, 3),
            "confidence": round(item.confidence, 3), "reason": item.reason,
            "value": round(item.value, 2) if item.value is not None else None,
        })
    best_hours = [{"hour": h, "accuracy": round(acc, 2), "samples": n} for h, acc, n in ind.best_study_hours(obs)]
    db.flush()

    # Student-facing effects (never labels like "you are frustrated")
    active_names = {i["name"] for i in out_list if i["active"]}
    effects: list[str] = []
    if "rapid_guessing" in active_names:
        effects.append("Take your time — this isn't timed for speed.")
    if "help_avoidance" in active_names:
        effects.append("Want a quick guiding question to break this step down?")
    if "frustration_risk" in active_names or "disengagement" in active_names:
        effects.append("Let's try a shorter, focused step or take a quick breather.")
    if "productive_struggle" in active_names:
        effects.append("Sticking with that step and revising paid off.")

    payload = {"subject_id": subject_id, "indicators": out_list, "best_study_hours": best_hours,
               "student_effects": effects, "event_count": len(rows)}
    events.publish(db, events.Event(events.INDICATOR_UPDATED, owner_id, payload))
    return payload


def get_indicators(db: Session, owner_id: str, subject_id: str | None = None) -> dict:
    summary = refresh_indicators(db, owner_id, subject_id)
    return summary | {
        "actor": pseudonymous_actor(owner_id),
        "signal_catalog": [{"name": s.name, "measure": s.measure, "tier": s.tier.value} for s in SIGNAL_CATALOG],
    }
