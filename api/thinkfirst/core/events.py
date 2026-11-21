"""In-process event dispatcher (swappable for a bus later).

Handlers run synchronously inside the publisher's transaction, so a reaction either commits with the
originating change or not at all. Handlers must be idempotent (they key on event payload IDs).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from thinkfirst.core.db import new_id, utcnow


@dataclass
class Event:
    type: str
    owner_id: str
    payload: dict[str, Any]
    id: str = field(default_factory=new_id)
    ts: datetime = field(default_factory=utcnow)


Handler = Callable[[Session, Event], None]
_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(event_type: str):
    def deco(fn: Handler) -> Handler:
        if fn not in _handlers[event_type]:
            _handlers[event_type].append(fn)
        return fn

    return deco


def publish(db: Session, event: Event) -> None:
    for handler in list(_handlers.get(event.type, [])):
        handler(db, event)


# ---- Event catalog ----------------------------------------------------------------------------------------
# Every event type has exactly one owning brain (the only one allowed to publish it) and a list of consumers.
# Stages hand over through events, so any stage can be rebuilt or tested on its own. `tests/test_architecture.py`
# fails if a constant, or a subscribed event type, is missing from EVENT_CONTRACTS.


class Brain(StrEnum):
    CORE = "core"          # identity, consent, policy gate, workspaces
    STUDENT = "student"    # onboarding conversation, companion voice
    SUBJECT = "subject"    # content extractor, RAG, skill graph, item bank
    EVIDENCE = "evidence"  # behavioral tracking, indicators, BKT/Elo, profile
    SESSION = "session"    # tutor session, adaptive diagnostic, grader
    PLAN = "plan"          # planner solver, adaptation engine


@dataclass(frozen=True)
class EventContract:
    owner: Brain
    consumers: tuple[Brain, ...] = ()


# Learning-session events (existing).
SOURCE_CONFIRMED = "source.confirmed"
TRANSCRIPT_CONFIRMED = "transcript.confirmed"
ASSESSMENT_ACCEPTED = "assessment.accepted"
CONVERSION_COMMITTED = "conversion.committed"
ATTEMPT_DELETED = "attempt.deleted"
REVIEW_BOOKED = "review.booked"
DELETION_ACKNOWLEDGED = "deletion.acknowledged"
MISCONCEPTION_DETECTED = "misconception.detected"
EXPOSURE_RECORDED = "exposure.recorded"
HELP_GIVEN = "help.given"  # tutor showed a hint / worked example (feeds memory, engine, hint quality)

# Onboarding -> diagnostic -> first plan (design doc "Architecture up to the Diagnostic", SysBrain ownership).
USER_CREATED = "user.created"
AGE_GATED = "age.gated"
CONSENT_UPDATED = "consent.updated"
PROFILE_SEEDED = "profile.seeded"
GOAL_SET = "goal.set"
WORKSPACE_CREATED = "workspace.created"
CONTENT_INDEXED = "content.indexed"
GRAPH_BUILT = "graph.built"
ITEMS_READY = "items.ready"
INDICATOR_UPDATED = "indicator.updated"
ANSWER_GRADED = "answer.graded"
DIAGNOSTIC_COMPLETED = "diagnostic.completed"
MASTERY_UPDATED = "mastery.updated"
PROFILE_READY = "profile.ready"
PLAN_UPDATED = "plan.updated"

EVENT_CONTRACTS: dict[str, EventContract] = {
    SOURCE_CONFIRMED: EventContract(Brain.SUBJECT, (Brain.SESSION,)),
    TRANSCRIPT_CONFIRMED: EventContract(Brain.SESSION),
    ASSESSMENT_ACCEPTED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    CONVERSION_COMMITTED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    ATTEMPT_DELETED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    REVIEW_BOOKED: EventContract(Brain.PLAN),
    DELETION_ACKNOWLEDGED: EventContract(Brain.SESSION),
    MISCONCEPTION_DETECTED: EventContract(Brain.SESSION, (Brain.EVIDENCE, Brain.PLAN)),
    EXPOSURE_RECORDED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    HELP_GIVEN: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    USER_CREATED: EventContract(Brain.CORE),
    AGE_GATED: EventContract(Brain.CORE, (Brain.CORE,)),                      # consent flow
    CONSENT_UPDATED: EventContract(Brain.CORE, (Brain.STUDENT, Brain.EVIDENCE)),
    PROFILE_SEEDED: EventContract(Brain.STUDENT, (Brain.SESSION,)),
    GOAL_SET: EventContract(Brain.STUDENT, (Brain.PLAN,)),
    WORKSPACE_CREATED: EventContract(Brain.CORE, (Brain.SUBJECT,)),
    CONTENT_INDEXED: EventContract(Brain.SUBJECT, (Brain.SUBJECT,)),          # skill graph extraction
    GRAPH_BUILT: EventContract(Brain.SUBJECT, (Brain.SUBJECT,)),              # item bank and calibration
    ITEMS_READY: EventContract(Brain.SUBJECT, (Brain.SESSION,)),
    INDICATOR_UPDATED: EventContract(Brain.EVIDENCE, (Brain.SESSION, Brain.PLAN)),
    ANSWER_GRADED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    DIAGNOSTIC_COMPLETED: EventContract(Brain.SESSION, (Brain.EVIDENCE,)),
    MASTERY_UPDATED: EventContract(Brain.EVIDENCE, (Brain.PLAN,)),
    PROFILE_READY: EventContract(Brain.EVIDENCE, (Brain.PLAN, Brain.STUDENT)),
    PLAN_UPDATED: EventContract(Brain.PLAN, (Brain.STUDENT,)),
}
