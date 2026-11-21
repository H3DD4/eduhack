"""Placement test for the start wizard ("I already know some of this topic → test my level").

1. Questions: the AI writes 3 multiple-choice questions per roadmap concept (easy / medium / hard). Every wrong
   option is tagged with the misconception that would make a student choose it.
2. Cross-check: a SECOND, independent pass (another provider when one is configured) solves each question without
   seeing the key. Only questions where it lands on the same option are used ("verified"); the rest are discarded.
3. The adaptive diagnostic engine (domain/diagnostic) runs them: easy first, then the most informative question,
   stops once every key concept is classified (5-12 answers). Uncalibrated generated items count half.
4. Level report: level (beginner / intermediate / advanced / expert) + visible metrics, all derived from the
   recorded answers and the engine's mastery estimates (formula shown to the student).

"Start from scratch" skips 1-3: level = beginner, every concept starts at a low prior.
Without an AI service no questions are generated; the diagnostic falls back to its built-in checks (labelled).
"""

from __future__ import annotations

import random
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events, jobs
from thinkfirst.domain.mastery.elo import DIFFICULTY_PRIORS
from thinkfirst.modules.diagnostic.grading.models import DiagnosticItemRow, DiagnosticSessionRow
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.modules.tutor.llm import service as llm
from thinkfirst.platform.workspaces import service as workspaces

JOB = "diagnostic.placement_items"
MAX_CONCEPTS = 12
BATCH = 4
OPTION_MAX = 200  # answer_key column width; longer options are rejected, never truncated (grading compares text)
LEVELS = [(85, "expert", "Expert"), (60, "advanced", "Advanced"), (35, "intermediate", "Intermediate"),
          (0, "beginner", "Beginner")]
LEVEL_DESCRIPTIONS = {
    "beginner": "We start from the foundations, step by step, and explain every term.",
    "intermediate": "You know the basics. We consolidate and spend most time on your gaps.",
    "advanced": "You know most of it. We go fast on what you know and deep on the few gaps.",
    "expert": "You master this topic. Expect compact revision and hard transfer problems.",
}
DIFF_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}
SCRATCH_PRIOR = 0.05


def _curated() -> dict:
    from thinkfirst.modules.diagnostic.service import CURATED_BANK

    return CURATED_BANK


def _ai_available() -> bool:
    return llm.active_provider() != "demo"


def _job_key(subject) -> str:
    return f"placement:{subject.id}:{subject.active_graph_revision_id}"


def _targets(db: Session, owner_id: str, subject_id: str) -> list:
    return [c for c in ingestion.active_concepts(db, owner_id, subject_id) if c.key not in _curated()][:MAX_CONCEPTS]


def start_generation(db: Session, owner_id: str, subject_id: str) -> jobs.Job | None:
    """Idempotent per confirmed roadmap revision. No job when nothing needs generated questions or no AI is set."""
    subject = workspaces.get_subject(db, owner_id, subject_id)
    if subject.status != "ready" or not _targets(db, owner_id, subject_id) or not _ai_available():
        return None
    return jobs.enqueue(db, JOB, owner_id, {"subject_id": subject_id}, idempotency_key=_job_key(subject))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60] or "other"


def _clean(items: list, keys: set[str]) -> list[dict]:
    out = []
    for it in items or []:
        key, diff = str(it.get("concept_key", "")), it.get("difficulty")
        q, ok = str(it.get("question", "")).strip(), str(it.get("correct", "")).strip()
        dis = [(str(d.get("text", "")).strip(), _slug(str(d.get("misconception", "")))) for d in it.get("distractors") or []]
        texts = [ok] + [t for t, _ in dis]
        if (key not in keys or diff not in DIFF_WEIGHT or not q or len(dis) != 3 or not all(texts)
                or max(len(t) for t in texts) > OPTION_MAX or len({t.lower() for t in texts}) != 4):
            continue
        out.append({"concept_key": key, "difficulty": diff, "question": q[:1200], "correct": ok, "distractors": dis})
    return out


def _shuffled(item: dict) -> list[dict]:
    opts = [{"text": item["correct"], "misconception": None}] + [{"text": t, "misconception": m} for t, m in item["distractors"]]
    random.Random(item["question"]).shuffle(opts)  # stable per question
    return [{"id": "abcd"[i], **o} for i, o in enumerate(opts)]


def _other_provider(first: str) -> str | None:
    return next((p for p in llm.provider_chain() if p not in (first, "demo")), None)


def _cross_check(db: Session, owner_id: str, items: list[dict], generator: str) -> dict[int, bool]:
    questions = [{"qid": str(i), "question": it["question"], "options": [{"id": o["id"], "text": o["text"]} for o in it["options"]]}
                 for i, it in enumerate(items)]
    other = _other_provider(generator)
    res = llm.run(db, "cross_check_items", {"questions": questions}, owner_id=owner_id, purpose="placement_check",
                  provider=other) if other else None
    if res is None or res.status != "ok":
        res = llm.run(db, "cross_check_items", {"questions": questions}, owner_id=owner_id, purpose="placement_check")
    picked = {str(a.get("qid")): str(a.get("option_id", "")).strip().lower() for a in (res.output or {}).get("answers", [])} \
        if res.status == "ok" else {}
    return {i: picked.get(str(i)) == next(o["id"] for o in it["options"] if o["misconception"] is None)
            for i, it in enumerate(items)}


def _grounding(db: Session, owner_id: str, subject, batch: list) -> str:
    parts = []
    for c in batch:
        ex = ingestion.concept_excerpt(db, owner_id, c)
        if ex and not ex.get("tombstone") and ex.get("text"):
            parts.append(f"[{c.key} {c.title}] {ex['text'][:1500]}")
    if parts:
        return "\n\n".join(parts)
    from thinkfirst.modules.rag import service as rag

    g = rag.hybrid(db, owner_id, subject.id, " ".join(c.title for c in batch), fetch_query=subject.name)
    return g["text"][:4000]


@jobs.job_handler(JOB)
def _placement_job(db: Session, job: jobs.Job) -> dict:
    owner, sid = job.owner_id, job.payload["subject_id"]
    subject = workspaces.get_subject(db, owner, sid)
    targets = _targets(db, owner, sid)
    existing = {r.item_key for r in db.scalars(select(DiagnosticItemRow).where(
        DiagnosticItemRow.owner_id == owner, DiagnosticItemRow.subject_id == sid)).all()}
    made = verified = 0
    for start in range(0, len(targets), BATCH):
        batch = targets[start:start + BATCH]
        by_key = {c.key: c for c in batch}
        res = llm.run(db, "generate_placement_items", {
            "concepts": [{"key": c.key, "title": c.title, "objective": c.objective} for c in batch],
            "course_excerpt": _grounding(db, owner, subject, batch)}, owner_id=owner, purpose="placement_items")
        if res.status != "ok" or not res.output:
            continue
        items = [dict(it, options=_shuffled(it)) for it in _clean(res.output.get("items"), set(by_key))]
        agree = _cross_check(db, owner, items, res.provider)
        counter: dict[str, int] = {}
        for i, it in enumerate(items):
            c = by_key[it["concept_key"]]
            counter[c.key] = counter.get(c.key, 0) + 1
            ikey = f"{c.key}_q{counter[c.key]}"
            if ikey in existing:
                continue
            ok = agree.get(i, False)
            made += 1
            verified += ok
            db.add(DiagnosticItemRow(
                owner_id=owner, subject_id=sid, item_key=ikey, skills=[c.key], prompt=it["question"], kind="mcq",
                expression=None, answer_key=it["correct"], options=it["options"],
                difficulty=DIFFICULTY_PRIORS[it["difficulty"]] + 10.0 * c.position, typical_ms=40_000,
                diagnostic=True, verified=ok, generated=True, calibrated=False, cross_checked=ok, n_answers=0,
                language="en", source_page=(c.citations[0].get("page") if c.citations else None) or None,
                difficulty_label=it["difficulty"]))
            existing.add(ikey)
    db.flush()
    if made == 0:
        raise jobs.JobError("NO_ITEMS_GENERATED")
    return {"items": made, "verified": verified}


# ------------------------------------------------------------------ status

def _job(db: Session, subject) -> jobs.Job | None:
    return db.scalar(select(jobs.Job).where(jobs.Job.idempotency_key == _job_key(subject)))


def latest_session(db: Session, owner_id: str, subject_id: str) -> DiagnosticSessionRow | None:
    return db.scalar(select(DiagnosticSessionRow).where(
        DiagnosticSessionRow.owner_id == owner_id, DiagnosticSessionRow.subject_id == subject_id)
        .order_by(DiagnosticSessionRow.created_at.desc()))


def status(db: Session, owner_id: str, subject_id: str) -> dict:
    """not_needed | preparing | ready | in_progress | completed | skipped | failed (+ counts for the UI)."""
    subject = workspaces.get_subject(db, owner_id, subject_id)
    sess = latest_session(db, owner_id, subject_id)
    base = {"generated_items": 0, "verified_items": 0, "answered": len(sess.answers or []) if sess else 0,
            "job_id": None, "uses_ai_questions": False}
    if subject.prior_knowledge != "some":
        return {**base, "state": "not_needed"}
    rows = db.scalars(select(DiagnosticItemRow).where(DiagnosticItemRow.owner_id == owner_id,
                                                      DiagnosticItemRow.subject_id == subject_id,
                                                      DiagnosticItemRow.generated.is_(True))).all()
    base |= {"generated_items": len(rows), "verified_items": sum(1 for r in rows if r.verified),
             "uses_ai_questions": any(r.verified for r in rows)}
    if sess is not None and sess.status in ("completed", "active", "skipped"):
        return {**base, "state": {"active": "in_progress"}.get(sess.status, sess.status)}
    if subject.status != "ready":
        return {**base, "state": "preparing"}
    job = _job(db, subject)
    if job is not None:
        base["job_id"] = job.id
        if job.status in (jobs.QUEUED, jobs.RUNNING):
            return {**base, "state": "preparing"}
        if job.status == jobs.FAILED and not base["verified_items"]:
            return {**base, "state": "failed"}
    return {**base, "state": "ready"}


# ------------------------------------------------------------------ level + metrics

def _level_for(score: int) -> tuple[str, str]:
    return next((key, label) for th, key, label in LEVELS if score >= th)


def _status_of(m: dict | None) -> str:
    s = (m or {}).get("status")
    return {"mastered": "known", "uncertain": "partly"}.get(s, "to_learn")


def report(db: Session, owner_id: str, subject_id: str) -> dict:
    """The learner's starting level on this subject and the metrics behind it (None-safe for every path)."""
    subject = workspaces.get_subject(db, owner_id, subject_id)
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    core = [c for c in concepts if not c.is_foundation] or concepts
    sess = latest_session(db, owner_id, subject_id)
    tested = sess is not None and sess.status == "completed" and bool(sess.answers)
    if not tested:
        if subject.prior_knowledge == "some" and not (sess and sess.status == "skipped"):
            return {"available": False, "basis": "pending", "level": None}
        chosen = subject.prior_knowledge is not None
        return {
            "available": True, "basis": "from_scratch" if chosen else "default", "level": "beginner",
            "level_label": "Beginner", "score": 0, "description": LEVEL_DESCRIPTIONS["beginner"],
            "explanation": ("You chose to start from scratch, so every concept starts as new. Your level rises as you "
                            "practise without help." if chosen else
                            "No level test taken for this subject yet, so it is treated as new. Take the level test any time."),
            "concepts": [{"concept_id": c.id, "key": c.key, "title": c.title, "unit_no": c.unit_no,
                          "is_foundation": c.is_foundation, "status": "to_learn", "evidence": "not tested"} for c in concepts],
            "by_unit": _by_unit(concepts, {c.key: "to_learn" for c in concepts}), "metrics": None,
        }
    prof = sess.profile or {}
    mastery = prof.get("mastery") or {}
    rows = {r.item_key: r for r in db.scalars(select(DiagnosticItemRow).where(
        DiagnosticItemRow.owner_id == owner_id, DiagnosticItemRow.subject_id == subject_id)).all()}
    answers = sess.answers or []

    def label_of(row) -> str:
        if row is None:
            return "medium"
        if row.difficulty_label:
            return row.difficulty_label
        return "easy" if row.difficulty < 1000 else "medium" if row.difficulty < 1200 else "hard"

    by_diff = {d: {"asked": 0, "correct": 0} for d in DIFF_WEIGHT}
    w_sum = w_ok = 0.0
    for a in answers:
        d = label_of(rows.get(a["item_id"]))
        by_diff[d]["asked"] += 1
        by_diff[d]["correct"] += int(bool(a.get("correct")))
        w_sum += DIFF_WEIGHT[d]
        w_ok += DIFF_WEIGHT[d] * bool(a.get("correct"))
    n = len(answers)
    n_ok = sum(1 for a in answers if a.get("correct"))
    mean_p = sum(float((mastery.get(c.key) or {}).get("p_l", 0.1)) for c in core) / max(1, len(core))
    w_acc = w_ok / w_sum if w_sum else 0.0
    score = round(100 * (0.7 * mean_p + 0.3 * w_acc))
    level, label = _level_for(score)
    statuses = {c.key: _status_of(mastery.get(c.key)) for c in concepts}
    titles = {c.key: c.title for c in concepts}
    answered_on = {}
    for a in answers:
        for sk in (rows[a["item_id"]].skills if a["item_id"] in rows else []):
            answered_on[sk] = answered_on.get(sk, 0) + 1
    view = prof.get("student_view") or {}
    durations = [int(a.get("duration_ms") or 0) for a in answers if not a.get("dont_know")]
    misc = []
    for m in prof.get("misconceptions") or []:
        code = m.get("code")
        if code and code not in {x["code"] for x in misc}:
            misc.append({"code": code, "label": code.replace("_", " ").capitalize(), "concept": titles.get(m.get("skill_id"), "")})
    return {
        "available": True, "basis": "placement_test", "level": level, "level_label": label, "score": score,
        "description": LEVEL_DESCRIPTIONS[level],
        "explanation": (f"Level score {score}/100 = 70% estimated mastery across {len(core)} concepts "
                        f"({round(100 * mean_p)}%) + 30% weighted accuracy ({round(100 * w_acc)}%; medium questions count "
                        "×1.5, hard ×2). Beginner < 35 ≤ Intermediate < 60 ≤ Advanced < 85 ≤ Expert."),
        "concepts": [{"concept_id": c.id, "key": c.key, "title": c.title, "unit_no": c.unit_no, "is_foundation": c.is_foundation,
                      "status": statuses[c.key],
                      "evidence": (f"{answered_on[c.key]} answer(s)" if answered_on.get(c.key)
                                   else "inferred from related answers" if (mastery.get(c.key) or {}).get("inferred")
                                   else "not asked")} for c in concepts],
        "by_unit": _by_unit(concepts, statuses),
        "metrics": {
            "answered": n, "correct": n_ok, "dont_know": sum(1 for a in answers if a.get("dont_know")),
            "accuracy": round(100 * n_ok / n) if n else 0, "weighted_accuracy": round(100 * w_acc),
            "estimated_mastery": round(100 * mean_p), "by_difficulty": by_diff,
            "avg_seconds": round(sum(durations) / len(durations) / 1000) if durations else None,
            "rapid_guesses": sum(1 for a in answers if a.get("rapid_guess")),
            "calibration_gap": prof.get("calibration_gap"), "calibration_line": view.get("calibration_line"),
            "misconceptions": misc,
            "strengths": [titles[k] for k, st in statuses.items() if st == "known"][:4],
            "gaps": [titles[k] for k, st in statuses.items() if st == "to_learn"][:4],
            "stop_reason": prof.get("stop_reason"), "low_confidence": bool(prof.get("low_confidence")),
            "needs_retest": bool(prof.get("needs_retest")), "evidence_note": prof.get("evidence_note"),
        },
    }


def _by_unit(concepts: list, statuses: dict[str, str]) -> list[dict]:
    units: dict[int, dict] = {}
    for c in concepts:
        u = units.setdefault(c.unit_no, {"unit_no": c.unit_no, "title": c.unit_title, "known": 0, "partly": 0, "to_learn": 0,
                                         "total": 0})
        u[statuses.get(c.key, "to_learn")] += 1
        u["total"] += 1
    return [units[k] for k in sorted(units)]


def current_level(db: Session, owner_id: str, subject_id: str) -> str | None:
    r = report(db, owner_id, subject_id)
    return r["level"] if r.get("available") else None


def learner_context(db: Session, owner_id: str, subject_id: str) -> dict:
    """What the content generators need: level, goal, known concepts, gap concepts."""
    subject = workspaces.get_subject(db, owner_id, subject_id)
    r = report(db, owner_id, subject_id)
    concepts = r.get("concepts") or []
    return {"level": r.get("level") or "beginner", "goal": subject.goal or "explore",
            "known": [c["title"] for c in concepts if c["status"] == "known"],
            "gaps": [c["title"] for c in concepts if c["status"] == "to_learn" and not c.get("is_foundation")]}


def concept_priors(db: Session, owner_id: str, subject_id: str) -> dict[str, float]:
    """Starting P(known) per concept for the learner engine: from the placement test, or low for 'from scratch'."""
    subject = workspaces.get_subject(db, owner_id, subject_id)
    sess = latest_session(db, owner_id, subject_id)
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    if sess is not None and sess.status == "completed" and sess.answers:
        mastery = (sess.profile or {}).get("mastery") or {}
        return {c.id: min(0.9, max(0.02, float(mastery[c.key]["p_l"]))) for c in concepts if c.key in mastery}
    if subject.prior_knowledge == "none" or (sess is not None and sess.status == "skipped"):
        return {c.id: SCRATCH_PRIOR for c in concepts}
    return {}


@events.subscribe(events.SOURCE_CONFIRMED)
def _on_roadmap_confirmed(db: Session, e: events.Event) -> None:
    """'Test my level' subjects: write + cross-check the placement questions right after the roadmap is confirmed."""
    subject = workspaces.get_subject(db, e.owner_id, e.payload["subject_id"])
    if subject.prior_knowledge == "some":
        start_generation(db, e.owner_id, subject.id)
