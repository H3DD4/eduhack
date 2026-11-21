"""G02/C01/C02/W01/W04/W06/W07 HTTP API (workspaces + ingestion service interfaces)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core import jobs
from thinkfirst.core.db import get_db
from thinkfirst.core.deps import current_user
from thinkfirst.core.errors import ValidationFailed
from thinkfirst.data.student_profile import service as learner
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.tutor import policy
from thinkfirst.platform.identity.models import User
from thinkfirst.platform.workspaces import service as workspaces

router = APIRouter(tags=["workspaces"])


@router.get("/limits")
def limits():
    return ingestion.limits()


@router.get("/subjects")
def list_subjects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for s in workspaces.list_subjects(db, user.id):
        srcs = ingestion.sources_public(db, user.id, s.id)
        from thinkfirst.modules.tutor import service as tutor

        concepts = [c for c in ingestion.active_concepts(db, user.id, s.id) if not c.is_foundation] if s.status == "ready" else []
        sums = learner.concept_summaries(db, user.id, s.id) if concepts else {}
        out.append({**workspaces.subject_public(s), "source_count": len([x for x in srcs if x["status"] != "removed"]),
                    "needs_attention": any(x["status"] == "needs_attention" for x in srcs),
                    "concept_count": len(concepts),
                    "applied_count": sum(1 for c in concepts if "applied_independently" in sums.get(c.id, {}).get("states", [])),
                    "resume": tutor.unfinished_for_subject(db, user.id, s.id)})
    return {"subjects": out}


@router.post("/subjects")
async def create_subject(name: str = Form(...), role: str = Form("course"), rights_ack: bool = Form(False),
                         paste_text: str = Form(""), files: list[UploadFile] = File(default=[]),
                         user: User = Depends(current_user), db: Session = Depends(get_db)):
    """C01: create subject + sources. Unsupported files stay flagged while usable ones proceed (UC03)."""
    s_limits = get_settings()
    files = [f for f in files if f.filename]
    if len(files) > s_limits.max_files_per_batch:
        raise ValidationFailed(f"Choose up to {s_limits.max_files_per_batch} files at a time.", field="files")
    if not files and not paste_text.strip():
        raise ValidationFailed("Add a file or paste your notes, or choose a guided topic.", field="files")
    if not rights_ack:
        raise ValidationFailed("Confirm you may use these materials for your own study.", field="rights_ack")
    subject = workspaces.create_subject(db, user.id, name)
    for f in files:
        data = await f.read()
        ingestion.add_source(db, user.id, subject.id, f.filename or "file", f.content_type or "", data, role, rights_ack)
    if paste_text.strip():
        ingestion.add_source(db, user.id, subject.id, "Pasted notes.txt", "text/plain", paste_text.encode(), role, rights_ack)
    return {"subject": workspaces.subject_public(subject)}


class GuidedIn(BaseModel):
    name: str = "Guided topic"
    discipline: str


@router.post("/subjects/guided")
def create_guided(body: GuidedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    subject = workspaces.create_subject(db, user.id, body.name or "Guided topic", origin="guided_topic")
    ingestion.create_guided_scope(db, user.id, subject.id, body.discipline)
    return {"subject": workspaces.subject_public(subject)}


TOPIC_SUGGESTIONS = [
    {"topic": "Distributive property and expanding brackets", "area": "Algebra", "icon": "∑"},
    {"topic": "Derivatives and the chain rule", "area": "Calculus", "icon": "∂"},
    {"topic": "Newton's laws of motion", "area": "Physics", "icon": "⚙"},
    {"topic": "Ohm's law and simple circuits", "area": "Electronics", "icon": "⚡"},
    {"topic": "Conditional probability and Bayes' rule", "area": "Probability", "icon": "◔"},
    {"topic": "Python loops and functions", "area": "Programming", "icon": "{ }"},
    {"topic": "Matrices and linear systems", "area": "Linear algebra", "icon": "▦"},
    {"topic": "Supply and demand", "area": "Economics", "icon": "↗"},
]


@router.get("/topics/suggestions")
def topic_suggestions():
    from thinkfirst.modules.tutor.llm import service as llm

    caps = llm.capabilities()
    return {"suggestions": TOPIC_SUGGESTIONS, "ai_available": not caps["simulated"], "provider_label": caps["label"]}


class TopicIn(BaseModel):
    topic: str
    level: str = "university"


@router.post("/subjects/topic")
def create_from_topic(body: TopicIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Learn any topic directly: AI-generated roadmap the student confirms (UC05, no documents needed)."""
    subject = workspaces.create_subject(db, user.id, body.topic.strip()[:200] or "New topic", origin="guided_topic")
    ingestion.start_topic_scope(db, user.id, subject.id, body.topic, body.level)
    return {"subject": workspaces.subject_public(workspaces.get_subject(db, user.id, subject.id))}


@router.post("/subjects/{subject_id}/start")
def confirm_and_start(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """One-click 'Start learning' for generated roadmaps: confirms the proposal unchanged."""
    rev = ingestion.proposed_revision(db, user.id, subject_id)
    if rev is None:
        raise ValidationFailed("The roadmap is not ready yet.")
    ingestion.confirm_scope(db, user.id, subject_id, rev.id, [])
    return {"subject": workspaces.subject_public(workspaces.get_subject(db, user.id, subject_id))}


@router.get("/subjects/{subject_id}")
def get_subject(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"subject": workspaces.subject_public(workspaces.get_subject(db, user.id, subject_id))}


@router.delete("/subjects/{subject_id}")
def archive_subject(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.archive(db, user.id, subject_id)
    return {"archived": True}


@router.get("/subjects/{subject_id}/setup")
def setup_state(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """C02: actual phases per file (no invented percentages) + proposed scope with cited pages."""
    subject = workspaces.get_subject(db, user.id, subject_id)
    srcs = ingestion.sources_public(db, user.id, subject_id)
    rev = ingestion.proposed_revision(db, user.id, subject_id)
    job_rows = db.scalars(select(jobs.Job).where(jobs.Job.owner_id == user.id, jobs.Job.type == "ingestion.extract")).all()
    topic_job = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"topic:{subject_id}", jobs.Job.owner_id == user.id))
    if topic_job is not None and topic_job.status == jobs.FAILED and subject.status == "processing":
        subject.status = "needs_attention"  # a failed job must never leave the page "building" forever
    return {"subject": workspaces.subject_public(subject), "sources": srcs,
            "topic_job": jobs.job_public(topic_job) if topic_job else None,
            "jobs": [jobs.job_public(j) for j in job_rows if j.payload.get("revision_id")],
            "proposal": None if rev is None else {
                "id": rev.id, "revision_no": rev.revision_no, "basis": rev.basis, "label": rev.extraction_label,
                "concepts": [ingestion.concept_public(c) for c in ingestion.concepts_of(db, rev.id)]},
            "limits": ingestion.limits()}


class ConfirmIn(BaseModel):
    graph_revision_id: str
    edits: list[dict] = []


@router.post("/subjects/{subject_id}/scope/confirm")
def confirm_scope(subject_id: str, body: ConfirmIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rev = ingestion.confirm_scope(db, user.id, subject_id, body.graph_revision_id, body.edits)
    return {"graph_revision_id": rev.id, "subject": workspaces.subject_public(workspaces.get_subject(db, user.id, subject_id))}


@router.post("/subjects/{subject_id}/sources")
async def add_sources(subject_id: str, role: str = Form("course"), rights_ack: bool = Form(False),
                      files: list[UploadFile] = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for f in files[: get_settings().max_files_per_batch]:
        src = ingestion.add_source(db, user.id, subject_id, f.filename or "file", f.content_type or "", await f.read(), role, rights_ack)
        out.append(src.id)
    return {"source_ids": out}


@router.post("/sources/{source_id}/retry")
def retry_source(source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"status": ingestion.retry_source(db, user.id, source_id).status}


@router.post("/sources/{source_id}/cancel")
def cancel_source(source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"status": ingestion.cancel_source(db, user.id, source_id).status}


@router.post("/sources/{source_id}/exclude")
def exclude_source(source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"status": ingestion.exclude_source(db, user.id, source_id).status}


@router.post("/sources/{source_id}/replace")
async def replace_source(source_id: str, file: UploadFile = File(...), user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    src = ingestion.replace_source(db, user.id, source_id, file.filename or "file", file.content_type or "", await file.read())
    return {"status": src.status}


@router.get("/sources/{source_id}/impact")
def source_impact(source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ingestion.removal_impact(db, user.id, source_id)


@router.delete("/sources/{source_id}")
def remove_source(source_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    src = ingestion.remove_source(db, user.id, source_id)
    return {"status": "removed", "removed_at": src.removed_at.isoformat() if src.removed_at else None}


@router.get("/subjects/{subject_id}/resources")
def resources(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces.get_subject(db, user.id, subject_id)
    lock = policy.active_lock(db, user.id, subject_id)
    from thinkfirst.modules.rag.agent import service as resources

    return {"sources": ingestion.sources_public(db, user.id, subject_id), "locked": lock is not None,
            "open_resources": [] if lock else [resources.public(i) for i in resources.for_subject(db, user.id, subject_id)],
            "generated_aids": [], "generated_aids_note": "Generated study aids arrive in a later milestone."}


@router.get("/documents/{source_id}/pages/{page_no}")
def document_page(source_id: str, page_no: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """W07 cited page. Denied while an independent transfer is active in this subject (no revealing sources)."""
    from thinkfirst.core.deps import get_owned
    from thinkfirst.modules.rag.ingestion.models import Source

    src = get_owned(db, Source, source_id, user.id)
    policy.assert_unlocked(db, user.id, src.subject_id)
    return ingestion.page_text(db, user.id, source_id, page_no)


@router.get("/subjects/{subject_id}/roadmap")
def roadmap(subject_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """W01: vertical path by unit, with dated evidence states (never percentages) and optional foundations."""
    subject = workspaces.get_subject(db, user.id, subject_id)
    concepts = ingestion.active_concepts(db, user.id, subject_id)
    sums = learner.concept_summaries(db, user.id, subject_id)
    units: dict[int, dict] = {}
    for c in concepts:
        u = units.setdefault(c.unit_no, {"unit_no": c.unit_no, "title": c.unit_title, "concepts": [], "foundations": []})
        entry = {**ingestion.concept_public(c), "evidence": _summary_public(sums.get(c.id))}
        (u["foundations"] if c.is_foundation else u["concepts"]).append(entry)
    from thinkfirst.modules.adaptation import service as adaptation

    sug = adaptation.suggest_concept(db, user.id, subject_id)
    suggested = {"id": sug["concept_id"], "reason": sug["reason"], "kind": sug["kind"]} if sug else None
    from thinkfirst.modules.tutor import service as tutor

    all_concepts = [c for u in units.values() for c in u["concepts"]]
    return {"subject": workspaces.subject_public(subject), "units": [units[k] for k in sorted(units)],
            "suggested_concept_id": suggested["id"] if suggested else None,
            "suggestion": suggested,
            "resume": tutor.unfinished_for_subject(db, user.id, subject_id),
            "counts": {"concepts": len(all_concepts),
                       "applied": sum(1 for c in all_concepts if "applied_independently" in c["evidence"]["states"]),
                       "started": sum(1 for c in all_concepts if c["evidence"]["states"])}}


def _summary_public(s: dict | None) -> dict:
    if not s:
        return {"states": [], "highest": None, "highest_text": "Not checked yet", "attempts": 0, "insufficient": True,
                "mixed": False, "review_due_on": None, "receipts": []}
    return {k: s.get(k) for k in ("states", "highest", "highest_text", "attempts", "unscored", "insufficient", "mixed",
                                  "review_due_on", "review_due", "last_at", "receipts")}


@router.get("/subjects/{subject_id}/concepts/{concept_id}")
def concept_detail(subject_id: str, concept_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """W06 inspector: objective, prerequisites (with reasons), citations, evidence. Never a hard gate."""
    c = ingestion.get_concept(db, user.id, concept_id)
    concepts = {x.key: x for x in ingestion.active_concepts(db, user.id, subject_id)}
    sums = learner.concept_summaries(db, user.id, subject_id)
    prereqs = [{"id": concepts[k].id, "key": k, "title": concepts[k].title, "is_foundation": concepts[k].is_foundation,
                "reason": f"Listed as a prerequisite in your course ({c.key})."} for k in c.prerequisites if k in concepts]
    return {"concept": ingestion.concept_public(c), "prerequisites": prereqs,
            "evidence": _summary_public(sums.get(c.id)),
            "items": [{"id": i.id, "prompt": i.prompt, "origin": i.origin, "page": i.page_no}
                      for i in ingestion.items_for(db, user.id, subject_id, c.key)]}
