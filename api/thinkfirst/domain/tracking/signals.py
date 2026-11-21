"""Layer 2: the signal catalog, and redaction of events by consent tier."""

from __future__ import annotations

from dataclasses import dataclass, replace

from thinkfirst.domain.consent.tiers import ConsentState, Tier
from thinkfirst.domain.tracking.events import TrackingEvent, Verb


@dataclass(frozen=True)
class Signal:
    name: str
    measure: str
    tier: Tier


SIGNAL_CATALOG: tuple[Signal, ...] = (
    Signal("response_time", "Time from item shown to submit", Tier.ESSENTIAL),
    Signal("time_to_first_action", "Time before the first keystroke or tap", Tier.LEARNING_BEHAVIOR),
    Signal("edits_and_revisions", "Number of changes before submitting", Tier.LEARNING_BEHAVIOR),
    Signal("help_seeking_timing", "Time and attempts before asking for help", Tier.ESSENTIAL),
    Signal("skips_and_give_ups", "Items skipped, sessions abandoned mid-way", Tier.ESSENTIAL),
    Signal("confidence_rating", "1-5 before seeing the result", Tier.ESSENTIAL),
    Signal("session_rhythm", "Time of day, session length, breaks", Tier.LEARNING_BEHAVIOR),
    Signal("focus_switches", "App sent to background during an item", Tier.LEARNING_BEHAVIOR),
    Signal("free_text_tone", "Negative or frustrated wording in chat", Tier.LEARNING_BEHAVIOR),
)

# Verbs that are learning-behavior by nature (hesitation, edits, rhythm). Everything else is essential.
VERB_TIERS: dict[Verb, Tier] = {Verb.EDITED: Tier.LEARNING_BEHAVIOR, Verb.PAUSED: Tier.LEARNING_BEHAVIOR,
                                Verb.RESUMED: Tier.LEARNING_BEHAVIOR}

# Fields inside `result` / `context` that belong to a tier above essential. Unlisted fields are essential.
FIELD_TIERS: dict[str, Tier] = {
    "result.edits": Tier.LEARNING_BEHAVIOR,
    "result.time_to_first_action_ms": Tier.LEARNING_BEHAVIOR,
    "result.free_text_tone": Tier.LEARNING_BEHAVIOR,
    "result.negative_words": Tier.LEARNING_BEHAVIOR,
    "context.focus_switches": Tier.LEARNING_BEHAVIOR,
    "context.hour_of_day": Tier.LEARNING_BEHAVIOR,
    "context.session_length_ms": Tier.LEARNING_BEHAVIOR,
    "context.breaks": Tier.LEARNING_BEHAVIOR,
    "result.audio_ref": Tier.VOICE_IMAGES,
    "result.image_ref": Tier.VOICE_IMAGES,
}


def redact(event: TrackingEvent, consent: ConsentState) -> TrackingEvent | None:
    """What may be stored for this student: None if the event itself is not allowed, else the event minus
    every field whose tier the student has not granted."""
    if not consent.allows(Tier.ESSENTIAL):  # minors without guardian consent: nothing but the account
        return None
    if not consent.allows(VERB_TIERS.get(event.verb, Tier.ESSENTIAL)):
        return None
    result = {k: v for k, v in event.result.items()
              if consent.allows(FIELD_TIERS.get(f"result.{k}", Tier.ESSENTIAL))}
    context = {k: v for k, v in event.context.items()
               if consent.allows(FIELD_TIERS.get(f"context.{k}", Tier.ESSENTIAL))}
    return replace(event, result=result, context=context)
