"""Layer 1 of the behavioral tracking layer: raw events in the xAPI pattern (actor - verb - object - result - context)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Verb(StrEnum):
    VIEWED = "viewed"
    STARTED = "started"
    ANSWERED = "answered"
    EDITED = "edited"
    SKIPPED = "skipped"
    REQUESTED_HELP = "requested_help"
    RECEIVED_HINT = "received_hint"
    RATED_CONFIDENCE = "rated_confidence"
    PAUSED = "paused"
    RESUMED = "resumed"
    ABANDONED = "abandoned"
    COMPLETED = "completed"
    FLAGGED_ERROR = "flagged_error"


# What we never track (design doc, "What we never track"): rejected at the schema level, whatever the consent.
NEVER_TRACKED = frozenset({
    "camera", "microphone", "keystrokes", "keylog", "location", "gps", "geolocation", "contacts", "installed_apps",
    "other_apps", "health", "mental_health", "diagnosis",
})


class EventError(ValueError):
    pass


def _scan_forbidden(node: Any, path: str = "") -> None:
    if isinstance(node, Mapping):
        for k, v in node.items():
            if str(k).lower() in NEVER_TRACKED:
                raise EventError(f"{path}{k!r} is never tracked")
            _scan_forbidden(v, f"{path}{k}.")
    elif isinstance(node, (list, tuple)):
        for v in node:
            _scan_forbidden(v, path)


@dataclass(frozen=True)
class TrackingEvent:
    actor: str                                   # pseudonymous student id (real identity stays in Identity)
    verb: Verb
    object: Mapping[str, Any]                    # {"type": "item", "id": "...", "skills": [...]}
    result: Mapping[str, Any] = field(default_factory=dict, compare=False)
    context: Mapping[str, Any] = field(default_factory=dict, compare=False)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:8]}")

    def __post_init__(self) -> None:
        if not self.actor or "@" in self.actor:
            raise EventError("actor must be a pseudonymous id, never an email or empty")
        if not self.object.get("type") or not self.object.get("id"):
            raise EventError("object needs a type and an id")
        if self.timestamp.tzinfo is None:
            raise EventError("timestamp must be timezone-aware")
        _scan_forbidden({"object": self.object, "result": self.result, "context": self.context})

    def to_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, "actor": self.actor, "verb": self.verb.value, "object": dict(self.object),
                "result": dict(self.result), "context": dict(self.context),
                "timestamp": self.timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> TrackingEvent:
        try:
            verb = Verb(raw["verb"])
        except (KeyError, ValueError) as exc:
            raise EventError(f"unknown or missing verb: {raw.get('verb')!r}") from exc
        ts = raw.get("timestamp")
        try:
            when = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else datetime.now(UTC)
        except ValueError as exc:
            raise EventError(f"bad timestamp {ts!r}") from exc
        extra = {"event_id": raw["event_id"]} if raw.get("event_id") else {}
        return cls(actor=str(raw.get("actor", "")), verb=verb, object=dict(raw.get("object") or {}),
                   result=dict(raw.get("result") or {}), context=dict(raw.get("context") or {}), timestamp=when, **extra)
