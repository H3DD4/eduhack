"""In-process event dispatcher (swappable for a bus later).

Handlers run synchronously inside the publisher's transaction, so a reaction either commits with the
originating change or not at all. Handlers must be idempotent (they key on event payload IDs).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
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


# Event type names (normalized events, blueprint "Frontend state and data contracts").
SOURCE_CONFIRMED = "source.confirmed"
TRANSCRIPT_CONFIRMED = "transcript.confirmed"
ASSESSMENT_ACCEPTED = "assessment.accepted"
CONVERSION_COMMITTED = "conversion.committed"
ATTEMPT_DELETED = "attempt.deleted"
REVIEW_BOOKED = "review.booked"
DELETION_ACKNOWLEDGED = "deletion.acknowledged"
