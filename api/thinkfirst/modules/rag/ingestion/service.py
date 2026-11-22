"""ingestion service: uploads -> extraction jobs -> proposed scope -> student confirmation (C01/C02, UC03-UC06, UC32-UC33)."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core import events, jobs
from thinkfirst.core.db import utcnow
from thinkfirst.core.deps import get_owned
from thinkfirst.core.errors import Conflict, NotFound, ValidationFailed
from thinkfirst.core.storage import get_storage, sha256
from thinkfirst.modules.rag.ingestion import extract
from thinkfirst.modules.rag.ingestion.models import (
    Concept,
    ConceptGraphRevision,
    Source,
    SourceChunk,
    SourceItem,
    SourcePage,
    SourceRevision,
)
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.platform.workspaces import service as workspaces

ROLES = {"course", "notes", "past_exam"}
ACTIVE_STATUSES = {"queued", "extracting", "extracted", "awaiting_confirmation", "ready"}
TOC_LABEL = "From your book's table of contents: one level per chapter"
OUTLINE_LABEL = "Extracted from your course headings (check each level)"
HEURISTIC_LABEL = "Heuristic extraction from your document's numbered headings (no AI used). Check every item."
AI_LABEL_TMPL = "AI-proposed scope ({provider}). Check every item; uncertain items are marked."
GENERATED_LABEL = "AI-generated starter scope (Demo data). Not extracted from your course."


def limits() -> dict:
    s = get_settings()
    return {"max_file_bytes": s.max_file_bytes, "max_files_per_batch": s.max_files_per_batch,
            "max_pages_per_file": s.max_pages_per_file,
            "accepted": ["PDF (text)", "PPTX", "TXT", "MD", "Pasted text"],
            "not_yet": ["Scanned PDFs and photos (OCR arrives in a later milestone)"]}


# ---------------- uploads ----------------

def add_source(db: Session, owner_id: str, subject_id: str, filename: str, mime: str, data: bytes,
               role: str, rights_ack: bool) -> Source:
    workspaces.get_subject(db, owner_id, subject_id)
    if role not in ROLES:
        raise ValidationFailed("Choose Course, Notes or Past exam.", field="role")
    if not rights_ack:
        raise ValidationFailed("Confirm you may use these materials for your own study.", field="rights_ack")
    s = get_settings()
    src = Source(owner_id=owner_id, subject_id=subject_id, filename=filename[:300] or "untitled", role=role,
                 mime=mime or "application/octet-stream", size_bytes=len(data), rights_ack=True)
    db.add(src)
    db.flush()
    kind = extract.detect_kind(filename, mime)
    if kind is None:
        src.status, src.error_code = "needs_attention", "UNSUPPORTED_TYPE"
        return src
    if len(data) > s.max_file_bytes:
        src.status, src.error_code = "needs_attention", "TOO_LARGE"
        return src
    if not data:
        src.status, src.error_code = "needs_attention", "EMPTY_FILE"
        return src
    _new_revision(db, src, data, kind)
    return src


def _new_revision(db: Session, src: Source, data: bytes, kind: str) -> SourceRevision:
    no = (db.scalar(select(func.max(SourceRevision.revision_no)).where(SourceRevision.source_id == src.id)) or 0) + 1
    rev = SourceRevision(owner_id=src.owner_id, source_id=src.id, revision_no=no, checksum=sha256(data),
                         generation=src.generation)
    db.add(rev)
    db.flush()
    rev.storage_key = f"private/{src.owner_id}/sources/{src.id}/{rev.id}"
    get_storage().put(rev.storage_key, data, src.mime)
    src.status, src.error_code = "queued", None
    jobs.enqueue(db, "ingestion.extract", src.owner_id, {"revision_id": rev.id, "kind": kind},
                 idempotency_key=f"extract:{rev.id}:{src.generation}")
    return rev


@jobs.job_handler("ingestion.extract")
def _extract_job(db: Session, job: jobs.Job) -> dict:
    rev = db.get(SourceRevision, job.payload["revision_id"])
    if rev is None:
        raise jobs.JobError("REVISION_MISSING")
    src = db.get(Source, rev.source_id)
    assert src is not None
    if src.generation != rev.generation or src.status in ("cancelled", "excluded") or src.removed_at:
        return {"stale": True}  # late callback for a cancelled/replaced generation: rejected
    src.status = "extracting"
    try:
        pages = extract.extract_pages(get_storage().get(rev.storage_key or ""), job.payload["kind"],
                                      get_settings().max_pages_per_file)
    except extract.ExtractionError as exc:
        src.status, src.error_code = "needs_attention", exc.code
        return {"source_id": src.id, "status": src.status, "error_code": exc.code}
    rev.page_count = len(pages)
    for i, text in enumerate(pages, start=1):
        db.add(SourcePage(owner_id=src.owner_id, revision_id=rev.id, page_no=i, text=text))
    new_chunks = []
    for ch in extract.chunk_pages(pages):
        row = SourceChunk(owner_id=src.owner_id, revision_id=rev.id, subject_id=src.subject_id, page_no=ch.page_no,
                          span_start=ch.start, span_end=ch.end, text=ch.text, embedding=extract.demo_embed(ch.text))
        db.add(row)
        new_chunks.append(row)
    db.flush()
    if len(new_chunks) <= 300:
        from thinkfirst.modules.rag import service as rag

        rag.index_course_chunks(db, new_chunks)  # Qdrant + embeddings (fallback vectors stay in Postgres)
    else:  # a book: the student sees the roadmap first, indexing (minutes) continues in its own job
        jobs.enqueue(db, "ingestion.index_chunks", src.owner_id, {"revision_id": rev.id}, idempotency_key=f"index:{rev.id}")
    src.current_revision_id = rev.id
    src.status, src.error_code = "extracted", None
    db.flush()
    events.publish(db, events.Event(events.CONTENT_INDEXED, src.owner_id, {
        "subject_id": src.subject_id, "source_id": src.id, "revision_id": rev.id, "pages": len(pages),
    }))
    propose_scope(db, src.owner_id, src.subject_id)
    return {"source_id": src.id, "status": src.status, "pages": len(pages)}


@jobs.job_handler("ingestion.index_chunks")
def _index_job(db: Session, job: jobs.Job) -> dict:
    from thinkfirst.modules.rag import service as rag

    rows = list(db.scalars(select(SourceChunk).where(SourceChunk.revision_id == job.payload["revision_id"])).all())
    for i in range(0, len(rows), 256):
        rag.index_course_chunks(db, rows[i:i + 256])
    return {"chunks": len(rows)}


def _sources(db: Session, owner_id: str, subject_id: str) -> list[Source]:
    return list(db.scalars(select(Source).where(Source.owner_id == owner_id, Source.subject_id == subject_id)
                           .order_by(Source.created_at)).all())


def propose_scope(db: Session, owner_id: str, subject_id: str) -> ConceptGraphRevision | None:
    """Build a proposed graph revision once no usable source is still processing."""
    srcs = [s for s in _sources(db, owner_id, subject_id) if not s.removed_at]
    if any(s.status in ("queued", "extracting") for s in srcs):
        return None
    usable = [s for s in srcs if s.status in ("extracted", "awaiting_confirmation", "ready") and s.current_revision_id]
    subject = workspaces.get_subject(db, owner_id, subject_id)
    if not usable:
        if subject.status != "ready":
            subject.status = "needs_attention"
        return None
    concepts, items, citations_src = [], [], {}
    basis, label = "", ""
    for s in usable:  # every file contributes, with the best structure it has
        pages = [p.text for p in db.scalars(select(SourcePage).where(SourcePage.revision_id == s.current_revision_id)
                                            .order_by(SourcePage.page_no)).all()]
        cs, its, b, lab = _source_scope(db, owner_id, s, pages)
        cs, its = _renumber(cs, its, {c.key for c in concepts}, max((c.unit_no for c in concepts), default=0))
        for c in cs:
            citations_src[c.key] = (s, c)
        concepts.extend(cs)
        items.extend((s, it) for it in its)
        if cs and not basis:
            basis, label = b, lab
    if not concepts:
        if not concepts:
            for s in usable:
                s.status, s.error_code = "needs_attention", "NO_STRUCTURE_FOUND"
            subject.status = "needs_attention"
            return None
    # supersede older proposals
    for old in db.scalars(select(ConceptGraphRevision).where(ConceptGraphRevision.subject_id == subject_id,
                                                             ConceptGraphRevision.owner_id == owner_id,
                                                             ConceptGraphRevision.status == "proposed")).all():
        old.status = "superseded"
    no = (db.scalar(select(func.max(ConceptGraphRevision.revision_no))
                    .where(ConceptGraphRevision.subject_id == subject_id)) or 0) + 1
    rev = ConceptGraphRevision(owner_id=owner_id, subject_id=subject_id, revision_no=no, status="proposed",
                               basis=basis, extraction_label=label)
    db.add(rev)
    db.flush()
    seen: set[str] = set()
    for pos, c in enumerate(concepts):
        if c.key in seen:
            continue
        seen.add(c.key)
        s, _ = citations_src.get(c.key, (usable[0], c))
        db.add(Concept(owner_id=owner_id, graph_revision_id=rev.id, subject_id=subject_id, key=c.key, title=c.title,
                       objective=c.objective, unit_no=c.unit_no, unit_title=c.unit_title, position=pos,
                       prerequisites=c.prerequisites, is_foundation=c.is_foundation, uncertain=c.uncertain,
                       citations=[{"source_id": s.id, "revision_id": s.current_revision_id, "page": c.page,
                                   "span": [c.span_start, c.span_end], "quote": c.quote,
                                   "filename": s.filename}]))
    db.execute(delete(SourceItem).where(SourceItem.subject_id == subject_id, SourceItem.owner_id == owner_id))
    for s, it in items:
        db.add(SourceItem(owner_id=owner_id, revision_id=s.current_revision_id, subject_id=subject_id,
                          concept_key=it.concept_key, kind=it.kind, prompt=it.prompt, expression=it.expression,
                          page_no=it.page))
    for s in usable:
        if s.status == "extracted":
            s.status = "awaiting_confirmation"
    if subject.status != "ready":
        subject.status = "awaiting_confirmation"
    db.flush()
    return rev


def _source_scope(db: Session, owner_id: str, src: Source, pages: list[str]) -> tuple[list, list, str, str]:
    """(concepts, exercises, basis, label) for one file: table of contents (books) > numbered headings > AI > headings."""
    if len(pages) > 60 and (toc := extract.toc_scope(pages)):
        return toc, [], "extracted-outline", TOC_LABEL
    cs, its = extract.heuristic_scope(pages)
    if cs:
        return cs, its, "extracted-heuristic", HEURISTIC_LABEL
    provider = llm.active_provider()
    if provider != "demo" and (ai := _ai_scope(db, owner_id, src)):
        return ai, [], "extracted-ai", AI_LABEL_TMPL.format(provider=provider)
    return extract.outline_scope(pages), [], "extracted-outline", OUTLINE_LABEL


def _renumber(concepts: list, items: list, taken: set[str], last_unit: int) -> tuple[list, list]:
    """Second file also starts at "1.1"? Continue the unit numbers instead of dropping its concepts."""
    if not taken & {c.key for c in concepts}:
        return concepts, items
    remap: dict[str, str] = {}
    foundations = sum(1 for k in taken if k.startswith("F"))
    for c in concepts:
        unit, _, rest = c.key.partition(".")
        new = (f"F{foundations + int(c.key[1:])}" if c.key[:1] == "F" and c.key[1:].isdigit()
               else f"{int(unit) + last_unit}.{rest}" if unit.isdigit() and rest else f"{last_unit + c.unit_no}.{c.key}")
        remap[c.key] = new[:32]
    for c in concepts:
        c.key, c.unit_no = remap[c.key], c.unit_no + last_unit
        c.prerequisites = [remap.get(k, k) for k in c.prerequisites]
    for it in items:
        it.concept_key = remap.get(it.concept_key, it.concept_key)
    return concepts, items


def concept_text(db: Session, owner_id: str, concept: Concept, limit: int = 6000) -> str:
    """The course text of a concept: its cited page up to where the next concept of that file starts."""
    ex = concept_excerpt(db, owner_id, concept)
    if not ex or ex.get("tombstone"):
        return ""
    ci = concept.citations[0]
    starts = sorted(c.citations[0]["page"] for c in concepts_of(db, concept.graph_revision_id)
                    if c.citations and c.citations[0].get("source_id") == ci["source_id"] and c.citations[0]["page"] > ci["page"])
    end = starts[0] if starts else ci["page"] + 12
    if end <= ci["page"] + 1:
        return ex["text"]
    pages = db.scalars(select(SourcePage).where(SourcePage.revision_id == ci["revision_id"], SourcePage.page_no >= ci["page"],
                                                SourcePage.page_no < end).order_by(SourcePage.page_no).limit(40)).all()
    per = max(300, limit // max(1, len(pages)))
    return "\n".join(p.text[:per] for p in pages)[:limit]


def _ai_scope(db: Session, owner_id: str, s: Source) -> list:
    pages = db.scalars(select(SourcePage).where(SourcePage.revision_id == s.current_revision_id)
                       .order_by(SourcePage.page_no)).all()
    step = max(1, len(pages) // 40)
    sample = pages[::step][:40]
    per = max(400, 28_000 // max(1, len(sample)))  # stay inside the provider's request size
    res = llm.run(db, "propose_concepts", {"course_pages": [{"page": p.page_no, "text": p.text[:per]} for p in sample]},
                  owner_id=owner_id, purpose="scope_proposal")
    if res.status != "ok" or not res.output:
        return []
    out = []
    page_text = {p.page_no: p.text for p in pages}
    for unit in res.output.get("units", []):
        for c in unit.get("concepts", []):
            page = int(c.get("page") or 1)
            text = page_text.get(page, "")
            idx = text.lower().find(str(c.get("title", "")).lower()[:20])
            quote = text[idx: idx + 200] if idx >= 0 else ""  # verbatim or nothing — never invented
            pc = extract.ProposedConcept(key=str(c["key"])[:32], title=str(c["title"])[:300], unit_no=int(unit.get("no", 1)),
                                         unit_title=str(unit.get("title", "")), page=page, span_start=max(idx, 0),
                                         span_end=max(idx, 0) + len(quote), objective=str(c.get("objective", "")),
                                         prerequisites=[str(p) for p in c.get("prerequisites", [])],
                                         is_foundation=bool(c.get("is_foundation")), uncertain=True, quote=quote)
            out.append(pc)
    return out


def confirm_scope(db: Session, owner_id: str, subject_id: str, graph_revision_id: str, edits: list[dict]) -> ConceptGraphRevision:
    rev = get_owned(db, ConceptGraphRevision, graph_revision_id, owner_id)
    if rev.subject_id != subject_id:
        raise NotFound()
    if rev.status != "proposed":
        raise Conflict("This scope proposal is no longer current. Review the latest one.", code="STALE_REVISION")
    by_id = {c.id: c for c in db.scalars(select(Concept).where(Concept.graph_revision_id == rev.id)).all()}
    for e in edits:
        c = by_id.get(e.get("concept_id", ""))
        if c is None:
            continue
        if "title" in e and str(e["title"]).strip():
            c.title = str(e["title"]).strip()[:300]
        if "excluded" in e:
            c.excluded = bool(e["excluded"])
    if all(c.excluded for c in by_id.values()):
        raise ValidationFailed("Keep at least one concept in scope.")
    for old in db.scalars(select(ConceptGraphRevision).where(ConceptGraphRevision.subject_id == subject_id,
                                                             ConceptGraphRevision.status == "confirmed")).all():
        old.status = "superseded"  # historical attempts keep their frozen concept/rubric copies
    rev.status, rev.confirmed_at = "confirmed", utcnow()
    for s in _sources(db, owner_id, subject_id):
        if s.status == "awaiting_confirmation":
            s.status = "ready"
    workspaces.set_status(db, owner_id, subject_id, "ready", rev.id)
    events.publish(db, events.Event(events.SOURCE_CONFIRMED, owner_id, {"subject_id": subject_id, "graph_revision_id": rev.id}))
    events.publish(db, events.Event(events.GRAPH_BUILT, owner_id, {"subject_id": subject_id, "graph_revision_id": rev.id}))
    return rev


# ---------------- recovery (UC04) ----------------

def _source(db: Session, owner_id: str, source_id: str) -> Source:
    return get_owned(db, Source, source_id, owner_id)


def retry_source(db: Session, owner_id: str, source_id: str) -> Source:
    src = _source(db, owner_id, source_id)
    if src.status != "needs_attention":
        return src
    rev = _latest_revision(db, src)
    if rev is None:
        return src
    job = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"extract:{rev.id}:{src.generation}"))
    if job is not None:
        src.status, src.error_code = "queued", None
        job.status = jobs.FAILED  # allow retry of the same job ID
        jobs.retry(db, job)
    return src


def _latest_revision(db: Session, src: Source) -> SourceRevision | None:
    return db.scalar(select(SourceRevision).where(SourceRevision.source_id == src.id)
                     .order_by(SourceRevision.revision_no.desc()))


def replace_source(db: Session, owner_id: str, source_id: str, filename: str, mime: str, data: bytes) -> Source:
    src = _source(db, owner_id, source_id)
    kind = extract.detect_kind(filename, mime)
    src.generation += 1  # in-flight jobs for the previous file become stale
    src.filename, src.mime, src.size_bytes = filename[:300], mime, len(data)
    if kind is None or len(data) > get_settings().max_file_bytes or not data:
        src.status = "needs_attention"
        src.error_code = "UNSUPPORTED_TYPE" if kind is None else ("TOO_LARGE" if data else "EMPTY_FILE")
        return src
    _new_revision(db, src, data, kind)
    return src


def cancel_source(db: Session, owner_id: str, source_id: str) -> Source:
    src = _source(db, owner_id, source_id)
    if src.status in ("queued", "extracting"):
        src.generation += 1
        src.status = "cancelled"
        for job in db.scalars(select(jobs.Job).where(jobs.Job.owner_id == owner_id, jobs.Job.type == "ingestion.extract")).all():
            if job.status not in jobs.TERMINAL:
                jobs.cancel(db, job)
        propose_scope(db, owner_id, src.subject_id)
    return src


def exclude_source(db: Session, owner_id: str, source_id: str) -> Source:
    src = _source(db, owner_id, source_id)
    if src.status != "ready":
        src.status = "excluded"
        propose_scope(db, owner_id, src.subject_id)
    return src


def removal_impact(db: Session, owner_id: str, source_id: str) -> dict:
    src = _source(db, owner_id, source_id)
    cited = db.scalars(select(Concept).where(Concept.subject_id == src.subject_id, Concept.owner_id == owner_id)).all()
    n = sum(1 for c in cited if any(ci.get("source_id") == src.id for ci in c.citations))
    return {"source_id": src.id, "filename": src.filename, "cited_concepts": n,
            "evidence_effect": "Existing evidence receipts are kept; their citations to this file become tombstones."}


def remove_source(db: Session, owner_id: str, source_id: str) -> Source:
    """W04 removal: delete content, keep a tombstone. Evidence is not rewritten (UC32)."""
    src = _source(db, owner_id, source_id)
    if src.removed_at:
        return src
    for rev in db.scalars(select(SourceRevision).where(SourceRevision.source_id == src.id)).all():
        if rev.storage_key:
            get_storage().delete(rev.storage_key)
            rev.storage_key = None
        db.execute(delete(SourcePage).where(SourcePage.revision_id == rev.id))
        db.execute(delete(SourceChunk).where(SourceChunk.revision_id == rev.id))
        from thinkfirst.modules.rag import service as rag

        rag.delete_course_revision(rev.id)
    src.removed_at = utcnow()
    src.generation += 1
    return src


# ---------------- reads ----------------

def active_concepts(db: Session, owner_id: str, subject_id: str) -> list[Concept]:
    subject = workspaces.get_subject(db, owner_id, subject_id)
    if not subject.active_graph_revision_id:
        return []
    return list(db.scalars(select(Concept).where(Concept.graph_revision_id == subject.active_graph_revision_id,
                                                 Concept.owner_id == owner_id, Concept.excluded.is_(False))
                           .order_by(Concept.unit_no, Concept.position)).all())


def get_concept(db: Session, owner_id: str, concept_id: str) -> Concept:
    return get_owned(db, Concept, concept_id, owner_id)


def proposed_revision(db: Session, owner_id: str, subject_id: str) -> ConceptGraphRevision | None:
    return db.scalar(select(ConceptGraphRevision).where(ConceptGraphRevision.subject_id == subject_id,
                                                        ConceptGraphRevision.owner_id == owner_id,
                                                        ConceptGraphRevision.status == "proposed")
                     .order_by(ConceptGraphRevision.revision_no.desc()))


def concepts_of(db: Session, revision_id: str) -> list[Concept]:
    return list(db.scalars(select(Concept).where(Concept.graph_revision_id == revision_id)
                           .order_by(Concept.unit_no, Concept.position)).all())


def items_for(db: Session, owner_id: str, subject_id: str, concept_key: str) -> list[SourceItem]:
    return list(db.scalars(select(SourceItem).where(SourceItem.owner_id == owner_id, SourceItem.subject_id == subject_id,
                                                    SourceItem.concept_key == concept_key)).all())


def all_items(db: Session, owner_id: str, subject_id: str) -> list[SourceItem]:
    return list(db.scalars(select(SourceItem).where(SourceItem.owner_id == owner_id,
                                                    SourceItem.subject_id == subject_id)).all())


def page_text(db: Session, owner_id: str, source_id: str, page_no: int) -> dict:
    src = _source(db, owner_id, source_id)
    if src.removed_at or not src.current_revision_id:
        return {"tombstone": True, "source_id": src.id, "filename": src.filename,
                "removed_at": src.removed_at.isoformat() if src.removed_at else None}
    rev = db.get(SourceRevision, src.current_revision_id)
    page = db.scalar(select(SourcePage).where(SourcePage.revision_id == src.current_revision_id,
                                              SourcePage.page_no == page_no))
    if page is None:
        raise NotFound("This page is not available.")
    return {"tombstone": False, "source_id": src.id, "filename": src.filename, "revision_no": rev.revision_no if rev else None,
            "page": page_no, "page_count": rev.page_count if rev else None, "text": page.text}


def concept_excerpt(db: Session, owner_id: str, concept: Concept) -> dict | None:
    """Cited chunk for Learn: verbatim text of the concept's cited span."""
    if not concept.citations:
        return None
    ci = concept.citations[0]
    src = db.get(Source, ci["source_id"])
    if src is None or src.removed_at:
        return {"tombstone": True, **ci}
    page = db.scalar(select(SourcePage).where(SourcePage.revision_id == ci["revision_id"], SourcePage.page_no == ci["page"]))
    if page is None:
        return {"tombstone": True, **ci}
    s, e = ci.get("span", [0, len(page.text)])
    return {"tombstone": False, **ci, "text": page.text[s:e].strip() or page.text[:800]}


def retrieve(db: Session, owner_id: str, subject_id: str, query: str, k: int = 3) -> list[tuple[float, SourceChunk]]:
    from thinkfirst.modules.rag import service as rag

    return rag.search_course(db, owner_id, subject_id, query, k)


def sources_public(db: Session, owner_id: str, subject_id: str) -> list[dict]:
    out = []
    for s in _sources(db, owner_id, subject_id):
        rev = db.get(SourceRevision, s.current_revision_id) if s.current_revision_id else None
        out.append({"id": s.id, "filename": s.filename, "role": s.role, "mime": s.mime, "size_bytes": s.size_bytes,
                    "status": "removed" if s.removed_at else s.status, "error_code": s.error_code,
                    "content_category": s.content_category, "revision_no": rev.revision_no if rev else None,
                    "page_count": rev.page_count if rev else None,
                    "removed_at": s.removed_at.isoformat() if s.removed_at else None})
    return out


def concept_public(c: Concept) -> dict:
    return {"id": c.id, "key": c.key, "title": c.title, "objective": c.objective, "unit_no": c.unit_no,
            "unit_title": c.unit_title, "position": c.position, "prerequisites": c.prerequisites,
            "citations": c.citations, "is_foundation": c.is_foundation, "uncertain": c.uncertain, "excluded": c.excluded}


# ---------------- UC05 guided topic ----------------

GUIDED_TOPICS = {
    "algebra": {
        "title": "Algebra foundations",
        "concepts": [
            ("F1", "Order of operations", "Evaluate expressions using the order of operations.", [], True),
            ("1.1", "Variables and terms", "Identify terms, coefficients and constants.", [], False),
            ("1.2", "The distributive property", "Expand a product a(b + c) into ab + ac.", ["1.1", "F1"], False),
            ("1.3", "Combining like terms", "Simplify expressions by combining like terms.", ["1.2"], False),
        ],
    }
}


def create_guided_scope(db: Session, owner_id: str, subject_id: str, discipline: str) -> ConceptGraphRevision:
    topic = GUIDED_TOPICS.get(discipline)
    if topic is None:
        raise ValidationFailed("Only 'algebra' is available as a guided topic in this build.", field="discipline")
    rev = ConceptGraphRevision(owner_id=owner_id, subject_id=subject_id, revision_no=1, status="proposed",
                               basis="generated", extraction_label=GENERATED_LABEL)
    db.add(rev)
    db.flush()
    for pos, (key, title, objective, prereq, foundation) in enumerate(topic["concepts"]):
        db.add(Concept(owner_id=owner_id, graph_revision_id=rev.id, subject_id=subject_id, key=key, title=title,
                       objective=objective, unit_no=1, unit_title=topic["title"], position=pos, prerequisites=prereq,
                       is_foundation=foundation, uncertain=True, citations=[]))
    workspaces.set_status(db, owner_id, subject_id, "awaiting_confirmation")
    return rev


# ---------------- learn any topic directly (no documents required) ----------------

TOPIC_LABEL_TMPL = "AI-generated roadmap for “{topic}” ({provider}). Not from your course — edit freely."


@llm.register_demo("generate_topic_scope")
def _demo_topic_scope(v: dict) -> dict:
    """Demo adapter (no AI key): only the built-in algebra starter is available."""
    topic = str(v.get("student_topic", "")).lower()
    if any(w in topic for w in ("algebra", "algèbre", "distribut", "expression", "equation", "équation")):
        cs = GUIDED_TOPICS["algebra"]["concepts"]
        return {"title": GUIDED_TOPICS["algebra"]["title"], "units": [{"no": 1, "title": GUIDED_TOPICS["algebra"]["title"],
                "concepts": [{"key": k, "title": t, "objective": o, "prerequisites": p, "is_foundation": f}
                             for k, t, o, p, f in cs]}]}
    return {"title": v.get("student_topic", ""), "units": []}


def start_topic_scope(db: Session, owner_id: str, subject_id: str, topic: str, level: str) -> None:
    topic = (topic or "").strip()[:200]
    if len(topic) < 2:
        raise ValidationFailed("Type what you want to learn.", field="topic")
    workspaces.set_status(db, owner_id, subject_id, "processing")
    jobs.enqueue(db, "ingestion.topic_scope", owner_id, {"subject_id": subject_id, "topic": topic, "level": level},
                 idempotency_key=f"topic:{subject_id}")


@jobs.job_handler("ingestion.topic_scope")
def _topic_scope_job(db: Session, job: jobs.Job) -> dict:
    p = job.payload
    owner, subject_id = job.owner_id, p["subject_id"]
    from thinkfirst.modules.rag import service as rag

    g = rag.hybrid(db, owner, subject_id, p["topic"], fetch_query=p["topic"])  # library first, live fetch if missing
    found = g["citations"]
    grounding = g["text"][:6000]
    units: list = []
    for _ in range(2):
        res = llm.run(db, "generate_topic_scope", {"student_topic": p["topic"], "level": p.get("level", "university"),
                                                   "course_excerpt": grounding}, owner_id=owner, purpose="topic_scope")
        units = [u for u in (res.output or {}).get("units") or [] if isinstance(u, dict)]
        if res.status == "ok" and any(u.get("concepts") for u in units):
            break
    if res.status != "ok" or not any(u.get("concepts") for u in units):
        if not res.simulated:
            raise jobs.JobError("TOPIC_GENERATION_FAILED")  # setup shows "Try again"
        workspaces.set_status(db, owner_id=owner, subject_id=subject_id, status="needs_attention")
        return {"error": "TOPIC_GENERATION_FAILED" if not res.simulated else "AI_NOT_CONFIGURED"}
    no = (db.scalar(select(func.max(ConceptGraphRevision.revision_no))
                    .where(ConceptGraphRevision.subject_id == subject_id)) or 0) + 1
    rev = ConceptGraphRevision(owner_id=owner, subject_id=subject_id, revision_no=no, status="proposed", basis="generated",
                               extraction_label=(TOPIC_LABEL_TMPL.format(topic=p["topic"][:60], provider=res.label.split("(")[-1].split(")")[0])
                                                 + (f" Grounded in {len(found)} open source(s) ({'shared library' if g['route'] == 'library' else 'fetched live'})."
                                                    if found else ""))[:200])
    db.add(rev)
    db.flush()
    pos, seen = 0, set()
    for u in units[:4]:
        for c in (u.get("concepts") or [])[:6]:
            key = str(c.get("key") or f"{u.get('no', 1)}.{pos + 1}")[:32]
            if key in seen:
                continue
            seen.add(key)
            db.add(Concept(owner_id=owner, graph_revision_id=rev.id, subject_id=subject_id, key=key,
                           title=str(c.get("title", key))[:300], objective=str(c.get("objective", ""))[:600],
                           unit_no=int(u.get("no") or 1), unit_title=str(u.get("title", ""))[:300], position=pos,
                           prerequisites=[str(x)[:32] for x in c.get("prerequisites", [])][:6],
                           is_foundation=bool(c.get("is_foundation")), uncertain=True, citations=[]))
            pos += 1
    subject = workspaces.get_subject(db, owner, subject_id)
    subject.status = "awaiting_confirmation"
    title = str((res.output or {}).get("title") or "").strip()
    if title and subject.name.lower() == p["topic"].lower():
        subject.name = title[:200]
    return {"graph_revision_id": rev.id, "concepts": pos}
