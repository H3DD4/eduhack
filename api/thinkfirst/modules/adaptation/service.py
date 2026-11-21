"""Moteur d'adaptation — decides what comes next for this student, from the profile (evidence) and memory.

Transparent rules (every recommendation carries a human-readable reason; no hidden scores, no traits):
- next action: unfinished session > next level without independent application > roadmap review > add subject;
- suggested level: if memory shows a recurring misconception on a level that lists an optional foundation,
  suggest that foundation as a side quest (never a gate);
- review interval: adaptive hypothesis (1 / 2 / 4 days) based on this session's evidence, always adjustable;
- in-session nudge: remind the student of their own recent misconception on this concept.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.data.memory import service as memory
from thinkfirst.modules.adaptation import engine
from thinkfirst.modules.adaptation.models import BanditStat
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.workspaces import service as workspaces

MISCONCEPTION_HINTS = {
    "distribution_first_term_only": "Last time the factor multiplied only the first term. Check every term inside the brackets.",
    "sign_error": "Last time a sign flipped. Check the sign of each product.",
}


def suggest_concept(db: Session, owner_id: str, subject_id: str) -> dict | None:
    """First choice of the learner engine (remediate > review > diagnostic side quest > frontier > continue)."""
    concepts = {c.id: c for c in ingestion.active_concepts(db, owner_id, subject_id)}
    if not concepts:
        return None
    rec = recommend(db, owner_id, subject_id)
    for choice in rec["next_concepts"]:
        c = concepts.get(choice["concept_id"])
        if c is None:
            continue
        kind = "side_quest" if choice["kind"] == "diagnostic_check" else choice["kind"]
        return {"concept_id": c.id, "title": c.title, "kind": kind, "reason": f"{c.title}: {choice['reason']}",
                "alternatives": [{"concept_id": x["concept_id"], "kind": x["kind"], "title": concepts[x["concept_id"]].title,
                                  "reason": x["reason"]} for x in rec["next_concepts"][1:] if x["concept_id"] in concepts]}
    return None


def next_action(db: Session, owner_id: str, unfinished: dict | None) -> dict:
    if unfinished is not None:
        return {"kind": "resume", **unfinished,
                "reason": f"You {'paused' if unfinished['status'] == 'paused' else 'left'} “{unfinished['concept_title']}” at the {unfinished['stage']} step."}
    subjects = workspaces.list_subjects(db, owner_id)
    for sub in [s for s in subjects if s.status == "ready"]:
        sug = suggest_concept(db, owner_id, sub.id)
        if sug:
            return {"kind": "start", "subject_id": sub.id, "concept_id": sug["concept_id"], "concept_title": sug["title"],
                    "reason": sug["reason"] + f" ({sub.name})"}
    pending = [s for s in subjects if s.status != "ready"]
    if pending:
        return {"kind": "setup", "subject_id": pending[0].id, "reason": f"“{pending[0].name}” is waiting for you to review its roadmap."}
    return {"kind": "add_subject", "reason": "Add a course or type a topic to get a roadmap."}


def review_interval(evidence_labels: set[str], today: date | None = None) -> tuple[date, str]:
    today = today or date.today()
    if "applied_independently" in evidence_labels:
        days, why = 4, "you applied it without help, so a slightly longer gap is a fair test"
    elif "explained" in evidence_labels:
        days, why = 2, "you explained it but have not applied it on your own yet"
    else:
        days, why = 1, "this concept is still new, so an early check helps"
    return today + timedelta(days=days), f"Suggested in {days} day(s): {why}. A scheduling hypothesis — change it freely."


def session_nudge(db: Session, owner_id: str, subject_id: str, concept_id: str) -> str | None:
    for e in memory.history(db, owner_id, subject_id, concept_id, limit=20):
        if e.kind == "misconception":
            return MISCONCEPTION_HINTS.get(e.detail.get("code"), f"From your history: {e.summary}")
    return None


# ======================================================================================================
# Learner engine integration (modules/adaptation/engine is pure JSON in/out). Below we only BUILD engine input
# from the app's data and STORE its output; the learning logic itself lives in the engine.
# ======================================================================================================

ACTION_LABELS = {
    "targeted_hint": "a targeted hint", "worked_example": "a worked example with different numbers",
    "prerequisite_refresher": "a quick refresher on the prerequisite", "guided_retry": "a guided retry, one step at a time",
    "refutation": "a short explanation of why the tempting answer is wrong",
}
TAXONOMY = {  # closed misconception lists per concept family ("bug library"); "other" catches unclassified errors
    "distribut": [("distribution_first_term_only", "Multiplies only the first term inside the brackets"),
                  ("sign_error", "Sign error when distributing")],
}


def concept_specs(db: Session, owner_id: str, subject_id: str) -> list[dict]:
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    by_key = {c.key: c for c in concepts}
    out = []
    for c in concepts:
        foundation = next((by_key[k].id for k in c.prerequisites if k in by_key and by_key[k].is_foundation), None)
        mis = [{"id": mid, "label": label, "prerequisite_id": foundation if mid == "distribution_first_term_only" else None}
               for fam, items in TAXONOMY.items() if fam in c.title.lower() for mid, label in items]
        mis.append({"id": "other", "label": "Other error (AI-detected, not yet classified)"})
        out.append({"concept_id": c.id, "prerequisites": [by_key[k].id for k in c.prerequisites if k in by_key],
                    "order": c.position, "is_foundation": c.is_foundation, "misconceptions": mis})
    return out


def learner_state(db: Session, owner_id: str, subject_id: str, as_of: datetime | None = None) -> dict:
    return engine.fold_json({"student_id": owner_id, "concepts": concept_specs(db, owner_id, subject_id),
                             "events": memory.engine_events(db, owner_id, subject_id),
                             "as_of": (as_of or datetime.now(UTC)).isoformat()})


def population_bandit_stats(db: Session) -> dict:
    out: dict[str, dict[str, list[float]]] = {}
    for r in db.scalars(select(BanditStat)).all():
        out.setdefault(r.context_key, {})[r.action] = [r.successes, r.failures]
    return out


def recommend(db: Session, owner_id: str, subject_id: str, focus_concept_id: str | None = None,
              error_class: str | None = None, seed: int | None = None) -> dict:
    return engine.recommend_json({
        "student_id": owner_id, "concepts": concept_specs(db, owner_id, subject_id),
        "events": memory.engine_events(db, owner_id, subject_id), "as_of": datetime.now(UTC).isoformat(),
        "focus_concept_id": focus_concept_id, "error_class": error_class, "seed": seed,
        "bandit_stats": population_bandit_stats(db)})


def recommend_action(db: Session, owner_id: str, *, subject_id: str, concept_id: str, task_id: str,
                     error_class: str | None, key: str) -> dict | None:
    """After a wrong answer: which help to OFFER first (never withheld). Logged with its propensity."""
    rec = recommend(db, owner_id, subject_id, focus_concept_id=concept_id, error_class=error_class)
    a = rec.get("action")
    if not a:
        return None
    memory.log_recommendation(db, owner_id, subject_id=subject_id, concept_id=concept_id, task_id=task_id,
                              action=a["action"], context_key=a["context_key"], propensity=a["propensity"], key=key)
    return {"action": a["action"], "label": ACTION_LABELS[a["action"]], "propensity": a["propensity"],
            "context_key": a["context_key"]}


@events.subscribe(events.ASSESSMENT_ACCEPTED)
def _reward_bandit(db: Session, e: events.Event) -> None:
    """A fresh UNAIDED answer rewards this student's latest pending recommendation on the concept; the reward is
    then added to the shared aggregate (counts only, no student id)."""
    p = e.payload
    if not p.get("is_fresh") or p.get("assistance_level") != "none" or p["outcome"] == "unscored":
        return
    from thinkfirst.data.memory.models import LearningEvent

    rec = db.scalar(select(LearningEvent).where(
        LearningEvent.owner_id == e.owner_id, LearningEvent.concept_id == p.get("concept_id"),
        LearningEvent.kind == "recommendation", LearningEvent.reward.is_(None)).order_by(LearningEvent.created_at.desc()))
    if rec is None or not rec.context_key or not rec.recommended_action:
        return
    reward = {"demonstrated": 1.0, "partial": 0.5}.get(p["outcome"], 0.0)
    rec.reward = reward
    stat = db.scalar(select(BanditStat).where(BanditStat.context_key == rec.context_key,
                                              BanditStat.action == rec.recommended_action))
    if stat is None:
        stat = BanditStat(context_key=rec.context_key, action=rec.recommended_action, successes=0.0, failures=0.0)
        db.add(stat)
    stat.successes += reward
    stat.failures += 1 - reward
    db.flush()


def engine_review_date(db: Session, owner_id: str, subject_id: str, concept_id: str) -> tuple[date, str] | None:
    """Review date from the engine's retention model (memory stability), when it has unaided evidence."""
    st = learner_state(db, owner_id, subject_id)["concepts"].get(concept_id)
    if not st or not st.get("review_due_at"):
        return None
    due = max(datetime.fromisoformat(st["review_due_at"]).date(), date.today() + timedelta(days=1))
    threshold = int(engine.schemas.EngineConfig().review_threshold_R * 100)
    return due, (f"Your estimated recall drops below {threshold}% around then "
                 f"(memory stability about {st['stability_days']:.1f} days). Change it freely.")
