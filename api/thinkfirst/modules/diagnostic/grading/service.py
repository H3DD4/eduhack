"""assessment service: rubrics, idempotent attempts, graded assessments, deletion."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.deps import get_owned
from thinkfirst.modules.diagnostic.grading import explanation, mathcheck
from thinkfirst.modules.diagnostic.grading.models import Assessment, Attempt, Rubric
from thinkfirst.modules.diagnostic.grading.rubrics import template_for
from thinkfirst.modules.tutor.llm import service as llm

SYMBOLIC_LABEL = "Checked symbolically (SymPy)"


@events.subscribe(events.SOURCE_CONFIRMED)
def _create_rubrics(db: Session, event: events.Event) -> None:
    """React to scope confirmation: one rubric per confirmed concept (idempotent per subject+concept)."""
    from thinkfirst.modules.rag.ingestion import service as ingestion

    owner, subject_id = event.owner_id, event.payload["subject_id"]
    for c in ingestion.concepts_of(db, event.payload["graph_revision_id"]):
        if c.excluded:
            continue
        if db.scalar(select(Rubric).where(Rubric.owner_id == owner, Rubric.subject_id == subject_id,
                                          Rubric.concept_key == c.key)):
            continue
        t = template_for(c.title)
        db.add(Rubric(owner_id=owner, subject_id=subject_id, concept_key=c.key, template=t["template"],
                      explain_prompt=t["explain_prompt"], criteria=t["criteria"], followup_bank=t["followup_bank"],
                      source_citation=c.citations[0] if c.citations else None))
    db.flush()


def get_rubric(db: Session, owner_id: str, subject_id: str, concept_key: str, title: str = "") -> Rubric:
    r = db.scalar(select(Rubric).where(Rubric.owner_id == owner_id, Rubric.subject_id == subject_id,
                                       Rubric.concept_key == concept_key).order_by(Rubric.version.desc()))
    if r is None:
        t = template_for(title or concept_key)
        r = Rubric(owner_id=owner_id, subject_id=subject_id, concept_key=concept_key, template=t["template"],
                   explain_prompt=t["explain_prompt"], criteria=t["criteria"], followup_bank=t["followup_bank"])
        db.add(r)
        db.flush()
    return r


def rubric_public(r: Rubric) -> dict:
    """What the student may see before answering: criteria + essential descriptions (no patterns)."""
    return {"id": r.id, "template": r.template, "approval": r.approval,
            "approval_label": ("Demo rubric — not domain-approved" if r.approval.startswith("demo") else
                               "AI-generated rubric — not domain-approved" if r.approval.startswith("ai-generated")
                               else r.approval),
            "criteria": [{"criterion": c["criterion"], "applicable": c.get("applicable", True),
                          "essentials": [{"id": e["id"], "description": e["description"]} for e in c.get("essentials", [])]}
                         for c in r.criteria],
            "source_citation": r.source_citation}


def record_attempt(db: Session, *, owner_id: str, task_id: str, session_id: str, task_revision: int, response_kind: str,
                   response_text: str, mode: str, idempotency_key: str, supplement_text: str | None = None,
                   transcript_version_id: str | None = None) -> tuple[Attempt, bool]:
    existing = db.scalar(select(Attempt).where(Attempt.idempotency_key == idempotency_key))
    if existing:
        return existing, False
    a = Attempt(owner_id=owner_id, task_id=task_id, session_id=session_id, task_revision=task_revision,
                response_kind=response_kind, response_text=response_text, supplement_text=supplement_text,
                transcript_version_id=transcript_version_id, mode_at_submit=mode, idempotency_key=idempotency_key)
    db.add(a)
    db.flush()
    return a, True


def assessment_for_attempt(db: Session, attempt_id: str) -> Assessment | None:
    return db.scalar(select(Assessment).where(Assessment.attempt_id == attempt_id, Assessment.superseded_by_id.is_(None)))


def save_symbolic(db: Session, attempt: Attempt, result: mathcheck.GradeResult) -> Assessment:
    existing = assessment_for_attempt(db, attempt.id)
    if existing:
        return existing
    crit = [c.as_dict() for c in result.criteria]
    applicable = [c for c in crit if c["status"] != "na"]
    total = None if any(c["status"] == "unscored" for c in applicable) else sum(c["score"] for c in applicable)
    a = Assessment(owner_id=attempt.owner_id, attempt_id=attempt.id, method="symbolic", method_label=SYMBOLIC_LABEL,
                   criteria=crit, outcome=result.outcome, sufficiency=result.sufficiency, reason=result.reason,
                   feedback=result.feedback, misconception=result.misconception, total=total)
    db.add(a)
    db.flush()
    return a


def assess_explanation(db: Session, attempt: Attempt, rubric: Rubric, *, sentences: list[dict],
                       unresolved_spans: list[dict], course_excerpt: str | None, only_criteria: set[str] | None) -> Assessment:
    existing = assessment_for_attempt(db, attempt.id)
    if existing:
        return existing
    rubric_vars = {"criteria": [c for c in rubric.criteria
                                if only_criteria is None or c["criterion"] in only_criteria]}
    res = llm.run(db, "assess_explanation",
                  {"student_sentences": sentences, "rubric": rubric_vars, "course_excerpt": course_excerpt or ""},
                  owner_id=attempt.owner_id, purpose="explain_back_assessment")
    normalized = explanation.validate_explanation_output(
        res.output if res.status == "ok" else None, sentences,
        {"criteria": rubric.criteria, "source_citation": rubric.source_citation}, unresolved_spans, only_criteria)
    reason = normalized["reason"] if res.status == "ok" else f"Assessment service unavailable ({res.error_code})."
    method = "simulated" if res.simulated else "ai"
    a = Assessment(owner_id=attempt.owner_id, attempt_id=attempt.id, rubric_id=rubric.id, method=method,
                   method_label=res.label, criteria=normalized["criteria"], outcome=normalized["outcome"],
                   sufficiency=normalized["sufficiency"], reason=reason, total=normalized["total"],
                   feedback=_explanation_feedback(normalized))
    db.add(a)
    db.flush()
    return a


def _explanation_feedback(n: dict) -> str:
    shown = [c for c in n["criteria"] if c["status"] == "demonstrated"]
    missing = [c for c in n["criteria"] if c["status"] in ("absent", "partial")]
    unscored = [c for c in n["criteria"] if c["status"] == "unscored"]
    parts = []
    if shown:
        parts.append(f"{len(shown)} criteria demonstrated with quotes from your words.")
    if missing:
        parts.append(f"{len(missing)} not yet fully demonstrated — see what is missing.")
    if unscored:
        parts.append(f"{len(unscored)} unscored: not enough reliable information (this is not a mark against you).")
    return " ".join(parts) or "What this answer showed, and what remains uncertain."


def assessment_public(a: Assessment | None) -> dict | None:
    if a is None:
        return None
    return {"id": a.id, "attempt_id": a.attempt_id, "method": a.method, "method_label": a.method_label,
            "simulated": a.method == "simulated", "criteria": a.criteria, "outcome": a.outcome,
            "sufficiency": a.sufficiency, "reason": a.reason, "feedback": a.feedback, "misconception": a.misconception,
            "total": a.total, "disputed": a.disputed, "created_at": a.created_at.isoformat()}


def attempts_for_task(db: Session, owner_id: str, task_id: str) -> list[Attempt]:
    return list(db.scalars(select(Attempt).where(Attempt.owner_id == owner_id, Attempt.task_id == task_id)
                           .order_by(Attempt.created_at)).all())


def delete_task_attempts(db: Session, owner_id: str, task_id: str) -> int:
    """UC37 'Delete attempt': remove response content + derived assessment content; keep content-free metadata."""
    n = 0
    for at in attempts_for_task(db, owner_id, task_id):
        if at.status == "deleted":
            continue
        at.response_text, at.supplement_text, at.status, at.deleted_at = None, None, "deleted", utcnow()
        for a in db.scalars(select(Assessment).where(Assessment.attempt_id == at.id)).all():
            a.criteria, a.feedback, a.reason, a.misconception, a.total = [], "", "deleted", None, None
        n += 1
    events.publish(db, events.Event(events.ATTEMPT_DELETED, owner_id, {"task_id": task_id}))
    return n


def get_attempt(db: Session, owner_id: str, attempt_id: str) -> Attempt:
    return get_owned(db, Attempt, attempt_id, owner_id)


@llm.register_demo("grade_short_answer")
def _demo_short_answer(v: dict) -> dict:
    return {"verdict": "uncertain", "feedback": "No AI service is configured to check free-text answers, so this stays unscored.",
            "misconception": None, "targeted_question": None}


_VERDICT_STATUS = {"correct": "demonstrated", "partially_correct": "partial", "incorrect": "absent", "uncertain": "unscored"}
_OUTCOME = {"demonstrated": "demonstrated", "partial": "partial", "absent": "not_demonstrated", "unscored": "unscored"}


def grade_generated(db: Session, attempt: Attempt, *, question: str, expected: str, kind: str, answer: str,
                    transfer: bool) -> Assessment:
    """Generated practice/transfer items: SymPy when both sides are expressions, otherwise the LLM grader.
    Uncertain or invalid output => unscored (never zero). Feedback never reveals the reference answer."""
    existing = assessment_for_attempt(db, attempt.id)
    if existing:
        return existing
    verdict, feedback, misc, tq = None, "", None, None
    method, label = "symbolic", SYMBOLIC_LABEL
    if kind == "expression":
        e, a = mathcheck.parse(expected), mathcheck.parse(answer)
        if e is not None and a is not None:
            ok = mathcheck.equivalent(a, e)
            verdict = "correct" if ok else "incorrect"
            feedback = "Your answer is equivalent to the expected result." if ok else "Not equivalent yet — check each step."
    if verdict is None:
        res = llm.run(db, "grade_short_answer", {"question": question, "reference_answer": expected, "student_answer": answer},
                      owner_id=attempt.owner_id, purpose="short_answer_grading")
        method, label = ("simulated" if res.simulated else "ai"), res.label
        out = res.output if res.status == "ok" else None
        verdict = (out or {}).get("verdict") if (out or {}).get("verdict") in _VERDICT_STATUS else "uncertain"
        feedback = str((out or {}).get("feedback") or "There is not enough reliable information to score this yet.")[:600]
        misc, tq = (out or {}).get("misconception"), (out or {}).get("targeted_question")
    if expected and len(expected.strip()) > 2 and expected.strip().lower() in feedback.lower():
        feedback = "Not quite yet — compare your answer with the key idea, then try the next step."
    status = _VERDICT_STATUS[verdict]
    quote = [{"sentence_id": "answer", "text": answer.strip()}] if status != "unscored" else []
    crit = [{"criterion": "correctness", "status": status, "score": {"absent": 0, "partial": 1, "demonstrated": 2}.get(status),
             "quotes": quote, "missing": [], "covered_essentials": [], "rationale": feedback}]
    for c in ("essential_coverage", "why_relationships", "example_application", "limits"):
        if transfer and c == "example_application":
            crit.append({**crit[0], "criterion": c, "rationale": "Applying the idea to the new situation."})
        else:
            crit.append({"criterion": c, "status": "na", "score": None, "quotes": [], "missing": [], "covered_essentials": [],
                         "rationale": "Not applicable."})
    applicable = [c for c in crit if c["status"] != "na"]
    total = None if any(c["status"] == "unscored" for c in applicable) else sum(c["score"] for c in applicable)
    misconception = ({"code": "generated", "message": str(misc or "Not quite yet.")[:300],
                      "targeted_question": str(tq)[:300] if tq else None} if verdict == "incorrect" and (misc or tq) else None)
    a = Assessment(owner_id=attempt.owner_id, attempt_id=attempt.id, method=method, method_label=label, criteria=crit,
                   outcome=_OUTCOME[status], sufficiency="sufficient" if status != "unscored" else "limited",
                   reason="", feedback=feedback, misconception=misconception, total=total)
    db.add(a)
    db.flush()
    return a
