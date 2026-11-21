"""Module DIAGNOSTIC — finds where understanding breaks down.

- Answer diagnosis: after each graded practice/transfer answer, publish `misconception.detected` when the grader
  identified one (SymPy patterns for algebra, LLM for free text). Memory and adaptation react to it.
- Optional baseline (C03/UC07): a few extracted exercises checked symbolically; skipping records *insufficient
  evidence* — never zero ability, never locks concepts.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.errors import NotFound
from thinkfirst.data.student_profile import service as profile
from thinkfirst.modules.diagnostic.grading import mathcheck
from thinkfirst.modules.rag.ingestion import service as ingestion

MISCONCEPTION_DETECTED = "misconception.detected"


def diagnose_answer(db: Session, owner_id: str, *, subject_id: str, concept_id: str | None, task_id: str,
                    attempt_id: str, stage: str, assessment: dict) -> dict | None:
    m = assessment.get("misconception")
    if not m:
        return None
    events.publish(db, events.Event(MISCONCEPTION_DETECTED, owner_id, {
        "subject_id": subject_id, "concept_id": concept_id, "task_id": task_id, "attempt_id": attempt_id, "stage": stage,
        "code": m.get("code"), "message": m.get("message")}))
    return m


def baseline_items(db: Session, owner_id: str, subject_id: str, limit: int = 3) -> list[dict]:
    items = [i for i in ingestion.all_items(db, owner_id, subject_id) if i.kind == "expand" and i.expression]
    return [{"id": i.id, "prompt": i.prompt, "origin": i.origin, "page": i.page_no, "concept_key": i.concept_key}
            for i in items[:limit]]


def check_baseline(db: Session, owner_id: str, subject_id: str, item_id: str, answer: str) -> dict:
    item = next((i for i in ingestion.all_items(db, owner_id, subject_id) if i.id == item_id), None)
    if item is None or not item.expression:
        raise NotFound()
    res = mathcheck.grade_expand(answer, item.expression)
    concept = next((c for c in ingestion.active_concepts(db, owner_id, subject_id) if c.key == item.concept_key), None)
    ev = profile.record(db, owner_id=owner_id, idempotency_key=f"baseline:{item.id}", subject_id=subject_id,
                        concept_id=concept.id if concept else None, concept_key=item.concept_key, stage="diagnostic",
                        label="introduced" if res.outcome != "unscored" else "insufficient_evidence", outcome=res.outcome,
                        summary=f"Baseline check: {res.feedback}", assistance={}, origin=item.origin)
    return {"outcome": res.outcome, "feedback": res.feedback, "misconception": res.misconception, "evidence_id": ev.id}


def skip_baseline(db: Session, owner_id: str, subject_id: str) -> dict:
    ev = profile.record(db, owner_id=owner_id, idempotency_key=f"diagnostic-skip:{subject_id}", subject_id=subject_id,
                        stage="diagnostic", label="insufficient_evidence", outcome="unscored",
                        summary="Baseline skipped: insufficient evidence (not a low score).", assistance={})
    return profile.evidence_public(ev)
