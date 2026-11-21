"""Concept packs: per-concept AI-generated lesson + practice + rubric essentials + follow-ups + transfer.

Generated once per concept (idempotent job `pack:{concept_id}`), validated structurally, labelled ai-generated.
Without an AI key, only concepts with a built-in template (distributive property) get practice/transfer.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events, jobs
from thinkfirst.modules.diagnostic.grading import service as assessment
from thinkfirst.modules.diagnostic.grading.rubrics import CRITERIA
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.modules.tutor.models import ConceptPack


@llm.register_demo("generate_concept_pack")
def _demo_pack(v: dict) -> dict:
    # No AI service: no invented content. Lesson falls back to the objective; practice/transfer only from templates.
    return {"lesson": {"summary": "", "key_points": [], "example_problem": "", "example_steps": ""}, "practice": [],
            "explain_prompt": "", "essentials": {c: [] for c in CRITERIA}, "followups": {}, "transfer": {
                "prompt": "", "answer_kind": "text", "expected_answer": "", "why_new": "", "hints": []}}


def ensure_pack(db: Session, owner_id: str, subject_id: str, concept_id: str) -> ConceptPack:
    pack = get_pack(db, owner_id, concept_id)
    if pack is None:
        pack = ConceptPack(owner_id=owner_id, subject_id=subject_id, concept_id=concept_id, status="pending")
        db.add(pack)
        db.flush()
        jobs.enqueue(db, "tutor.concept_pack", owner_id, {"pack_id": pack.id}, idempotency_key=f"pack:{concept_id}")
    return pack


@events.subscribe(events.SOURCE_CONFIRMED)
def _prefetch_first_levels(db: Session, e: events.Event) -> None:
    """Warm up: prepare study packs for the first two levels as soon as a roadmap is confirmed."""
    concepts = [c for c in ingestion.concepts_of(db, e.payload["graph_revision_id"]) if not c.excluded and not c.is_foundation]
    for c in concepts[:2]:
        ensure_pack(db, e.owner_id, e.payload["subject_id"], c.id)


def get_pack(db: Session, owner_id: str, concept_id: str) -> ConceptPack | None:
    return db.scalar(select(ConceptPack).where(ConceptPack.owner_id == owner_id, ConceptPack.concept_id == concept_id))


def _clean_practice(items: list) -> list[dict]:
    out = []
    for it in items or []:
        prompt, answer = str(it.get("prompt", "")).strip(), str(it.get("expected_answer", "")).strip()
        hints = [str(h) for h in (it.get("hints") or []) if str(h).strip()]
        if prompt and answer and len(hints) >= 3:
            out.append({"prompt": prompt[:800], "answer_kind": it.get("answer_kind") if it.get("answer_kind") in ("expression", "text") else "text",
                        "difficulty": it.get("difficulty") if it.get("difficulty") in ("easy", "medium", "hard") else "medium",
                        "expected_answer": answer[:400], "hints": (hints + [f"Worked solution: {answer}"])[:5]})
    return out


@jobs.job_handler("tutor.concept_pack")
def _pack_job(db: Session, job: jobs.Job) -> dict:
    pack = db.get(ConceptPack, job.payload["pack_id"])
    if pack is None:
        raise jobs.JobError("MISSING")
    concept = ingestion.get_concept(db, pack.owner_id, pack.concept_id)
    excerpt = ingestion.concept_excerpt(db, pack.owner_id, concept)
    grounding = (excerpt or {}).get("text", "") if excerpt and not excerpt.get("tombstone") else ""
    sources: list[dict] = []
    if not grounding:
        from thinkfirst.modules.rag import service as rag

        g = rag.hybrid(db, pack.owner_id, pack.subject_id, f"{concept.title} {concept.objective}", fetch_query=concept.title)
        grounding, sources = g["text"], [c for c in g["citations"] if c.get("kind") == "open"]
    res = llm.run(db, "generate_concept_pack", {
        "concept": {"title": concept.title, "objective": concept.objective, "unit": concept.unit_title},
        "course_excerpt": grounding,
    }, owner_id=pack.owner_id, purpose="concept_pack")
    if res.status != "ok" or not res.output:
        pack.status, pack.label, pack.provider = "failed", res.label, res.provider
        return {"status": "failed"}
    o = res.output
    lesson = o.get("lesson") or {}
    transfer = o.get("transfer") or {}
    tr_ok = bool(str(transfer.get("prompt", "")).strip() and str(transfer.get("expected_answer", "")).strip())
    content = {
        "lesson": {"summary": str(lesson.get("summary", ""))[:1200], "key_points": [str(k)[:300] for k in lesson.get("key_points", [])][:6],
                   "example_problem": str(lesson.get("example_problem", ""))[:600], "example_steps": str(lesson.get("example_steps", ""))[:1500]},
        "practice": _clean_practice(o.get("practice")),
        "explain_prompt": str(o.get("explain_prompt", ""))[:600],
        "sources": sources,
        "essentials": {c: [str(e)[:200] for e in (o.get("essentials") or {}).get(c, [])][:4] for c in CRITERIA},
        "followups": {c: str(q)[:400] for c, q in (o.get("followups") or {}).items() if c in CRITERIA and str(q).strip()},
        "transfer": ({"prompt": str(transfer["prompt"])[:800], "answer_kind": transfer.get("answer_kind", "text"),
                      "expected_answer": str(transfer["expected_answer"])[:400], "why_new": str(transfer.get("why_new", ""))[:300],
                      "hints": [str(h) for h in transfer.get("hints", [])][:3]} if tr_ok else None),
    }
    pack.content, pack.status, pack.label, pack.provider = content, "ready", res.label, res.provider
    _upgrade_generic_rubric(db, pack, concept, content)
    return {"status": "ready"}


def _upgrade_generic_rubric(db: Session, pack: ConceptPack, concept, content: dict) -> None:
    """Give generic rubrics predeclared essentials from the pack (labelled AI-generated, not domain-approved)."""
    rubric = assessment.get_rubric(db, pack.owner_id, pack.subject_id, concept.key, concept.title)
    if rubric.template != "generic-v1" or not any(content["essentials"].values()):
        return
    criteria = []
    for c in CRITERIA:
        ess = content["essentials"].get(c, [])
        applicable = bool(ess) or c != "limits"
        criteria.append({"criterion": c, "applicable": applicable,
                         "essentials": [{"id": f"{c}-{i}", "description": d, "patterns": []} for i, d in enumerate(ess, 1)]})
    rubric.criteria = criteria
    rubric.template = "generated-v1"
    rubric.approval = "ai-generated-not-domain-approved"
    if content["explain_prompt"]:
        rubric.explain_prompt = content["explain_prompt"]
    if content["followups"]:
        rubric.followup_bank = {c: {"id": f"fu-gen-{c}", "question": q} for c, q in content["followups"].items()}
