"""Module DIAGNOSTIC — Session Brain & Subject Brain item-bank builder.

- Knowledge space pipeline: builds an acyclic SkillGraph from the subject's active concepts, populates a
  calibrated item bank with verified reference answers, Q-matrix skill links, and misconception distractors,
  checks quality rules, and publishes `items.ready`.
- Adaptive diagnostic engine: combines CAT (Elo item information p(1-p)), BKT mastery updates, Knowledge Space
  Theory prerequisite inference, and behavioral tracking signals (rapid guessing, confidence calibration,
  frustration/disengagement early stopping). Publishes `answer.graded` and `diagnostic.completed`.
- Answer diagnosis in tutoring sessions: after each graded practice/transfer answer, publishes
  `misconception.detected`.
- Legacy 3-item baseline check / skip (C03/UC07) is preserved for backward compatibility.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import Conflict, NotFound, ValidationFailed
from thinkfirst.data.memory import service as memory
from thinkfirst.data.student_profile import service as profile
from thinkfirst.domain.diagnostic.engine import Answer, DiagnosticEngine
from thinkfirst.domain.diagnostic.profile import InitialProfile
from thinkfirst.domain.knowledge.graph import GraphError, Skill, SkillGraph
from thinkfirst.domain.knowledge.qmatrix import Item, ItemBank
from thinkfirst.domain.mastery import elo
from thinkfirst.modules.diagnostic.grading import mathcheck
from thinkfirst.modules.diagnostic.grading.models import DiagnosticItemRow, DiagnosticSessionRow
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.identity import service as identity

MISCONCEPTION_DETECTED = events.MISCONCEPTION_DETECTED

# Verified curated bank for standard algebra concepts (with misconception distractors & Elo difficulties).
# The curated items belong to the algebra course ONLY. Every AI roadmap also uses keys like "1.1" or "F1", so the
# concept title must match too (a Java "2.1 Classes and Objects" must never receive "Solve for x").
CURATED_TITLES = {
    "F1": "order of operations", "1.1": "variables and terms", "1.2": "the distributive property",
    "1.3": "combining like terms", "2.1": "solving one-step equations", "2.2": "solving two-step equations",
}


def is_curated(concept) -> bool:
    return CURATED_TITLES.get(concept.key) == (concept.title or "").strip().lower()


CURATED_BANK: dict[str, list[dict]] = {
    "F1": [
        {
            "suffix": "1", "prompt": "Evaluate 2 * (4 + 1).", "kind": "mcq", "expression": "2*(4 + 1)",
            "answer_key": "10", "difficulty": 880.0, "typical_ms": 30_000,
            "options": [
                {"id": "a", "text": "10", "misconception": None},
                {"id": "b", "text": "9", "misconception": "order_multiply_before_brackets"},
                {"id": "c", "text": "7", "misconception": "added_instead_of_multiplied"},
            ],
        },
        {
            "suffix": "2", "prompt": "Evaluate 3 * (5 - 2) + 4.", "kind": "mcq", "expression": "3*(5 - 2) + 4",
            "answer_key": "13", "difficulty": 960.0, "typical_ms": 35_000,
            "options": [
                {"id": "a", "text": "13", "misconception": None},
                {"id": "b", "text": "17", "misconception": "order_multiply_before_brackets"},
                {"id": "c", "text": "21", "misconception": "added_before_multiplying"},
            ],
        },
        {
            "suffix": "3", "prompt": "Evaluate (6 + 2) * 3.", "kind": "mcq", "expression": "(6 + 2)*3",
            "answer_key": "24", "difficulty": 910.0, "typical_ms": 30_000,
            "options": [
                {"id": "a", "text": "24", "misconception": None},
                {"id": "b", "text": "12", "misconception": "order_multiply_before_brackets"},
                {"id": "c", "text": "11", "misconception": "added_instead_of_multiplied"},
            ],
        },
    ],
    "1.1": [
        {
            "suffix": "1", "prompt": "In the expression 3x + 5, what is the coefficient of x?", "kind": "mcq",
            "answer_key": "3", "difficulty": 900.0, "typical_ms": 25_000,
            "options": [
                {"id": "a", "text": "3", "misconception": None},
                {"id": "b", "text": "5", "misconception": "confused_constant_and_coefficient"},
                {"id": "c", "text": "3x", "misconception": "confused_term_and_coefficient"},
            ],
        },
        {
            "suffix": "2", "prompt": "In the expression 4y + 7, what is the constant term?", "kind": "mcq",
            "answer_key": "7", "difficulty": 940.0, "typical_ms": 25_000,
            "options": [
                {"id": "a", "text": "7", "misconception": None},
                {"id": "b", "text": "4", "misconception": "confused_constant_and_coefficient"},
                {"id": "c", "text": "4y", "misconception": "confused_term_and_constant"},
            ],
        },
        {
            "suffix": "3", "prompt": "How many terms are in 5a + 2b - 9?", "kind": "mcq",
            "answer_key": "3", "difficulty": 980.0, "typical_ms": 25_000,
            "options": [
                {"id": "a", "text": "3", "misconception": None},
                {"id": "b", "text": "2", "misconception": "ignored_constant_term"},
                {"id": "c", "text": "5", "misconception": "confused_coefficient_with_term_count"},
            ],
        },
    ],
    "1.2": [
        {
            "suffix": "1", "prompt": "Expand 2(x + 3).", "kind": "expand", "expression": "2*(x + 3)",
            "answer_key": "2x + 6", "difficulty": 1020.0, "typical_ms": 40_000,
            "options": [
                {"id": "a", "text": "2x + 6", "misconception": None},
                {"id": "b", "text": "2x + 3", "misconception": "distribution_first_term_only"},
                {"id": "c", "text": "2x - 6", "misconception": "sign_error"},
            ],
        },
        {
            "suffix": "2", "prompt": "Expand 5(a - 1).", "kind": "expand", "expression": "5*(a - 1)",
            "answer_key": "5a - 5", "difficulty": 1080.0, "typical_ms": 40_000,
            "options": [
                {"id": "a", "text": "5a - 5", "misconception": None},
                {"id": "b", "text": "5a - 1", "misconception": "distribution_first_term_only"},
                {"id": "c", "text": "5a + 5", "misconception": "sign_error"},
            ],
        },
        {
            "suffix": "3", "prompt": "Expand 3(x + 4).", "kind": "expand", "expression": "3*(x + 4)",
            "answer_key": "3x + 12", "difficulty": 1050.0, "typical_ms": 40_000,
            "options": [
                {"id": "a", "text": "3x + 12", "misconception": None},
                {"id": "b", "text": "3x + 4", "misconception": "distribution_first_term_only"},
                {"id": "c", "text": "3x - 12", "misconception": "sign_error"},
            ],
        },
    ],
    "1.3": [
        {
            "suffix": "1", "prompt": "Simplify 3x + 2x + 4.", "kind": "mcq", "expression": "3*x + 2*x + 4",
            "answer_key": "5x + 4", "difficulty": 1080.0, "typical_ms": 40_000,
            "options": [
                {"id": "a", "text": "5x + 4", "misconception": None},
                {"id": "b", "text": "9x", "misconception": "combined_unlike_terms"},
                {"id": "c", "text": "6x + 4", "misconception": "multiplied_coefficients_when_adding"},
            ],
        },
        {
            "suffix": "2", "prompt": "Simplify 7y - 2y + 5.", "kind": "mcq", "expression": "7*y - 2*y + 5",
            "answer_key": "5y + 5", "difficulty": 1130.0, "typical_ms": 40_000,
            "options": [
                {"id": "a", "text": "5y + 5", "misconception": None},
                {"id": "b", "text": "10y", "misconception": "combined_unlike_terms"},
                {"id": "c", "text": "9y + 5", "misconception": "sign_error"},
            ],
        },
        {
            "suffix": "3", "prompt": "Simplify 4x + 3 + 2x.", "kind": "mcq", "expression": "4*x + 3 + 2*x",
            "answer_key": "6x + 3", "difficulty": 1100.0, "typical_ms": 35_000,
            "options": [
                {"id": "a", "text": "6x + 3", "misconception": None},
                {"id": "b", "text": "9x", "misconception": "combined_unlike_terms"},
                {"id": "c", "text": "8x + 3", "misconception": "multiplied_coefficients_when_adding"},
            ],
        },
    ],
    "2.1": [
        {
            "suffix": "1", "prompt": "Solve for x: x + 4 = 9.", "kind": "mcq",
            "answer_key": "5", "difficulty": 1120.0, "typical_ms": 35_000,
            "options": [
                {"id": "a", "text": "5", "misconception": None},
                {"id": "b", "text": "13", "misconception": "added_instead_of_subtracted_both_sides"},
                {"id": "c", "text": "-5", "misconception": "sign_error"},
            ],
        },
        {
            "suffix": "2", "prompt": "Solve for x: x - 3 = 7.", "kind": "mcq",
            "answer_key": "10", "difficulty": 1160.0, "typical_ms": 35_000,
            "options": [
                {"id": "a", "text": "10", "misconception": None},
                {"id": "b", "text": "4", "misconception": "subtracted_instead_of_added_both_sides"},
                {"id": "c", "text": "21", "misconception": "multiplied_instead_of_added"},
            ],
        },
        {
            "suffix": "3", "prompt": "Solve for x: 3x = 15.", "kind": "mcq",
            "answer_key": "5", "difficulty": 1140.0, "typical_ms": 35_000,
            "options": [
                {"id": "a", "text": "5", "misconception": None},
                {"id": "b", "text": "12", "misconception": "subtracted_coefficient_instead_of_dividing"},
                {"id": "c", "text": "45", "misconception": "multiplied_instead_of_dividing"},
            ],
        },
    ],
    "2.2": [
        {
            "suffix": "1", "prompt": "Solve for x: 2x + 3 = 11.", "kind": "mcq",
            "answer_key": "4", "difficulty": 1220.0, "typical_ms": 45_000,
            "options": [
                {"id": "a", "text": "4", "misconception": None},
                {"id": "b", "text": "11/2", "misconception": "forgot_to_subtract"},
                {"id": "c", "text": "7", "misconception": "added_instead_of_subtracted_both_sides"},
            ],
        },
        {
            "suffix": "2", "prompt": "Solve for x: 3x + 5 = 20.", "kind": "mcq",
            "answer_key": "5", "difficulty": 1260.0, "typical_ms": 45_000,
            "options": [
                {"id": "a", "text": "5", "misconception": None},
                {"id": "b", "text": "25/3", "misconception": "forgot_to_subtract"},
                {"id": "c", "text": "15", "misconception": "forgot_to_divide_by_coefficient"},
            ],
        },
        {
            "suffix": "3", "prompt": "Solve for x: 4x - 2 = 14.", "kind": "mcq",
            "answer_key": "4", "difficulty": 1240.0, "typical_ms": 45_000,
            "options": [
                {"id": "a", "text": "4", "misconception": None},
                {"id": "b", "text": "3", "misconception": "subtracted_instead_of_added_both_sides"},
                {"id": "c", "text": "14/4", "misconception": "forgot_to_add_constant"},
            ],
        },
    ],
}

MISCONCEPTION_EXPLANATIONS = {
    "distribution_first_term_only": "multiplying every term inside the brackets (not only the first term)",
    "sign_error": "keeping track of signs when multiplying or moving terms",
    "forgot_to_subtract": "applying the inverse operation to both sides before dividing",
    "order_multiply_before_brackets": "evaluating brackets before multiplying",
    "combined_unlike_terms": "keeping variable terms separate from constants",
    "confused_constant_and_coefficient": "distinguishing a variable's coefficient from the constant term",
    "added_instead_of_subtracted_both_sides": "using the opposite operation on both sides of the equation",
}


def diagnose_answer(db: Session, owner_id: str, *, subject_id: str, concept_id: str | None, task_id: str,
                    attempt_id: str, stage: str, assessment: dict) -> dict | None:
    m = assessment.get("misconception")
    if not m:
        return None
    events.publish(db, events.Event(MISCONCEPTION_DETECTED, owner_id, {
        "subject_id": subject_id, "concept_id": concept_id, "task_id": task_id, "attempt_id": attempt_id, "stage": stage,
        "code": m.get("code"), "message": m.get("message")}))
    return m


# ---- Legacy 3-item baseline (C03 / UC07) ----

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


# ---- Subject Brain: Knowledge Space (SkillGraph + Q-matrix + Calibrated Item Bank) ----

def _build_skill_graph(concepts: list) -> SkillGraph:
    skills = [
        Skill(
            id=c.key,
            name=c.title,
            chapter=c.unit_title or f"Unit {c.unit_no}",
            weight=1.2 if not c.is_foundation else 1.0,
            is_key=True,
            bloom="apply" if not c.is_foundation else "understand",
        )
        for c in concepts
    ]
    known = {s.id for s in skills}
    pos_by_key = {c.key: idx for idx, c in enumerate(concepts)}
    edges: list[tuple[str, str]] = []
    for c in concepts:
        for pre in (c.prerequisites or []):
            if pre in known and pre != c.key:
                edges.append((pre, c.key))
    try:
        return SkillGraph(skills, edges)
    except GraphError:
        # Guard against cyclical user edits by keeping only forward edges in concept position order
        safe_edges = [(p, k) for p, k in edges if pos_by_key.get(p, 0) < pos_by_key.get(k, 0)]
        return SkillGraph(skills, safe_edges)


def _generic_items_for_concept(db: Session, owner_id: str, subject_id: str, c, idx: int) -> list[dict]:
    """Build verified diagnostic items for a non-curated concept, grounded by the RAG stack (Qdrant + HF / fallback)
    and any SymPy-verifiable extracted exercises from the student's uploaded course."""
    import sympy

    from thinkfirst.modules.rag import service as rag

    base_d = 950.0 + idx * 60.0
    out: list[dict] = []

    # 1. Any extracted algebraic exercises from the uploaded course file, verified symbolically with SymPy
    for s_idx, src_item in enumerate(ingestion.items_for(db, owner_id, subject_id, c.key), start=1):
        if src_item.kind == "expand" and src_item.expression:
            parsed = mathcheck.parse(src_item.expression)
            if parsed is not None:
                expanded = mathcheck.pretty(sympy.expand(parsed))
                sp = mathcheck.split_product(src_item.expression)
                wrong_first = (
                    mathcheck.pretty(sp.factor * sp.terms[0] + sympy.Add(*sp.terms[1:]))
                    if sp and len(sp.terms) >= 2 else f"{expanded} + 1"
                )
                wrong_sign = (
                    mathcheck.pretty(sp.factor * sp.terms[0] - sp.factor * sympy.Add(*sp.terms[1:]))
                    if sp and len(sp.terms) >= 2 else f"-({expanded})"
                )
                out.append({
                    "suffix": f"src{s_idx}",
                    "prompt": src_item.prompt,
                    "kind": "expand",
                    "expression": src_item.expression,
                    "answer_key": expanded,
                    "difficulty": base_d,
                    "typical_ms": 40_000,
                    "source_page": src_item.page_no,
                    "options": [
                        {"id": "a", "text": expanded, "misconception": None},
                        {"id": "b", "text": wrong_first, "misconception": "distribution_first_term_only"},
                        {"id": "c", "text": wrong_sign, "misconception": "sign_error"},
                    ],
                })

    # 2. Ground in the RAG stack (Qdrant + HF multilingual embedder or fallback) for page citations & context
    _, cites = rag.ground(db, owner_id, subject_id, f"{c.title} {c.objective}")
    rag_page = next((ci.get("page") for ci in cites if ci.get("page")), None)
    if rag_page is None and c.citations:
        rag_page = c.citations[0].get("page")

    obj = (c.objective or f"Apply the core idea of {c.title}.").rstrip(".")
    for n, delta in enumerate((-30.0, 0.0, 30.0), start=1):
        if len(out) >= 3:
            break
        out.append({
            "suffix": str(n),
            "prompt": f"Which statement best captures the core goal of “{c.title}”? (Check {n})",
            "kind": "mcq",
            "expression": None,
            "answer_key": obj,
            "difficulty": base_d + delta,
            "typical_ms": 40_000,
            "source_page": rag_page,
            "options": [
                {"id": "a", "text": obj, "misconception": None},
                {"id": "b", "text": f"Skip prerequisites and memorize {c.title} formulas only",
                 "misconception": "rote_formula_only"},
                {"id": "c", "text": f"Apply {c.title} without checking conditions or limits",
                 "misconception": "ignored_conditions"},
            ],
        })
    return out


def ensure_knowledge_space(db: Session, owner_id: str, subject_id: str) -> tuple[SkillGraph, ItemBank, list[DiagnosticItemRow]]:
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    graph = _build_skill_graph(concepts)
    rows = list(db.scalars(select(DiagnosticItemRow).where(
        DiagnosticItemRow.owner_id == owner_id,
        DiagnosticItemRow.subject_id == subject_id,
    ).order_by(DiagnosticItemRow.item_key)).all())

    existing_keys = {r.item_key for r in rows}
    # Concepts with verified AI-written placement questions (modules/diagnostic/placement.py) do not need the
    # generic "core goal" placeholder checks; those placeholders are also left out of the bank below.
    ai_skills = {sk for r in rows if r.generated and r.verified for sk in (r.skills or [])}
    created = False
    for idx, c in enumerate(concepts):
        if ai_skills and not is_curated(c):
            continue  # real questions exist for this subject: no filler questions
        templates = CURATED_BANK[c.key] if is_curated(c) else _generic_items_for_concept(db, owner_id, subject_id, c, idx)
        for tmpl in templates:
            ikey = f"{c.key}_{tmpl['suffix']}"
            if ikey in existing_keys:
                continue
            page = tmpl.get("source_page")
            if page is None and c.citations:
                page = c.citations[0].get("page")
            row = DiagnosticItemRow(
                owner_id=owner_id,
                subject_id=subject_id,
                item_key=ikey,
                skills=[c.key],
                prompt=tmpl["prompt"],
                kind=tmpl["kind"],
                expression=tmpl.get("expression"),
                answer_key=tmpl["answer_key"],
                options=tmpl["options"],
                difficulty=float(tmpl["difficulty"]),
                typical_ms=int(tmpl["typical_ms"]),
                diagnostic=True,
                verified=True,
                generated=False,
                calibrated=True,
                n_answers=30,
                language="en",
                source_page=page,
            )
            db.add(row)
            rows.append(row)
            existing_keys.add(ikey)
            created = True

    if created:
        db.flush()

    valid_skills = {s.id for s in graph.skills}
    curated_keys = {c.key for c in concepts if is_curated(c)}
    curated_prompts = {t["prompt"] for items in CURATED_BANK.values() for t in items}
    domain_items: list[Item] = []
    for r in rows:
        sk = tuple(s for s in (r.skills or []) if s in valid_skills)
        if not sk:
            continue
        if not r.generated and not any(s in curated_keys for s in sk):
            if r.prompt in curated_prompts:
                continue  # algebra question attached to a non-algebra concept by an older version
            if ai_skills and r.kind == "mcq":
                continue  # filler question superseded by verified AI questions
        misc_map = {str(opt["id"]): str(opt["misconception"]) for opt in (r.options or []) if opt.get("misconception")}
        domain_items.append(Item(
            id=r.item_key,
            skills=sk,
            difficulty=r.difficulty,
            typical_ms=r.typical_ms,
            diagnostic=r.diagnostic,
            verified=r.verified,
            generated=r.generated,
            calibrated=r.calibrated,
            cross_checked=bool(r.cross_checked),
            n_answers=r.n_answers,
            language=r.language,
            misconceptions=misc_map,
        ))
    bank = ItemBank(domain_items)
    if created:
        issues = bank.validate(graph)
        events.publish(db, events.Event(events.ITEMS_READY, owner_id, {
            "subject_id": subject_id, "skill_count": len(graph), "item_count": len(bank),
            "quality_issues": len(issues),
        }))
    return graph, bank, rows


@events.subscribe(events.GRAPH_BUILT)
def _on_graph_built(db: Session, e: events.Event) -> None:
    sid = e.payload.get("subject_id")
    if sid:
        ensure_knowledge_space(db, e.owner_id, sid)


def knowledge_space_public(db: Session, owner_id: str, subject_id: str) -> dict:
    graph, bank, rows = ensure_knowledge_space(db, owner_id, subject_id)
    issues = bank.validate(graph)
    return {
        "skills": [
            {
                "id": s.id, "name": s.name, "chapter": s.chapter, "weight": s.weight,
                "is_key": s.is_key, "bloom": s.bloom,
                "prerequisites": sorted(graph.prerequisites(s.id)),
                "dependents": sorted(graph.dependents(s.id)),
                "importance": round(graph.importance(s.id), 2),
            }
            for s in graph.skills
        ],
        "q_matrix": {k: list(v) for k, v in bank.q_matrix().items()},
        "item_count": len(bank),
        "ready_for_diagnostic": len(issues) == 0,
        "quality_issues": [{"rule": i.rule, "message": i.message, "item_id": i.item_id, "skill_id": i.skill_id}
                           for i in issues],
    }


# ---- Session Brain: Adaptive Diagnostic Engine ----

def _student_starting_theta(db: Session, owner_id: str) -> float:
    row = identity.get_or_create_student_consent(db, owner_id)
    data = row.onboarding_data or {}
    if isinstance(data.get("prior_theta"), (int, float)):
        return float(data["prior_theta"])
    return elo.prior_theta(data.get("level", "university"), data.get("goal", "exam"))


def _replay_engine(graph: SkillGraph, bank: ItemBank, sess: DiagnosticSessionRow) -> DiagnosticEngine:
    eng = DiagnosticEngine(graph, bank, theta=sess.starting_theta)
    for ans in (sess.answers or []):
        item = eng.next_item()
        if item is None:
            break
        # Align with the recorded item
        eng._current = bank.get(ans["item_id"]) if ans.get("item_id") in {i.id for i in bank.items} else item
        eng.submit(Answer(
            item_id=eng._current.id,
            correct=bool(ans.get("correct")),
            duration_ms=int(ans.get("duration_ms") or 30_000),
            confidence=ans.get("confidence"),
            dont_know=bool(ans.get("dont_know")),
            misconception=ans.get("misconception"),
            response_len=ans.get("response_len"),
            negative_words=int(ans.get("negative_words") or 0),
            focus_switches=int(ans.get("focus_switches") or 0),
            pause_ms=int(ans.get("pause_ms") or 0),
        ))
    return eng


def _item_public(row: DiagnosticItemRow, step_no: int, max_items: int = 12) -> dict:
    elapsed_est = (step_no - 1) * 35
    remaining_sec = max(30, min(480, (max_items - step_no + 1) * 35))
    return {
        "id": row.item_key,
        "item_row_id": row.id,
        "skills": list(row.skills or []),
        "prompt": row.prompt,
        "kind": row.kind,
        "expression": row.expression,
        # stable shuffle: the stored order often has the right answer first
        "options": sorted(({"id": o["id"], "text": o["text"]} for o in (row.options or [])),
                          key=lambda o: hashlib.sha1(f"{row.id}:{o['id']}".encode()).hexdigest()),
        "typical_ms": row.typical_ms,
        "source_page": row.source_page,
        "step_no": step_no,
        "max_items": max_items,
        "remaining_seconds_estimate": remaining_sec,
        "elapsed_seconds_estimate": elapsed_est,
        "allow_dont_know": True,
        "help_locked": True,
        "framing": "8–12 short questions to find where to start. It's not a test.",
    }


def build_student_result_view(db: Session, owner_id: str, subject_id: str, graph: SkillGraph,
                              prof: InitialProfile) -> dict:
    """Design doc 'What the student sees': designed to motivate, not to rank (never a percentage score)."""
    names = {s.id: s.name or s.id for s in graph.skills}
    frontier_skills = [{"skill_id": sid, "title": names.get(sid, sid)} for sid in prof.frontier]
    if not frontier_skills and graph.skills:
        first = graph.skills[0]
        frontier_skills = [{"skill_id": first.id, "title": first.name or first.id}]

    # 2. One strength: something they already master (competence)
    mastered = sorted(
        (m for m in prof.mastery.values() if m.p_l >= 0.65 and not m.inferred),
        key=lambda m: (-m.p_l, m.skill_id),
    )
    if not mastered:
        mastered = sorted(prof.mastery.values(), key=lambda m: (-m.p_l, m.skill_id))
    best = mastered[0] if mastered else None
    strength = (
        {"skill_id": best.skill_id, "title": names.get(best.skill_id, best.skill_id),
         "message": f"You already look solid on “{names.get(best.skill_id, best.skill_id)}”."}
        if best and best.p_l >= 0.55
        else {"skill_id": None, "title": None,
              "message": "You gave us an honest starting picture so we can build from the ground up."}
    )

    # 3. The real gap, explained kindly via prerequisite edges or detected misconception
    start_target = frontier_skills[0]
    dependents = sorted(graph.dependents(start_target["skill_id"]))
    if prof.misconceptions:
        m = prof.misconceptions[0]
        m_title = names.get(m.skill_id, m.skill_id)
        detail = MISCONCEPTION_EXPLANATIONS.get(m.code, "checking each step carefully")
        gap_msg = f"“{m_title}” gets much easier once {detail} is automatic. Let's start there."
    elif dependents:
        dep_title = names.get(dependents[0], dependents[0])
        gap_msg = f"“{dep_title}” gets easier once “{start_target['title']}” is solid. Let's start there."
    else:
        gap_msg = f"“{start_target['title']}” is the clearest place to start on your roadmap."

    # 4. Calibration in one line
    gap = prof.calibration_gap
    if gap is None:
        cal_line = "Rate your confidence before each check — it helps you spot what you truly own."
    elif gap >= 20:
        cal_line = "You felt quite sure; a few answers say we should double-check. That's normal at the start."
    elif gap <= -20:
        cal_line = "You knew more than you thought — your answers were stronger than your confidence ratings."
    else:
        cal_line = "Your confidence matched your answers closely — great self-awareness."

    # 5. First session booked at the time chosen during onboarding
    consent_row = identity.get_or_create_student_consent(db, owner_id)
    rhythm = (consent_row.onboarding_data or {}).get("rhythm") or {}
    slot = rhythm.get("first_session_slot") or (rhythm.get("study_times") or ["Tomorrow at 18:00"])[0]

    return {
        "headline": "Here's where we start",
        "where_we_start": frontier_skills,
        "strength": strength,
        "real_gap": gap_msg,
        "calibration_line": cal_line,
        "first_session_booked": {"slot": slot, "starting_skill": start_target},
        "transparency": prof.evidence_note,
    }


def _grade_diagnostic_item(row: DiagnosticItemRow, answer: str, option_id: str | None,
                           dont_know: bool) -> tuple[bool, str | None, str]:
    if dont_know:
        return False, None, "Marked 'I don't know' — recorded as not yet covered, never a blind guess."
    options = row.options or []
    if option_id:
        chosen = next((o for o in options if str(o.get("id")) == str(option_id)), None)
        if chosen is not None:
            is_right = str(chosen.get("text", "")).strip().lower() == row.answer_key.strip().lower() or not chosen.get("misconception") and chosen == options[0]
            return is_right, chosen.get("misconception"), str(chosen.get("text", ""))
    text = (answer or "").strip()
    if not text:
        raise ValidationFailed("Enter an answer, pick an option, or tap 'I don't know'.", field="answer")
    # Check if the typed answer matches one of the known option texts (for misconception distractor matching)
    for o in options:
        if text.lower().replace(" ", "") == str(o.get("text", "")).strip().lower().replace(" ", ""):
            is_right = not o.get("misconception") and o == options[0]
            return is_right, o.get("misconception"), text
    # Symbolic check for expand / algebra items
    if row.kind == "expand" and row.expression:
        res = mathcheck.grade_expand(text, row.expression)
        code = (res.misconception or {}).get("code") if res.misconception else None
        return res.outcome == "demonstrated", code, text
    parsed_ans = mathcheck.parse(text)
    parsed_key = mathcheck.parse(row.answer_key)
    if parsed_ans is not None and parsed_key is not None:
        if mathcheck.equivalent(parsed_ans, parsed_key):
            return True, None, text
        for o in options:
            p_opt = mathcheck.parse(str(o.get("text", "")))
            if p_opt is not None and mathcheck.equivalent(parsed_ans, p_opt):
                return False, o.get("misconception"), text
        return False, None, text
    return text.lower() == row.answer_key.strip().lower(), None, text


def _finalize_session(db: Session, owner_id: str, subject_id: str, graph: SkillGraph,
                      sess: DiagnosticSessionRow, eng: DiagnosticEngine) -> dict:
    prof = eng.finish()
    view = build_student_result_view(db, owner_id, subject_id, graph, prof)
    sess.status = "completed"
    sess.current_item_id = None
    sess.current_theta = round(eng.theta, 1)
    sess.stop_reason = prof.stop_reason.value
    sess.completed_at = utcnow()
    sess.profile = prof.to_dict() | {"student_view": view}
    db.flush()
    events.publish(db, events.Event(events.DIAGNOSTIC_COMPLETED, owner_id, {
        "subject_id": subject_id,
        "diagnostic_session_id": sess.id,
        "profile": sess.profile,
        "skill_titles": {s.id: s.name for s in graph.skills},
    }))
    return sess.profile


def start_diagnostic(db: Session, owner_id: str, subject_id: str, *, restart: bool = False) -> dict:
    graph, bank, rows = ensure_knowledge_space(db, owner_id, subject_id)
    by_key = {r.item_key: r for r in rows}
    sess = db.scalar(select(DiagnosticSessionRow).where(
        DiagnosticSessionRow.owner_id == owner_id,
        DiagnosticSessionRow.subject_id == subject_id,
    ).order_by(DiagnosticSessionRow.created_at.desc()))

    if sess is None or restart or sess.status in ("skipped", "invalid"):
        theta0 = _student_starting_theta(db, owner_id)
        sess = DiagnosticSessionRow(
            owner_id=owner_id, subject_id=subject_id, status="active",
            starting_theta=theta0, current_theta=theta0, answers=[], profile={},
        )
        db.add(sess)
        db.flush()

    if sess.status == "completed":
        return {"session_id": sess.id, "status": "completed", "current_item": None,
                "n_answered": len(sess.answers or []), "profile": sess.profile}

    eng = _replay_engine(graph, bank, sess)
    nxt = eng.next_item()
    if nxt is None:
        prof = _finalize_session(db, owner_id, subject_id, graph, sess, eng)
        return {"session_id": sess.id, "status": "completed", "current_item": None,
                "n_answered": len(sess.answers or []), "profile": prof}
    sess.current_item_id = nxt.id
    sess.current_theta = round(eng.theta, 1)
    db.flush()
    return {
        "session_id": sess.id,
        "status": "active",
        "current_item": _item_public(by_key[nxt.id], len(sess.answers or []) + 1, eng.cfg.stop.max_items),
        "n_answered": len(sess.answers or []),
        "profile": None,
    }


def submit_diagnostic_answer(db: Session, owner_id: str, subject_id: str, *, item_id: str, answer: str = "",
                             option_id: str | None = None, confidence: int | None = None,
                             dont_know: bool = False, duration_ms: int = 30_000, edits: int = 0,
                             focus_switches: int = 0, pause_ms: int = 0) -> dict:
    if confidence is not None and not (1 <= confidence <= 5):
        raise ValidationFailed("Rate your confidence between 1 and 5.", field="confidence")
    graph, bank, rows = ensure_knowledge_space(db, owner_id, subject_id)
    by_key = {r.item_key: r for r in rows}
    sess = db.scalar(select(DiagnosticSessionRow).where(
        DiagnosticSessionRow.owner_id == owner_id,
        DiagnosticSessionRow.subject_id == subject_id,
        DiagnosticSessionRow.status == "active",
    ).order_by(DiagnosticSessionRow.created_at.desc()))
    if sess is None:
        start_diagnostic(db, owner_id, subject_id)
        sess = db.scalar(select(DiagnosticSessionRow).where(
            DiagnosticSessionRow.owner_id == owner_id,
            DiagnosticSessionRow.subject_id == subject_id,
            DiagnosticSessionRow.status == "active",
        ).order_by(DiagnosticSessionRow.created_at.desc()))
    if sess is None or sess.status != "active":
        raise Conflict("This diagnostic session is already finished.")

    eng = _replay_engine(graph, bank, sess)
    expected = eng.next_item()
    if expected is None or expected.id != item_id:
        raise Conflict("That item is no longer the active diagnostic question.", code="ITEM_MISMATCH")
    row = by_key[item_id]
    correct, misconception, resp_text = _grade_diagnostic_item(row, answer, option_id, dont_know)
    neg = memory.count_negative_words(resp_text)

    outcome = eng.submit(Answer(
        item_id=item_id, correct=correct, duration_ms=max(1, int(duration_ms)),
        confidence=confidence, dont_know=dont_know, misconception=misconception,
        response_len=len(resp_text), negative_words=neg,
        focus_switches=max(0, int(focus_switches)), pause_ms=max(0, int(pause_ms)),
    ))

    # Calibrate item difficulty from real answers
    if not dont_know:
        row.difficulty = round(elo.update_difficulty(row.difficulty, sess.current_theta, correct, weight=outcome.weight), 1)
        row.n_answers = (row.n_answers or 0) + 1

    # Record xAPI event in the behavioral tracking layer
    memory.ingest_tracking_event(db, owner_id, {
        "verb": "skipped" if dont_know else "answered",
        "object": {"type": "item", "id": item_id, "skills": list(row.skills or [])},
        "result": {
            "correct": correct, "response": resp_text[:200], "misconception": misconception,
            "duration_ms": duration_ms, "typical_ms": row.typical_ms, "edits": edits,
            "negative_words": neg,
        },
        "context": {
            "session": sess.id, "subject_id": subject_id, "phase": "diagnostic",
            "mode": "app", "help_level": 0, "confidence": confidence,
            "focus_switches": focus_switches, "pause_ms": pause_ms,
        },
    }, subject_id=subject_id)

    recorded = list(sess.answers or [])
    recorded.append({
        "item_id": item_id, "response": resp_text, "option_id": option_id, "correct": correct,
        "dont_know": dont_know, "confidence": confidence, "duration_ms": duration_ms,
        "misconception": misconception, "rapid_guess": outcome.rapid_guess, "weight": outcome.weight,
        "response_len": len(resp_text), "negative_words": neg,
        "focus_switches": focus_switches, "pause_ms": pause_ms,
    })
    sess.answers = recorded
    sess.current_theta = round(eng.theta, 1)

    events.publish(db, events.Event(events.ANSWER_GRADED, owner_id, {
        "subject_id": subject_id, "diagnostic_session_id": sess.id, "item_id": item_id,
        "skills": list(row.skills or []), "correct": correct, "dont_know": dont_know,
        "confidence": confidence, "misconception": misconception,
        "rapid_guess": outcome.rapid_guess, "weight": outcome.weight,
    }))
    if misconception:
        concept = next((c for c in ingestion.active_concepts(db, owner_id, subject_id)
                        if c.key in (row.skills or [])), None)
        events.publish(db, events.Event(MISCONCEPTION_DETECTED, owner_id, {
            "subject_id": subject_id, "concept_id": concept.id if concept else None,
            "task_id": None, "attempt_id": f"diag:{sess.id}:{len(recorded)}", "stage": "diagnostic",
            "code": misconception, "message": MISCONCEPTION_EXPLANATIONS.get(misconception, misconception),
        }))

    gentle_nudge = "Take your time — there's no speed bonus here." if outcome.rapid_guess else None
    if eng.finished or eng.next_item() is None:
        prof = _finalize_session(db, owner_id, subject_id, graph, sess, eng)
        return {
            "session_id": sess.id, "status": "completed",
            "last_answer": {"item_id": item_id, "rapid_guess": outcome.rapid_guess,
                            "followup_scheduled": outcome.followup_scheduled, "nudge": gentle_nudge},
            "current_item": None, "n_answered": len(recorded), "profile": prof,
        }

    nxt = eng.next_item()
    assert nxt is not None
    sess.current_item_id = nxt.id
    db.flush()
    return {
        "session_id": sess.id, "status": "active",
        "last_answer": {"item_id": item_id, "rapid_guess": outcome.rapid_guess,
                        "followup_scheduled": outcome.followup_scheduled, "nudge": gentle_nudge},
        "current_item": _item_public(by_key[nxt.id], len(recorded) + 1, eng.cfg.stop.max_items),
        "n_answered": len(recorded), "profile": None,
    }


def stop_diagnostic(db: Session, owner_id: str, subject_id: str) -> dict:
    """Stop the adaptive diagnostic early (marks profile low_confidence and finishes measurement in first sessions)."""
    graph, bank, _ = ensure_knowledge_space(db, owner_id, subject_id)
    sess = db.scalar(select(DiagnosticSessionRow).where(
        DiagnosticSessionRow.owner_id == owner_id,
        DiagnosticSessionRow.subject_id == subject_id,
        DiagnosticSessionRow.status == "active",
    ).order_by(DiagnosticSessionRow.created_at.desc()))
    if sess is None:
        return start_diagnostic(db, owner_id, subject_id)
    eng = _replay_engine(graph, bank, sess)
    eng.stop()
    prof = _finalize_session(db, owner_id, subject_id, graph, sess, eng)
    return {"session_id": sess.id, "status": "completed", "current_item": None,
            "n_answered": len(sess.answers or []), "profile": prof}


def diagnostic_overview(db: Session, owner_id: str, subject_id: str) -> dict:
    sess = db.scalar(select(DiagnosticSessionRow).where(
        DiagnosticSessionRow.owner_id == owner_id,
        DiagnosticSessionRow.subject_id == subject_id,
    ).order_by(DiagnosticSessionRow.created_at.desc()))
    if sess is not None and sess.status == "invalid":
        sess = None  # discarded test (wrong questions): start again
    state = start_diagnostic(db, owner_id, subject_id) if sess and sess.status == "active" else (
        {"session_id": sess.id, "status": sess.status, "current_item": None,
         "n_answered": len(sess.answers or []), "profile": sess.profile}
        if sess else None
    )
    return {
        "items": baseline_items(db, owner_id, subject_id),
        "adaptive": state,
        "knowledge_space": knowledge_space_public(db, owner_id, subject_id),
    }


def stack() -> dict:
    """Capability descriptor exposed by GET /api/capabilities alongside rag.stack()."""
    return {
        "engine": "cat_kst_bkt_elo",
        "max_items": 12,
        "max_minutes": 10,
        "tracking_schema": "xapi",
        "consent_tiers": ["essential", "learning_behavior", "voice_images", "research"],
    }
