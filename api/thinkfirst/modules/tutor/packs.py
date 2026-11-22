"""Concept packs: per-concept AI-generated lesson + practice + rubric essentials + follow-ups + transfer.

Enhanced with the Agentic Tutor engine (`tutor.fingerprint`, `tutor.similarity`, `tutor.agents.verify`,
and `tutor.llm.mock.MockLLM`):
- Extracts the course fingerprint (vocabulary, notation profile, imperative verbs, difficulty Elo) to condition
  pack generation on the student's actual course style.
- Scores generated lessons and practice items for course-likeness (`likeness` & `likeness_detail`) and verifies
  answer keys with SymPy / structural checks.
- Provides a grounded deterministic offline fallback via `MockLLM` when no external LLM key is active, so every
  concept gets a real course-grounded lesson, practice items with 4-step help ladder hints, and transfer check.
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
from tutor.agents.verify import check_answer_key
from tutor.fingerprint import build_fingerprint, style_summary
from tutor.similarity import CourseProfile, likeness
from tutor.textutil import sentences, tfidf_keywords


@llm.register_demo("generate_concept_pack")
def _demo_pack(v: dict) -> dict:
    """Grounded offline study-pack synthesizer powered by the Agentic Tutor's extractive engine."""
    concept = v.get("concept") or {}
    title = str(concept.get("title") or "Concept").strip()
    objective = str(concept.get("objective") or f"Understand and apply {title}.").strip()
    unit = str(concept.get("unit") or "Course").strip()
    excerpt = str(v.get("course_excerpt") or "").strip()

    raw_sents = [s.strip() for s in sentences(excerpt) if len(s.strip()) >= 20] if excerpt else []
    if not raw_sents:
        raw_sents = [
            f"{title} ({unit}): {objective}",
            f"To apply {title.lower()}, identify the structure of the problem and justify each transformation step.",
            f"Check edge cases and verify that both sides or forms remain equivalent under {title.lower()}.",
        ]

    summary = " ".join(raw_sents[:2])[:1000]
    kws = [k for k, _ in tfidf_keywords([excerpt or summary, f"{title} {objective}"], top=5)] or [title.lower()]
    key_points = [s[:280] for s in raw_sents[:4]]
    if len(key_points) < 2:
        key_points.append(f"Core objective: {objective}"[:280])

    example_sent = next((s for s in raw_sents if any(ch.isdigit() or ch in "=+-" for ch in s)), raw_sents[0])
    practice_items = [
        {
            "prompt": f"Using your course notes on {title}, state or apply the core rule for: {kws[0]}."[:800],
            "answer_kind": "text",
            "difficulty": "easy",
            "expected_answer": raw_sents[0][:350],
            "hints": [
                f"What does the question ask about {title}?",
                f"Look at the course section on {unit}: focus on {kws[0]}.",
                f"Similar example from your course: {example_sent[:220]}",
                f"Worked solution: {raw_sents[0][:300]}",
            ],
        },
        {
            "prompt": f"Explain how {title.lower()} applies in a multi-step problem and what common slip to avoid."[:800],
            "answer_kind": "text",
            "difficulty": "medium",
            "expected_answer": (raw_sents[1] if len(raw_sents) > 1 else objective)[:350],
            "hints": [
                f"Start from the definition of {title.lower()} ({objective[:140]}).",
                f"Connect {kws[0]} to the transformation or condition required by the course.",
                f"Worked example step: {example_sent[:220]}",
                f"Worked solution: {(raw_sents[1] if len(raw_sents) > 1 else objective)[:300]}",
            ],
        },
    ]

    return {
        "lesson": {
            "summary": summary,
            "key_points": key_points,
            "example_problem": f"Worked example — {title} ({unit})",
            "example_steps": example_sent[:1200],
        },
        "practice": practice_items,
        "explain_prompt": f"In your own words, explain {title.lower()} ({objective}), why the rule holds, and give one concrete example.",
        "essentials": {
            "correctness": [f"Accurately states or applies {title.lower()}"],
            "essential_coverage": [f"Includes key concept terms: {', '.join(kws[:3])}"],
            "why_relationships": [f"Explains why {title.lower()} works rather than only quoting a formula"],
            "example_application": [f"Applies {title.lower()} to a concrete example"],
            "limits": [f"Notes boundary conditions or common misconceptions for {title.lower()}"],
        },
        "followups": {
            "why_relationships": f"Why does {title.lower()} hold in that step, and what would break if a condition were changed?",
            "example_application": f"Can you show one new example where {title.lower()} is applied step by step?",
            "limits": f"When does {title.lower()} NOT apply, or what is the most common mistake students make?",
        },
        "transfer": {
            "prompt": f"New situation: apply {title.lower()} to a fresh case involving {kws[0]} and justify why your result is valid.",
            "answer_kind": "text",
            "expected_answer": summary[:350],
            "why_new": f"Applies {title} to a novel context outside the worked example.",
            "hints": [
                f"Identify which part of {title.lower()} governs this new situation.",
                f"Write the relationship for {kws[0]} first, then simplify or justify.",
                "Check that your final answer satisfies the objective.",
            ],
        },
    }


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
    """Warm up: prepare study packs for the first two levels as soon as a roadmap is confirmed (not when the student
    is about to take a placement test: the packs are written for their measured level afterwards)."""
    from thinkfirst.platform.workspaces import service as workspaces

    if workspaces.get_subject(db, e.owner_id, e.payload["subject_id"]).prior_knowledge == "some":
        return
    concepts = [c for c in ingestion.concepts_of(db, e.payload["graph_revision_id"]) if not c.excluded and not c.is_foundation]
    for c in concepts[:2]:
        ensure_pack(db, e.owner_id, e.payload["subject_id"], c.id)


@events.subscribe(events.PROFILE_READY)
def _prefetch_frontier_levels(db: Session, e: events.Event) -> None:
    """Warm up concept packs (grounded via Qdrant + HF RAG) for the student's diagnosed knowledge frontier."""
    sid = e.payload.get("subject_id")
    frontier = set(e.payload.get("frontier") or [])
    if not sid or not frontier:
        return
    for c in ingestion.active_concepts(db, e.owner_id, sid):
        if c.key in frontier:
            ensure_pack(db, e.owner_id, sid, c.id)


def get_pack(db: Session, owner_id: str, concept_id: str) -> ConceptPack | None:
    return db.scalar(select(ConceptPack).where(ConceptPack.owner_id == owner_id, ConceptPack.concept_id == concept_id))


def _subject_course_profile(db: Session, owner_id: str, subject_id: str, grounding: str) -> tuple[dict, CourseProfile]:
    """Build a Tutor CourseFingerprint and CourseProfile from the subject's chunks + current grounding."""
    from thinkfirst.modules.rag.ingestion import models as ing_models

    rows = list(
        db.scalars(
            select(ing_models.SourceChunk).where(
                ing_models.SourceChunk.owner_id == owner_id,
                ing_models.SourceChunk.subject_id == subject_id,
            ).limit(80)
        ).all()
    )
    chunk_dicts = [{"id": r.id, "text": r.text, "origin": "course"} for r in rows]
    if grounding and not chunk_dicts:
        chunk_dicts = [{"id": "grounding", "text": grounding, "origin": "course"}]
    texts = {c["id"]: c["text"] for c in chunk_dicts} or {"default": grounding or ""}
    docs = [{"id": k, "doc_type": "course"} for k in texts]
    fp = build_fingerprint(subject_id, owner_id, docs, texts, "en")
    return fp, CourseProfile.build(fp, chunk_dicts)


def _clean_practice(items: list, profile: CourseProfile | None = None) -> list[dict]:
    out = []
    for it in items or []:
        prompt, answer = str(it.get("prompt", "")).strip(), str(it.get("expected_answer", "")).strip()
        hints = [str(h) for h in (it.get("hints") or []) if str(h).strip()]
        if prompt and answer and len(hints) >= 3:
            answer_kind = it.get("answer_kind") if it.get("answer_kind") in ("expression", "text") else "text"
            quiz_shape = {"kind": "quiz", "question": prompt, "answer": answer, "answer_type": answer_kind}
            problems, flags = check_answer_key(quiz_shape)
            if problems and answer_kind == "expression":
                answer_kind = "text"
            score, detail = likeness(quiz_shape, profile) if profile else (0.85, {})
            out.append({
                "prompt": prompt[:800],
                "answer_kind": answer_kind,
                "difficulty": it.get("difficulty") if it.get("difficulty") in ("easy", "medium", "hard") else "medium",
                "expected_answer": answer[:400],
                "hints": (hints + [f"Worked solution: {answer}"])[:5],
                "likeness": score,
                "likeness_detail": detail,
                "verified": not problems,
                "math_checked": bool(flags.get("math_checked", False)),
            })
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
    from thinkfirst.modules.diagnostic import placement

    fp, course_prof = _subject_course_profile(db, pack.owner_id, pack.subject_id, grounding)
    ctx = placement.learner_context(db, pack.owner_id, pack.subject_id)
    res = llm.run(db, "generate_concept_pack", {
        "concept": {"title": concept.title, "objective": concept.objective, "unit": concept.unit_title},
        "course_excerpt": grounding,
        "course_style": style_summary(fp),
        "learner": {"level": ctx["level"], "goal": ctx["goal"],
                    "already_known": concept.title in ctx["known"]},
    }, owner_id=pack.owner_id, purpose="concept_pack")
    if res.status != "ok" or not res.output:
        pack.status, pack.label, pack.provider = "failed", res.label, res.provider
        return {"status": "failed"}
    o = res.output
    lesson = o.get("lesson") or {}
    transfer = o.get("transfer") or {}
    tr_ok = bool(str(transfer.get("prompt", "")).strip() and str(transfer.get("expected_answer", "")).strip())
    lesson_score, lesson_detail = likeness(
        {"kind": "lesson", "sections": [{"title": concept.title, "body": str(lesson.get("summary", ""))}]},
        course_prof,
    )
    content = {
        "lesson": {
            "summary": str(lesson.get("summary", ""))[:1200],
            "key_points": [str(k)[:300] for k in lesson.get("key_points", [])][:6],
            "example_problem": str(lesson.get("example_problem", ""))[:600],
            "example_steps": str(lesson.get("example_steps", ""))[:1500],
            "likeness": lesson_score,
            "likeness_detail": lesson_detail,
        },
        "practice": _clean_practice(o.get("practice"), course_prof),
        "explain_prompt": str(o.get("explain_prompt", ""))[:600],
        "sources": sources,
        "course_fingerprint": style_summary(fp),
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
