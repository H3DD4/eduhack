"""Moteur d'adaptation — decides what comes next for this student, from the profile (evidence) and memory.

Transparent rules (every recommendation carries a human-readable reason; no hidden scores, no traits):
- next action: unfinished session > next level without independent application > roadmap review > add subject;
- suggested level: if memory shows a recurring misconception on a level that lists an optional foundation,
  suggest that foundation as a side quest (never a gate);
- review interval: adaptive hypothesis (1 / 2 / 4 days) based on this session's evidence, always adjustable;
- in-session nudge: remind the student of their own recent misconception on this concept.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core import events
from thinkfirst.data.memory import service as memory
from thinkfirst.data.student_profile import service as profile
from thinkfirst.data.student_profile.models import InitialProfileRow
from thinkfirst.modules.rag.ingestion import service as ingestion
from thinkfirst.platform.identity import service as identity
from thinkfirst.platform.workspaces import service as workspaces

MISCONCEPTION_HINTS = {
    "distribution_first_term_only": "Last time the factor multiplied only the first term. Check every term inside the brackets.",
    "sign_error": "Last time a sign flipped. Check the sign of each product.",
}


def suggest_concept(db: Session, owner_id: str, subject_id: str) -> dict | None:
    concepts = ingestion.active_concepts(db, owner_id, subject_id)
    by_key = {c.key: c for c in concepts}
    sums = profile.concept_summaries(db, owner_id, subject_id)
    for rec in memory.recurring_misconceptions(db, owner_id, subject_id):
        c = next((x for x in concepts if x.id == rec["concept_id"]), None)
        f = next((by_key[k] for k in (c.prerequisites if c else []) if k in by_key and by_key[k].is_foundation), None)
        if f and "applied_independently" not in sums.get(c.id, {}).get("states", []):
            return {"concept_id": f.id, "title": f.title, "kind": "side_quest",
                    "reason": f"The same slip appeared {rec['count']} times on “{c.title}”. An optional refresher on “{f.title}” may help."}
    init_prof = profile.initial_profile_for_subject(db, owner_id, subject_id)
    if init_prof and init_prof.get("frontier"):
        for fkey in init_prof["frontier"]:
            fc = by_key.get(fkey)
            if fc and "applied_independently" not in sums.get(fc.id, {}).get("states", []):
                return {"concept_id": fc.id, "title": fc.title, "kind": "frontier",
                        "reason": f"On your knowledge frontier from the diagnostic ({init_prof['n_items']} answers): prerequisites are ready."}
    nxt = next((c for c in concepts if not c.is_foundation
                and "applied_independently" not in sums.get(c.id, {}).get("states", [])), None)
    if nxt:
        return {"concept_id": nxt.id, "title": nxt.title, "kind": "next_level",
                "reason": "Next level on your roadmap without independent application yet."}
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


@events.subscribe(events.PROFILE_READY)
def _on_profile_ready(db: Session, e: events.Event) -> None:
    """Plan Brain: consume `profile.ready` + onboarding goal/rhythm and publish `plan.updated`."""
    p = e.payload
    subject_id = p["subject_id"]
    concepts = ingestion.active_concepts(db, e.owner_id, subject_id)
    by_key = {c.key: c for c in concepts}
    frontier = p.get("frontier") or []
    consent_row = identity.get_or_create_student_consent(db, e.owner_id)
    onboard = consent_row.onboarding_data or {}
    rhythm = onboard.get("rhythm") or {}
    slot = rhythm.get("first_session_slot") or (rhythm.get("study_times") or ["Tomorrow at 18:00"])[0]

    steps = []
    for key in frontier[:3]:
        c = by_key.get(key)
        if c:
            steps.append({"concept_id": c.id, "skill_key": c.key, "title": c.title,
                          "reason": "Ready on your knowledge frontier (prerequisites met)."})
    if not steps and concepts:
        c = next((x for x in concepts if not x.is_foundation), concepts[0])
        steps.append({"concept_id": c.id, "skill_key": c.key, "title": c.title,
                      "reason": "First core concept on your roadmap."})

    plan = {
        "subject_id": subject_id,
        "goal": onboard.get("goal", "unsure"),
        "exam_date": onboard.get("exam_date"),
        "first_session_slot": slot,
        "hours_per_week": rhythm.get("hours_per_week", 5),
        "recommended_steps": steps,
    }
    init_row = db.get(InitialProfileRow, p.get("profile_id")) if p.get("profile_id") else None
    if init_row is None:
        init_row = db.scalar(select(InitialProfileRow).where(
            InitialProfileRow.owner_id == e.owner_id,
            InitialProfileRow.subject_id == subject_id,
        ).order_by(InitialProfileRow.created_at.desc()))
    if init_row is not None:
        init_row.first_plan = plan
        db.flush()

    events.publish(db, events.Event(events.PLAN_UPDATED, e.owner_id, plan))
