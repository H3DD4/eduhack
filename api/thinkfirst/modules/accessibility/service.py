from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core.errors import NotFound, ValidationFailed
from thinkfirst.modules.accessibility.models import AccessibilityProfile

FIELDS = {
    "enabled": (bool, None),
    "font": (str, {"Arial", "Verdana", "Lexend", "Atkinson Hyperlegible", "OpenDyslexic"}),
    "font_size": (int, (14, 20)),
    "line_spacing": (float, (1.5, 2.0)),
    "letter_spacing": (float, (0.0, 0.12)),
    "word_spacing": (float, (0.0, 0.3)),
    "theme": (str, {"cream", "pastel", "dark", "high-contrast"}),
    "line_width": (int, (50, 70)),
    "focus_mode": (str, {"off", "ruler", "dim"}),
    "tts_enabled": (bool, None),
    "tts_speed": (float, (0.75, 1.5)),
    "speech_language": (str, {"en-GB", "fr-FR", "ar-SA"}),
    "stt_enabled": (bool, None),
    "extra_time_factor": (float, (1.0, 2.0)),
    "hide_timer": (bool, None),
    "arabic_diacritics": (bool, None),
    "spelling_suggestions": (bool, None),
    "word_prediction": (bool, None),
    "language_subject_ids": (list, None),
}

READING_RULES = (
    "Presentation rules requested by the student: use short sentences, one idea per sentence, "
    "simple vocabulary with brief definitions for difficult terms, numbered steps or bullets, "
    "bold key terms, and a three-point summary. Offer a concrete example and a diagram or concept map "
    "when available. Keep the same intellectual level, Socratic approach, progressive hints, and "
    "source-citation requirements. Never diagnose, label, compare, or criticize the student."
)
SPELLING_RULES = (
    "For this non-language subject, judge the intended idea rather than minor spelling or phonetic "
    "errors. Do not correct spelling or lower a semantically correct answer for decoding errors. "
    "If the intended meaning is unclear, use an uncertain verdict instead of guessing."
)


def _enabled() -> None:
    if not get_settings().enable_accessibility_module:
        raise NotFound()


def get_profile(db: Session, student_id: str) -> AccessibilityProfile | None:
    _enabled()
    return db.get(AccessibilityProfile, student_id)


def profile_public(profile: AccessibilityProfile | None) -> dict | None:
    if profile is None:
        return None
    result = {key: getattr(profile, key) for key in FIELDS}
    result["consent_given_at"] = profile.consent_given_at.isoformat() if profile.consent_given_at else None
    return result


def give_consent(db: Session, student_id: str, accepted: bool) -> AccessibilityProfile:
    _enabled()
    if not accepted:
        raise ValidationFailed("Consent is required before saving reading-aid settings.", field="accepted")
    profile = db.get(AccessibilityProfile, student_id)
    if profile is None:
        profile = AccessibilityProfile(student_id=student_id)
        db.add(profile)
    profile.consent_given_at = datetime.now(UTC)
    profile.enabled = True
    profile.tts_enabled = True
    profile.tts_speed = 1.0
    profile.speech_language = "en-GB"
    profile.stt_enabled = False
    db.flush()
    return profile


def update_profile(db: Session, student_id: str, changes: dict) -> AccessibilityProfile:
    _enabled()
    profile = db.get(AccessibilityProfile, student_id)
    if profile is None or profile.consent_given_at is None:
        raise ValidationFailed("Review and accept the privacy notice before saving settings.", field="consent")
    if not changes:
        raise ValidationFailed("Choose at least one setting to update.")
    for key, value in changes.items():
        spec = FIELDS.get(key)
        if spec is None or key == "enabled" and value is None:
            raise ValidationFailed(f"Unsupported setting: {key}.", field=key)
        if value is None:
            setattr(profile, key, None)
            continue
        if key == "language_subject_ids":
            from thinkfirst.platform.workspaces.models import Subject

            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValidationFailed("Choose valid language-subject settings.", field=key)
            owned_ids = set(db.scalars(select(Subject.id).where(
                Subject.owner_id == student_id, Subject.id.in_(value)
            )).all()) if value else set()
            if owned_ids != set(value):
                raise ValidationFailed("A selected subject is not available in your account.", field=key)
            profile.language_subject_ids = sorted(owned_ids)
            continue
        kind, limits = spec
        if kind is bool:
            valid = type(value) is bool
        elif kind is int:
            valid = type(value) is int and limits[0] <= value <= limits[1]
        elif kind is float:
            valid = type(value) in (float, int) and not isinstance(value, bool) and limits[0] <= value <= limits[1]
        else:
            valid = isinstance(value, str) and value in limits
        if not valid:
            raise ValidationFailed(f"Unsupported setting value for {key}.", field=key)
        setattr(profile, key, value)
    db.flush()
    return profile


def prompt_rules(db: Session, student_id: str | None, *, prompt_id: str, subject_id: str | None = None) -> str | None:
    if not profile_active(db, student_id):
        return None
    profile = db.get(AccessibilityProfile, student_id)
    if prompt_id == "grade_short_answer":
        language_subjects = set(profile.language_subject_ids or []) if profile else set()
        return None if subject_id in language_subjects else SPELLING_RULES
    if prompt_id in {"professor_scaffold", "generate_concept_pack", "generate_topic_scope"}:
        return READING_RULES
    return None


def profile_active(db: Session, student_id: str | None) -> bool:
    if not student_id or not get_settings().enable_accessibility_module:
        return False
    profile = db.get(AccessibilityProfile, student_id)
    return bool(profile is not None and profile.enabled and profile.consent_given_at)


def delete_profile(db: Session, student_id: str) -> None:
    _enabled()
    profile = db.get(AccessibilityProfile, student_id)
    if profile is not None:
        db.delete(profile)
