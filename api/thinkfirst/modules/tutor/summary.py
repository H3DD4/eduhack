"""Level-adapted course summary ("résumé") for a subject.

Two modes:
  * course — the student uploaded files. Sections follow the files page by page (a section never crosses files),
    so NOTHING can be skipped by construction. After writing, coverage is CHECKED: every page with text must be
    listed by the model; missing pages get one repair pass, and anything still missing is shown to the student
    (status "incomplete" + the page numbers), never hidden.
  * topic — no files. One detailed section per roadmap concept, grounded in openly licensed sources (RAG hybrid).

Depth follows the learner's level (placement test or "start from scratch" = beginner) and goal (exam / explore);
known concepts get a quick recap, gap concepts the fullest explanation. One job per section, run ONE AFTER ANOTHER
(each finished section queues the next): parallel calls hit the AI provider's rate limit. A failed section is retried
once automatically, then shown with "Try again".
Without an AI service, course mode falls back to a labelled extract of the student's own pages (nothing invented);
topic mode is unavailable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import jobs
from thinkfirst.core.errors import NotFound, ValidationFailed
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.rag.ingestion.models import Source, SourcePage
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.modules.tutor.models import CourseSummary, CourseSummarySection

JOB = "tutor.summary_section"
SECTION_CHARS = 6000
SECTION_PAGES = 6
PAGE_CHARS = 5000
USABLE = ("extracted", "awaiting_confirmation", "ready")
EXTRACT_LABEL = "Extract of your own course pages (no AI service configured — not a summary)"


@llm.register_demo("summarize_course_section")
def _demo_course_section(v: dict) -> dict:
    """No AI: the student's own text, trimmed per page, clearly labelled. Never invented."""
    pages = v.get("course_pages") or []
    blocks = []
    for p in pages:
        text = " ".join(str(p.get("text", "")).split())
        if text:
            blocks.append({"type": "paragraph", "text": text[:700] + ("…" if len(text) > 700 else ""), "pages": [p["page"]]})
    first, last = (pages[0]["page"], pages[-1]["page"]) if pages else (0, 0)
    return {"title": f"Pages {first}–{last}", "blocks": blocks, "key_terms": [], "common_mistakes": [],
            "check_questions": [], "covered_pages": [p["page"] for p in pages if str(p.get("text", "")).strip()]}


# ------------------------------------------------------------------ planning

def _course_pages(db: Session, owner_id: str, subject_id: str) -> list[tuple[Source, list[SourcePage]]]:
    out = []
    for src in db.scalars(select(Source).where(Source.owner_id == owner_id, Source.subject_id == subject_id)
                          .order_by(Source.created_at)).all():
        if src.removed_at or src.status not in USABLE or not src.current_revision_id:
            continue
        pages = db.scalars(select(SourcePage).where(SourcePage.revision_id == src.current_revision_id)
                           .order_by(SourcePage.page_no)).all()
        if any(p.text.strip() for p in pages):
            out.append((src, list(pages)))
    return out


def _focus(keys: list[str], statuses: dict[str, str]) -> str:
    st = [statuses.get(k) for k in keys if k in statuses]
    if st and all(s == "known" for s in st):
        return "known"
    if any(s in ("to_learn", "partly") for s in st):
        return "focus"
    return "new"


def _plan_course(files: list[tuple[Source, list[SourcePage]]], concepts: list, statuses: dict[str, str]) -> list[dict]:
    sections = []
    for src, pages in files:
        buf, size = [], 0
        for p in pages:
            if not p.text.strip():
                continue
            if buf and (size + len(p.text) > SECTION_CHARS or len(buf) >= SECTION_PAGES):
                sections.append((src, buf))
                buf, size = [], 0
            buf.append(p)
            size += len(p.text)
        if buf:
            sections.append((src, buf))
    out = []
    for src, buf in sections:
        nos = [p.page_no for p in buf]
        keys = [c.key for c in concepts for ci in (c.citations or [])[:1]
                if ci.get("source_id") == src.id and ci.get("page") in nos]
        out.append({"title": f"{src.filename} · pages {nos[0]}–{nos[-1]}" if len(nos) > 1 else f"{src.filename} · page {nos[0]}",
                    "pages": [{"source_id": src.id, "filename": src.filename, "page": n} for n in nos],
                    "concept_keys": keys, "focus": _focus(keys, statuses)})
    return out


def _plan_topic(concepts: list, statuses: dict[str, str], level: str) -> list[dict]:
    chosen = [c for c in concepts if not c.is_foundation or level == "beginner"]
    return [{"title": c.title, "pages": [], "concept_keys": [c.key], "focus": _focus([c.key], statuses)} for c in chosen]


def ensure(db: Session, owner_id: str, subject_id: str, *, regenerate: bool = False) -> CourseSummary:
    """Summary for the learner's CURRENT level (re-planned when the level changes or on request)."""
    from thinkfirst.modules.diagnostic import placement
    from thinkfirst.platform.workspaces import service as workspaces

    subject = workspaces.get_subject(db, owner_id, subject_id)
    if subject.status != "ready":
        raise ValidationFailed("Confirm the roadmap first.")
    rep = placement.report(db, owner_id, subject_id)
    if not rep.get("available"):
        raise ValidationFailed("Take the level test (or choose to start from scratch) first, so the summary fits your level.")
    level = rep["level"]
    current = _current(db, owner_id, subject_id)
    if current is not None and current.level == level and not regenerate and current.status != "failed":
        return current
    if current is not None:
        current.superseded = True
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    statuses = {c["key"]: c["status"] for c in rep.get("concepts") or []}
    files = _course_pages(db, owner_id, subject_id)
    mode = "course" if files else "topic"
    if mode == "topic" and llm.active_provider() == "demo":
        raise ValidationFailed("No AI service is configured, so a summary can only be built from uploaded course files.")
    plan = _plan_course(files, concepts, statuses) if mode == "course" else _plan_topic(concepts, statuses, level)
    if not plan:
        raise ValidationFailed("There is nothing to summarise yet.")
    summary = CourseSummary(owner_id=owner_id, subject_id=subject_id, level=level, goal=subject.goal or "explore",
                            mode=mode, status="building")
    db.add(summary)
    db.flush()
    first = None
    for no, sec in enumerate(plan, 1):
        row = CourseSummarySection(owner_id=owner_id, summary_id=summary.id, no=no, title=sec["title"][:300],
                                   pages=sec["pages"], concept_keys=sec["concept_keys"], focus=sec["focus"])
        db.add(row)
        db.flush()
        first = first or row
    jobs.enqueue(db, JOB, owner_id, {"section_id": first.id, "chain": True}, idempotency_key=f"summary:{first.id}")
    db.flush()
    _refresh_status(db, summary)
    return summary


def _current(db: Session, owner_id: str, subject_id: str) -> CourseSummary | None:
    return db.scalar(select(CourseSummary).where(CourseSummary.owner_id == owner_id, CourseSummary.subject_id == subject_id,
                                                 CourseSummary.superseded.is_(False)).order_by(CourseSummary.created_at.desc()))


def _sections(db: Session, summary: CourseSummary) -> list[CourseSummarySection]:
    return list(db.scalars(select(CourseSummarySection).where(CourseSummarySection.summary_id == summary.id)
                           .order_by(CourseSummarySection.no)).all())


def _refresh_status(db: Session, summary: CourseSummary) -> None:
    secs = _sections(db, summary)
    st = [s.status for s in secs]
    if any(x == "pending" for x in st):
        summary.status = "building"
    elif all(x == "ready" for x in st):
        summary.status = "ready"
    elif any(x in ("ready", "incomplete") for x in st):
        summary.status = "partial"
    else:
        summary.status = "failed"
    db.flush()


# ------------------------------------------------------------------ writing one section

def _clean(o: dict) -> dict:
    blocks = []
    for b in o.get("blocks") or []:
        t = str(b.get("type", "paragraph"))
        if t not in ("heading", "paragraph", "bullets", "formula", "definition", "example", "tip", "warning"):
            t = "paragraph"
        text = str(b.get("text", "")).strip()
        items = [str(i).strip()[:600] for i in (b.get("items") or []) if str(i).strip()][:20]
        if text or items:
            blocks.append({"type": t, "text": text[:3000], "items": items,
                           "pages": [int(p) for p in (b.get("pages") or []) if str(p).lstrip("-").isdigit()][:12]})
    return {"blocks": blocks[:80],
            "key_terms": [{"term": str(k.get("term", ""))[:120], "definition": str(k.get("definition", ""))[:500]}
                          for k in (o.get("key_terms") or []) if str(k.get("term", "")).strip()][:20],
            "common_mistakes": [str(m)[:400] for m in (o.get("common_mistakes") or []) if str(m).strip()][:8],
            "check_questions": [str(q)[:400] for q in (o.get("check_questions") or []) if str(q).strip()][:8]}


def _covered(o: dict) -> set[int]:
    pages = {int(p) for p in (o.get("covered_pages") or []) if str(p).lstrip("-").isdigit()}
    for b in o.get("blocks") or []:
        pages |= {int(p) for p in (b.get("pages") or []) if str(p).lstrip("-").isdigit()}
    return pages


@jobs.job_handler(JOB)
def _section_job(db: Session, job: jobs.Job) -> dict:
    from thinkfirst.modules.diagnostic import placement

    sec = db.get(CourseSummarySection, job.payload["section_id"])
    if sec is None:
        raise jobs.JobError("MISSING")
    summary = db.get(CourseSummary, sec.summary_id)
    learner = placement.learner_context(db, summary.owner_id, summary.subject_id)
    learner["level"] = summary.level
    learner["this_section"] = {"known": sec.focus == "known", "focus": sec.focus == "focus"}
    write = _write_course_section if summary.mode == "course" else _write_topic_section
    try:
        result = write(db, summary, sec, learner)
        if sec.status == "failed" and sec.error_code not in ("SOURCE_REMOVED", "CONCEPT_REMOVED"):
            result = write(db, summary, sec, learner)  # one automatic retry (rate limit / malformed answer)
    finally:
        _refresh_status(db, summary)
        if job.payload.get("chain") and not summary.superseded:
            nxt = db.scalar(select(CourseSummarySection).where(CourseSummarySection.summary_id == summary.id,
                                                               CourseSummarySection.status == "pending",
                                                               CourseSummarySection.no > sec.no)
                            .order_by(CourseSummarySection.no))
            if nxt is not None:
                jobs.enqueue(db, JOB, summary.owner_id, {"section_id": nxt.id, "chain": True},
                             idempotency_key=f"summary:{nxt.id}")
    return result


def _write_course_section(db: Session, summary: CourseSummary, sec: CourseSummarySection, learner: dict) -> dict:
    src = db.get(Source, sec.pages[0]["source_id"]) if sec.pages else None
    nos = [p["page"] for p in sec.pages]
    pages = db.scalars(select(SourcePage).where(SourcePage.revision_id == (src.current_revision_id if src else ""),
                                                SourcePage.page_no.in_(nos)).order_by(SourcePage.page_no)).all() if src else []
    if not pages:
        sec.status, sec.error_code = "failed", "SOURCE_REMOVED"
        return {"status": "failed"}
    required = {p.page_no for p in pages if p.text.strip()}
    payload = [{"page": p.page_no, "text": p.text[:PAGE_CHARS]} for p in pages]
    style, profile = _course_style(db, summary)
    res = llm.run(db, "summarize_course_section", {"course_pages": payload, "learner": learner, "file": src.filename,
                                                   "course_style": style}, owner_id=summary.owner_id, purpose="course_summary")
    if res.status != "ok" or not res.output:
        sec.status, sec.error_code = "failed", res.error_code or "AI_FAILED"
        return {"status": "failed"}
    content = _clean(res.output)
    covered = _covered(res.output) & required
    missing = sorted(required - covered)
    if missing:  # one repair pass on exactly the pages the model skipped
        rep = llm.run(db, "summarize_course_section", {
            "course_pages": [x for x in payload if x["page"] in missing], "learner": learner, "file": src.filename,
            "note": "These pages were skipped in the first pass; summarise them completely."},
            owner_id=summary.owner_id, purpose="course_summary_repair")
        if rep.status == "ok" and rep.output:
            extra = _clean(rep.output)
            content["blocks"] += extra["blocks"]
            content["key_terms"] += extra["key_terms"]
            covered |= _covered(rep.output) & required
            missing = sorted(required - covered)
    sec.title = (str(res.output.get("title") or "").strip() or sec.title)[:300]
    if profile is not None and not res.simulated:
        content = _likeness_gate(db, summary, sec, content, profile, payload, learner, src.filename, style)
    sec.content = {**content, "label": EXTRACT_LABEL if res.simulated else res.label, "provider": res.provider}
    sec.missing_pages = missing
    sec.status = "incomplete" if missing else "ready"
    sec.error_code = None
    summary.label, summary.provider = (EXTRACT_LABEL if res.simulated else res.label), res.provider
    return {"status": sec.status, "missing": missing}


def _course_style(db: Session, summary: CourseSummary):
    """Course fingerprint (vocabulary, notation, exercise verbs) + likeness profile from the student's own chunks."""
    try:
        from thinkfirst.modules.tutor.packs import _subject_course_profile
        from tutor.fingerprint import style_summary

        fp, profile = _subject_course_profile(db, summary.owner_id, summary.subject_id, "")
        return style_summary(fp), profile
    except Exception:  # noqa: BLE001 - fingerprinting is an enhancement, never a blocker
        return {}, None


def _section_text(content: dict) -> str:
    parts = [b.get("text", "") + " " + " ".join(b.get("items") or []) for b in content.get("blocks", [])]
    parts += [k["term"] + " " + k["definition"] for k in content.get("key_terms", [])]
    return " ".join(parts)


def _likeness_gate(db: Session, summary: CourseSummary, sec, content: dict, profile, payload: list, learner: dict,
                   filename: str, style: dict) -> dict:
    """Agentic Tutor quality loop: score how much the section reads like the student's course (vocabulary,
    notation). >= 0.70 shown as is; below, rewritten once naming the weak components; the better version is kept."""
    from tutor.similarity import decision, likeness, weak_components

    score, detail = likeness({"kind": "lesson", "sections": [{"title": sec.title, "body": _section_text(content)}]}, profile)
    if decision(score) != "show":  # < 0.70: regenerate once naming the weak parts (Agentic Tutor thresholds)
        weak = ", ".join(weak_components(detail)) or "vocabulary"
        res = llm.run(db, "summarize_course_section", {
            "course_pages": payload, "learner": learner, "file": filename, "course_style": style,
            "note": f"The previous draft did not read like this course (weak: {weak}). Use the course's own terms and "
                    "notation from the pages and course_style."}, owner_id=summary.owner_id, purpose="course_summary_style")
        if res.status == "ok" and res.output:
            retry = _clean(res.output)
            s2, d2 = likeness({"kind": "lesson", "sections": [{"title": sec.title, "body": _section_text(retry)}]}, profile)
            if s2 > score and len(_covered(res.output)) >= len(_covered({"blocks": content["blocks"]})):
                content, score, detail = retry, s2, d2
    return {**content, "likeness": score, "likeness_detail": detail}


def _write_topic_section(db: Session, summary: CourseSummary, sec: CourseSummarySection, learner: dict) -> dict:
    from thinkfirst.modules.rag import service as rag

    concept = next((c for c in ingestion.active_concepts(db, summary.owner_id, summary.subject_id)
                    if c.key in (sec.concept_keys or [])), None)
    if concept is None:
        sec.status, sec.error_code = "failed", "CONCEPT_REMOVED"
        return {"status": "failed"}
    g = rag.hybrid(db, summary.owner_id, summary.subject_id, f"{concept.title} {concept.objective}", fetch_query=concept.title)
    res = llm.run(db, "explain_topic_section", {
        "concept": {"title": concept.title, "objective": concept.objective, "unit": concept.unit_title},
        "course_excerpt": g["text"][:PAGE_CHARS], "learner": learner}, owner_id=summary.owner_id, purpose="topic_summary")
    if res.status != "ok" or not res.output:
        sec.status, sec.error_code = "failed", res.error_code or "AI_FAILED"
        return {"status": "failed"}
    content = _clean(res.output)
    sec.title = concept.title[:300]
    sec.content = {**content, "label": res.label, "provider": res.provider,
                   "sources": [c for c in g["citations"] if c.get("kind") == "open"][:4]}
    sec.status, sec.error_code, sec.missing_pages = "ready", None, []
    summary.label, summary.provider = res.label, res.provider
    return {"status": "ready"}


def retry_section(db: Session, owner_id: str, section_id: str) -> CourseSummarySection:
    sec = db.get(CourseSummarySection, section_id)
    if sec is None or sec.owner_id != owner_id:
        raise NotFound("Section not found.")
    if sec.status not in ("failed", "incomplete"):
        return sec
    job = db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == f"summary:{sec.id}"))
    sec.status = "pending"
    db.flush()
    if job is not None and job.status == jobs.FAILED:
        jobs.retry(db, job)
    else:
        n = len(db.scalars(select(jobs.Job).where(jobs.Job.idempotency_key.like(f"summary:{sec.id}%"))).all())
        jobs.enqueue(db, JOB, owner_id, {"section_id": sec.id}, idempotency_key=f"summary:{sec.id}:r{n}")
    return sec


# ------------------------------------------------------------------ read

def public(db: Session, owner_id: str, subject_id: str) -> dict:
    summary = _current(db, owner_id, subject_id)
    if summary is None:
        return {"summary": None}
    secs = _sections(db, summary)
    required = sum(len(s.pages) for s in secs)
    missing = [{"filename": p["filename"], "page": p["page"]} for s in secs for p in s.pages if p["page"] in (s.missing_pages or [])]
    pending_or_failed = sum(len(s.pages) for s in secs if s.status in ("pending", "failed"))
    return {"summary": {
        "id": summary.id, "level": summary.level, "goal": summary.goal, "mode": summary.mode, "status": summary.status,
        "label": summary.label, "created_at": summary.created_at.isoformat(),
        "progress": {"done": sum(1 for s in secs if s.status != "pending"), "total": len(secs)},
        "coverage": ({"pages_total": required, "pages_covered": required - len(missing) - pending_or_failed,
                      "missing": missing} if summary.mode == "course" else None),
        "sections": [{"id": s.id, "no": s.no, "title": s.title, "status": s.status, "focus": s.focus,
                      "pages": [p["page"] for p in s.pages], "filename": s.pages[0]["filename"] if s.pages else None,
                      "missing_pages": s.missing_pages or [], "error_code": s.error_code,
                      "content": s.content if s.status in ("ready", "incomplete") else None} for s in secs],
    }}
