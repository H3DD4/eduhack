"""student_profile service. Reacts to assessment/exposure/deletion events; idempotent per event key.

Label rules (override §3.1/§3.2, blueprint evidence contract):
- reading/recall/learn => Introduced (exposure only, never performance);
- practice (guided session) => Practised with support, regardless of help amount;
- explanation/follow-up => Explained back (separate stage, not application);
- transfer: Applied independently (no in-app help) ONLY when mode was independent-transfer at commit
  and correctness, coverage and application were all demonstrated with sufficient evidence;
  converted/guided transfer => Practised with support; uncertain => unscored, never a success.
- revealed solutions never count as independent success.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.deps import get_owned
from thinkfirst.core.errors import ValidationFailed
from thinkfirst.data.student_profile.models import (
    LABELS,
    EvidenceRecord,
    InitialProfileRow,
    ReviewSchedule,
    SkillMasteryRow,
)

EXPOSURE_RECORDED = events.EXPOSURE_RECORDED
DEFAULT_REVIEW_DAYS = 3
STAGE_ORDER = ["introduced", "practised_with_support", "explained", "applied_independently", "recalled_later"]


def label_for(stage: str, mode: str | None, outcome: str, criteria: list[dict], assistance: dict) -> str:
    if stage in ("recall", "learn"):
        return "introduced"
    if outcome == "unscored":
        return "insufficient_evidence"  # uncertain grading is null, never a success and never zero
    if stage in ("explanation", "followup"):
        return "explained"
    if stage == "transfer":
        required = {"correctness", "essential_coverage", "example_application"}
        relevant = [c for c in criteria if c["criterion"] in required and c["status"] != "na"]
        ok = bool(relevant) and all(c["status"] == "demonstrated" for c in relevant)
        if (mode == "independent-transfer" and outcome == "demonstrated" and ok
                and not assistance.get("revealed") and not assistance.get("conversion")):
            return "applied_independently"
        return "practised_with_support"
    if stage == "diagnostic":
        return "introduced"
    return "practised_with_support"


def record(db: Session, *, owner_id: str, idempotency_key: str, **fields) -> EvidenceRecord:
    existing = db.scalar(select(EvidenceRecord).where(EvidenceRecord.idempotency_key == idempotency_key))
    if existing:
        return existing
    ev = EvidenceRecord(owner_id=owner_id, idempotency_key=idempotency_key, **fields)
    db.add(ev)
    db.flush()
    return ev


@events.subscribe(events.ASSESSMENT_ACCEPTED)
def _on_assessment(db: Session, e: events.Event) -> None:
    p = e.payload
    label = label_for(p["stage"], p.get("mode"), p["outcome"], p.get("criteria", []), p.get("assistance", {}))
    record(db, owner_id=e.owner_id, idempotency_key=f"evidence:assessment:{p['assessment_id']}",
           subject_id=p["subject_id"], concept_id=p.get("concept_id"), concept_key=p.get("concept_key"),
           session_id=p.get("session_id"), task_id=p.get("task_id"), attempt_id=p.get("attempt_id"),
           assessment_id=p["assessment_id"], stage=p["stage"], label=label, outcome=p["outcome"], mode=p.get("mode"),
           origin=p.get("origin"), method_label=p.get("method_label"), assistance=p.get("assistance", {}),
           summary=p.get("summary", ""))


@events.subscribe(EXPOSURE_RECORDED)
def _on_exposure(db: Session, e: events.Event) -> None:
    p = e.payload
    record(db, owner_id=e.owner_id, idempotency_key=f"evidence:exposure:{p['session_id']}:{p['stage']}",
           subject_id=p["subject_id"], concept_id=p.get("concept_id"), concept_key=p.get("concept_key"),
           session_id=p["session_id"], stage=p["stage"], label="introduced", outcome="exposure",
           summary=p.get("summary", "Read the cited course section."), assistance={})


@events.subscribe(events.ATTEMPT_DELETED)
def _on_attempt_deleted(db: Session, e: events.Event) -> None:
    for ev in db.scalars(select(EvidenceRecord).where(EvidenceRecord.owner_id == e.owner_id,
                                                      EvidenceRecord.task_id == e.payload["task_id"])).all():
        ev.status, ev.deleted_at, ev.summary, ev.assistance = "deleted", utcnow(), "", {}


def evidence_public(ev: EvidenceRecord) -> dict:
    return {"id": ev.id, "subject_id": ev.subject_id, "concept_id": ev.concept_id, "concept_key": ev.concept_key,
            "session_id": ev.session_id, "task_id": ev.task_id, "attempt_id": ev.attempt_id,
            "assessment_id": ev.assessment_id, "stage": ev.stage, "label": ev.label,
            "label_text": LABELS.get(ev.label, ev.label), "outcome": ev.outcome, "status": ev.status, "mode": ev.mode,
            "origin": ev.origin, "method_label": ev.method_label, "assistance": ev.assistance, "summary": ev.summary,
            "created_at": ev.created_at.isoformat(), "deleted_at": ev.deleted_at.isoformat() if ev.deleted_at else None}


def evidence_for_session(db: Session, owner_id: str, session_id: str) -> list[EvidenceRecord]:
    return list(db.scalars(select(EvidenceRecord).where(EvidenceRecord.owner_id == owner_id,
                                                        EvidenceRecord.session_id == session_id)
                           .order_by(EvidenceRecord.created_at)).all())


def evidence_for_subject(db: Session, owner_id: str, subject_id: str) -> list[EvidenceRecord]:
    return list(db.scalars(select(EvidenceRecord).where(EvidenceRecord.owner_id == owner_id,
                                                        EvidenceRecord.subject_id == subject_id)
                           .order_by(EvidenceRecord.created_at.desc())).all())


def get_evidence(db: Session, owner_id: str, evidence_id: str) -> EvidenceRecord:
    return get_owned(db, EvidenceRecord, evidence_id, owner_id)


def concept_summaries(db: Session, owner_id: str, subject_id: str) -> dict[str, dict]:
    """Per concept: reached evidence states (never a percentage), 'based on N attempts', due review."""
    out: dict[str, dict] = {}
    for ev in evidence_for_subject(db, owner_id, subject_id):
        if ev.status == "deleted" or not ev.concept_id:
            continue
        s = out.setdefault(ev.concept_id, {"states": set(), "attempts": 0, "unscored": 0, "mixed": False,
                                           "last_at": None, "receipts": []})
        if ev.outcome != "exposure":
            s["attempts"] += 1
        if ev.outcome == "unscored":
            s["unscored"] += 1
        if ev.outcome in ("demonstrated", "exposure"):
            s["states"].add(ev.label)
        if ev.outcome in ("not_demonstrated",) and ev.label in s["states"]:
            s["mixed"] = True
        s["last_at"] = s["last_at"] or ev.created_at.isoformat()
        s["receipts"].append(ev.id)
    for rv in db.scalars(select(ReviewSchedule).where(ReviewSchedule.owner_id == owner_id,
                                                      ReviewSchedule.subject_id == subject_id,
                                                      ReviewSchedule.status == "scheduled")).all():
        s = out.setdefault(rv.concept_id, {"states": set(), "attempts": 0, "unscored": 0, "mixed": False,
                                           "last_at": None, "receipts": []})
        s["review_due_on"] = rv.due_on.isoformat()
        s["review_due"] = rv.due_on <= date.today()
    for s in out.values():
        states = [st for st in STAGE_ORDER if st in s["states"]]
        s["states"] = states
        s["highest"] = states[-1] if states else None
        s["highest_text"] = LABELS.get(states[-1]) if states else "Not checked yet"
        s["insufficient"] = s["attempts"] == 0 or (s["attempts"] == s["unscored"])
    return out


# ---- review dates (persisted; full planner is M4) ----

def default_review_date(today: date | None = None) -> date:
    return (today or date.today()) + timedelta(days=DEFAULT_REVIEW_DAYS)


def book_review(db: Session, owner_id: str, *, subject_id: str, concept_id: str, session_id: str, due_on: date) -> ReviewSchedule:
    if due_on < date.today():
        raise ValidationFailed("Choose today or a later date.", field="due_on")
    if due_on > date.today() + timedelta(days=365):
        raise ValidationFailed("Choose a date within a year.", field="due_on")
    key = f"review:{session_id}"
    existing = db.scalar(select(ReviewSchedule).where(ReviewSchedule.idempotency_key == key))
    if existing:
        if existing.due_on != due_on:
            existing.due_on = due_on  # rescheduling the same booking, never a duplicate
        return existing
    rv = ReviewSchedule(owner_id=owner_id, subject_id=subject_id, concept_id=concept_id, session_id=session_id,
                        due_on=due_on, idempotency_key=key)
    db.add(rv)
    db.flush()
    events.publish(db, events.Event(events.REVIEW_BOOKED, owner_id, {"review_id": rv.id}))
    return rv


def review_for_session(db: Session, owner_id: str, session_id: str) -> ReviewSchedule | None:
    return db.scalar(select(ReviewSchedule).where(ReviewSchedule.owner_id == owner_id,
                                                  ReviewSchedule.session_id == session_id))


def reviews(db: Session, owner_id: str) -> list[ReviewSchedule]:
    return list(db.scalars(select(ReviewSchedule).where(ReviewSchedule.owner_id == owner_id,
                                                        ReviewSchedule.status == "scheduled")
                           .order_by(ReviewSchedule.due_on)).all())


def review_public(rv: ReviewSchedule | None) -> dict | None:
    if rv is None:
        return None
    return {"id": rv.id, "subject_id": rv.subject_id, "concept_id": rv.concept_id, "session_id": rv.session_id,
            "due_on": rv.due_on.isoformat(), "status": rv.status, "basis": rv.basis}


# ---- Evidence Brain: Initial Profile & BKT/Elo Skill Mastery persistence ----

@events.subscribe(events.DIAGNOSTIC_COMPLETED)
def _on_diagnostic_completed(db: Session, e: events.Event) -> None:
    p = e.payload
    subject_id = p["subject_id"]
    diag_id = p["diagnostic_session_id"]
    prof = p.get("profile") or {}
    theta = float(prof.get("theta") or 1000.0)
    expertise = prof.get("expertise") or {}
    default_stage = next(iter(expertise.values()), "novice")

    from thinkfirst.modules.rag.ingestion import service as ingestion

    concepts_by_key = {c.key: c for c in ingestion.active_concepts(db, e.owner_id, subject_id)}
    mastery_map = prof.get("mastery") or {}
    for sk_key, m in mastery_map.items():
        concept = concepts_by_key.get(sk_key)
        chapter = (concept.unit_title or f"Unit {concept.unit_no}") if concept else "all"
        stage = expertise.get(chapter, default_stage)
        row = db.scalar(select(SkillMasteryRow).where(
            SkillMasteryRow.owner_id == e.owner_id,
            SkillMasteryRow.subject_id == subject_id,
            SkillMasteryRow.skill_key == sk_key,
        ))
        if row is None:
            row = SkillMasteryRow(
                owner_id=e.owner_id, subject_id=subject_id,
                concept_id=concept.id if concept else None, skill_key=sk_key,
            )
            db.add(row)
        row.p_l = float(m.get("p_l", 0.3))
        row.evidence_count = int(m.get("n", 0))
        row.inferred = bool(m.get("inferred", False))
        row.status = str(m.get("status", "uncertain"))
        row.theta = theta
        row.expertise_stage = stage
        row.updated_at = utcnow()
        if row.evidence_count > 0 and row.status == "mastered":
            record(
                db, owner_id=e.owner_id, idempotency_key=f"evidence:diag:{diag_id}:{sk_key}",
                subject_id=subject_id, concept_id=concept.id if concept else None, concept_key=sk_key,
                stage="diagnostic", label="introduced", outcome="demonstrated",
                summary=f"Adaptive diagnostic starting estimate (based on {row.evidence_count} direct check(s)).",
                assistance={},
            )

    init_row = db.scalar(select(InitialProfileRow).where(InitialProfileRow.diagnostic_session_id == diag_id))
    if init_row is None:
        init_row = InitialProfileRow(owner_id=e.owner_id, subject_id=subject_id, diagnostic_session_id=diag_id)
        db.add(init_row)
    init_row.theta = theta
    init_row.frontier = list(prof.get("frontier") or [])
    init_row.expertise = dict(expertise)
    init_row.misconceptions = list(prof.get("misconceptions") or [])
    init_row.calibration_gap = prof.get("calibration_gap")
    init_row.behavior_priors = dict(prof.get("behavior_priors") or {})
    init_row.data_quality = dict(prof.get("data_quality") or {})
    init_row.student_view = dict(prof.get("student_view") or {})
    init_row.stop_reason = str(prof.get("stop_reason") or "all_classified")
    init_row.n_items = int(prof.get("n_items") or 0)
    init_row.low_confidence = bool(prof.get("low_confidence", False))
    init_row.needs_retest = bool(prof.get("needs_retest", False))
    db.flush()

    events.publish(db, events.Event(events.MASTERY_UPDATED, e.owner_id, {
        "subject_id": subject_id, "theta": theta, "skills": list(mastery_map.keys()),
    }))
    events.publish(db, events.Event(events.PROFILE_READY, e.owner_id, {
        "subject_id": subject_id, "profile_id": init_row.id,
        "diagnostic_session_id": diag_id, "frontier": init_row.frontier,
        "misconceptions": init_row.misconceptions, "theta": theta,
        "low_confidence": init_row.low_confidence,
    }))


def skill_mastery_for_subject(db: Session, owner_id: str, subject_id: str) -> list[dict]:
    rows = db.scalars(select(SkillMasteryRow).where(
        SkillMasteryRow.owner_id == owner_id,
        SkillMasteryRow.subject_id == subject_id,
    ).order_by(SkillMasteryRow.skill_key)).all()
    return [
        {
            "skill_key": r.skill_key, "concept_id": r.concept_id, "p_l": r.p_l,
            "evidence_count": r.evidence_count, "inferred": r.inferred, "status": r.status,
            "theta": r.theta, "expertise_stage": r.expertise_stage,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


def initial_profile_for_subject(db: Session, owner_id: str, subject_id: str) -> dict | None:
    row = db.scalar(select(InitialProfileRow).where(
        InitialProfileRow.owner_id == owner_id,
        InitialProfileRow.subject_id == subject_id,
    ).order_by(InitialProfileRow.created_at.desc()))
    if row is None:
        return None
    return {
        "id": row.id, "subject_id": row.subject_id, "diagnostic_session_id": row.diagnostic_session_id,
        "theta": row.theta, "frontier": row.frontier, "expertise": row.expertise,
        "misconceptions": row.misconceptions, "calibration_gap": row.calibration_gap,
        "behavior_priors": row.behavior_priors, "data_quality": row.data_quality,
        "student_view": row.student_view, "first_plan": row.first_plan,
        "stop_reason": row.stop_reason, "n_items": row.n_items,
        "low_confidence": row.low_confidence, "needs_retest": row.needs_retest,
        "created_at": row.created_at.isoformat(),
    }
