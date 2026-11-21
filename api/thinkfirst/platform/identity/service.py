"""identity service interface."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.core import events
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from thinkfirst.domain.consent.tiers import ConsentError, ConsentState, Tier
from thinkfirst.domain.mastery import elo
from thinkfirst.platform.identity.models import (
    DEFAULT_PREFERENCES,
    AccessAuditLog,
    AuthSession,
    ConsentGrant,
    StudentConsent,
    User,
)

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 64}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, salt_b64, dk_b64 = stored.split("$")
    dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
    return hmac.compare_digest(dk, base64.b64decode(dk_b64))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register(db: Session, email: str, password: str, display_name: str = "") -> User:
    email = normalize_email(email)
    if "@" not in email or len(email) > 320:
        raise ValidationFailed("Enter a valid email address.", field="email")
    if len(password) < 8:
        raise ValidationFailed("Use at least 8 characters.", field="password")
    if db.scalar(select(User).where(User.email == email)):
        raise Conflict("An account with this email already exists.", code="EMAIL_TAKEN", field="email")
    user = User(email=email, password_hash=hash_password(password), display_name=display_name,
                preferences=dict(DEFAULT_PREFERENCES))
    db.add(user)
    db.flush()
    events.publish(db, events.Event(events.USER_CREATED, user.id, {"user_id": user.id, "locale": "en"}))
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if not user or not verify_password(password, user.password_hash):
        raise Unauthorized("Email or password is incorrect.", code="INVALID_CREDENTIALS")
    return user


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(id=_token_id(token), user_id=user.id,
                       expires_at=utcnow() + timedelta(days=get_settings().session_days)))
    db.flush()
    return token


def resolve_session(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    s = db.get(AuthSession, _token_id(token))
    if not s or s.revoked or s.expires_at < utcnow():
        return None
    return db.get(User, s.user_id)


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        s = db.get(AuthSession, _token_id(token))
        if s:
            s.revoked = True


def upsert_google_user(db: Session, sub: str, email: str, name: str) -> User:
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user:
        return user
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user:
        user.google_sub = sub
        return user
    user = User(email=normalize_email(email), google_sub=sub, display_name=name, preferences=dict(DEFAULT_PREFERENCES))
    db.add(user)
    db.flush()
    return user


ALLOWED_PREF_VALUES = {
    "audio_retention": {"delete_after_confirmation", "replay_7_days"},
    "quiet_mode": {True, False},
    "xp_visible": {True, False},
    "reduced_motion": {"system", "reduce", "no-preference"},
    "input_preference": {"text", "voice"},
    "language": {"en"},  # French/Arabic are M7
}


def update_preferences(user: User, changes: dict) -> dict:
    prefs = dict(DEFAULT_PREFERENCES) | dict(user.preferences or {})
    for key, value in changes.items():
        if key not in ALLOWED_PREF_VALUES or value not in ALLOWED_PREF_VALUES[key]:
            raise ValidationFailed(f"Unsupported setting value for {key}.", field=key)
        prefs[key] = value
    user.preferences = prefs
    return prefs


# ---- consent + audit foundation (admin portal is M6) ----

def audit(db: Session, *, student_id: str, actor_id: str, actor_role: str, action: str,
          target_type: str | None = None, target_id: str | None = None,
          consent_grant_id: str | None = None, purpose: str | None = None) -> AccessAuditLog:
    row = AccessAuditLog(student_id=student_id, actor_id=actor_id, actor_role=actor_role, action=action,
                         target_type=target_type, target_id=target_id, consent_grant_id=consent_grant_id,
                         purpose=purpose)
    db.add(row)
    db.flush()
    return row


def create_consent(db: Session, student: User, purpose: str, scope_items: list[dict], hours: int) -> ConsentGrant:
    if not purpose.strip():
        raise ValidationFailed("Describe the purpose of this access.", field="purpose")
    if not scope_items:
        raise ValidationFailed("Choose the specific items to share.", field="scope_items")
    if not 1 <= hours <= 24 * 14:
        raise ValidationFailed("Access must expire within 14 days.", field="hours")
    grant = ConsentGrant(student_id=student.id, purpose=purpose.strip(), scope_items=scope_items,
                         expires_at=utcnow() + timedelta(hours=hours))
    db.add(grant)
    db.flush()
    audit(db, student_id=student.id, actor_id=student.id, actor_role="student", action="consent_created",
          consent_grant_id=grant.id, purpose=grant.purpose)
    return grant


def revoke_consent(db: Session, student: User, grant_id: str) -> ConsentGrant:
    grant = db.get(ConsentGrant, grant_id)
    if not grant or grant.student_id != student.id:
        raise NotFound()
    if grant.revoked_at is None:
        grant.revoked_at = utcnow()
        audit(db, student_id=student.id, actor_id=student.id, actor_role="student", action="consent_revoked",
              consent_grant_id=grant.id, purpose=grant.purpose)
    return grant


def active_grant_for(db: Session, student_id: str, item_type: str, item_id: str, now: datetime | None = None) -> ConsentGrant | None:
    now = now or utcnow()
    grants = db.scalars(select(ConsentGrant).where(ConsentGrant.student_id == student_id)).all()
    for g in grants:
        if g.revoked_at is not None or g.expires_at <= now:
            continue
        if any(i.get("type") == item_type and i.get("id") == item_id for i in g.scope_items):
            return g
    return None


def admin_access_check(db: Session, admin: User, student_id: str, item_type: str, item_id: str) -> ConsentGrant:
    """Admins have NO default access. Every attempt (granted or denied) is audited."""
    if admin.role != "admin":
        raise Forbidden()
    grant = active_grant_for(db, student_id, item_type, item_id)
    if grant is None:
        audit(db, student_id=student_id, actor_id=admin.id, actor_role="admin", action="access_denied",
              target_type=item_type, target_id=item_id)
        raise Forbidden("No active, scoped student consent covers this item.", code="NO_CONSENT")
    audit(db, student_id=student_id, actor_id=admin.id, actor_role="admin", action="access_granted",
          target_type=item_type, target_id=item_id, consent_grant_id=grant.id, purpose=grant.purpose)
    return grant


def audit_log_for_student(db: Session, student_id: str) -> list[AccessAuditLog]:
    return list(db.scalars(select(AccessAuditLog).where(AccessAuditLog.student_id == student_id)
                           .order_by(AccessAuditLog.created_at.desc())).all())


# ---- 4-tier behavioral tracking consent, age gate, minors gating & 10-step onboarding ----

TIER_DESCRIPTIONS = [
    {"tier": Tier.ESSENTIAL.value, "covers": "Answers, correctness, help level, time per item, mastery",
     "default": "on", "can_turn_off": False},
    {"tier": Tier.LEARNING_BEHAVIOR.value, "covers": "Hesitation, edits, hint timing, session rhythm, give-ups",
     "default": "asked", "can_turn_off": True},
    {"tier": Tier.VOICE_IMAGES.value, "covers": "Voice explain-back, photos of paper work",
     "default": "asked_when_used", "can_turn_off": True},
    {"tier": Tier.RESEARCH.value, "covers": "Pooled, anonymized data to improve the product and publish outcome studies",
     "default": "off", "can_turn_off": True},
]


def get_or_create_student_consent(db: Session, owner_id: str) -> StudentConsent:
    row = db.scalar(select(StudentConsent).where(StudentConsent.owner_id == owner_id))
    if row is None:
        row = StudentConsent(owner_id=owner_id, granted_tiers=[Tier.ESSENTIAL.value], onboarding_data={})
        db.add(row)
        db.flush()
    return row


def consent_state(db: Session, owner_id: str) -> ConsentState:
    row = db.scalar(select(StudentConsent).where(StudentConsent.owner_id == owner_id))
    if row is None:
        return ConsentState()
    tiers = frozenset(Tier(t) for t in (row.granted_tiers or [Tier.ESSENTIAL.value]) if t in Tier._value2member_map_)
    return ConsentState(
        granted=tiers | {Tier.ESSENTIAL},
        is_minor=bool(row.is_minor),
        guardian_required=bool(row.guardian_required),
        guardian_consented=bool(row.guardian_consented),
    )


def student_consent_public(row: StudentConsent, state: ConsentState) -> dict:
    return {
        "birth_year": row.birth_year,
        "is_minor": state.is_minor,
        "guardian_required": state.guardian_required,
        "guardian_email": row.guardian_email,
        "guardian_consented": state.guardian_consented,
        "demo_only": state.demo_only,
        "deal_accepted": row.deal_accepted,
        "granted_tiers": sorted(t.value for t in state.granted),
        "tiers": TIER_DESCRIPTIONS,
        "onboarding": row.onboarding_data or {},
    }


def apply_age_gate(db: Session, owner_id: str, birth_year: int, *, guardian_email: str | None = None,
                   current_year: int | None = None) -> dict:
    now_year = current_year or utcnow().year
    if not (1920 <= birth_year <= now_year):
        raise ValidationFailed("Enter a valid birth year.", field="birth_year")
    row = get_or_create_student_consent(db, owner_id)
    base = ConsentState.default(birth_year=birth_year, current_year=now_year)
    # Preserve existing non-research tiers if adult; for minors strip research unless guardian already consented
    existing = frozenset(Tier(t) for t in (row.granted_tiers or ["essential"]) if t in Tier._value2member_map_)
    if base.is_minor and not row.guardian_consented:
        existing = existing - {Tier.RESEARCH}
    state = ConsentState(existing | {Tier.ESSENTIAL}, is_minor=base.is_minor,
                         guardian_required=base.guardian_required, guardian_consented=bool(row.guardian_consented))
    row.birth_year = birth_year
    row.is_minor = state.is_minor
    row.guardian_required = state.guardian_required
    if guardian_email is not None:
        row.guardian_email = guardian_email.strip()[:320] or None
    row.granted_tiers = sorted(t.value for t in state.granted)
    db.flush()
    events.publish(db, events.Event(events.AGE_GATED, owner_id, {
        "birth_year": birth_year, "is_minor": state.is_minor, "demo_only": state.demo_only,
    }))
    return student_consent_public(row, state)


def update_tracking_consent(db: Session, owner_id: str, *, grant: list[str] = (), revoke: list[str] = (),
                            guardian_consented: bool | None = None, guardian_email: str | None = None,
                            deal_accepted: bool | None = None) -> dict:
    row = get_or_create_student_consent(db, owner_id)
    state = consent_state(db, owner_id)
    if guardian_email is not None:
        row.guardian_email = guardian_email.strip()[:320] or None
    if guardian_consented is True:
        state = state.with_guardian_consent()
        row.guardian_consented = True
    elif guardian_consented is False:
        row.guardian_consented = False
        state = ConsentState(state.granted - {Tier.RESEARCH}, state.is_minor, state.guardian_required, False)
    try:
        for t in grant:
            if t not in Tier._value2member_map_:
                raise ValidationFailed(f"Unknown consent tier {t!r}.", field="grant")
            state = state.grant(Tier(t))
        for t in revoke:
            if t not in Tier._value2member_map_:
                raise ValidationFailed(f"Unknown consent tier {t!r}.", field="revoke")
            state = state.revoke(Tier(t))
    except ConsentError as exc:
        raise ValidationFailed(str(exc), field="consent") from exc
    if deal_accepted is not None:
        row.deal_accepted = bool(deal_accepted)
    row.granted_tiers = sorted(t.value for t in state.granted)
    db.flush()
    events.publish(db, events.Event(events.CONSENT_UPDATED, owner_id, {
        "granted_tiers": row.granted_tiers, "is_minor": state.is_minor,
        "guardian_consented": state.guardian_consented, "demo_only": state.demo_only,
        "deal_accepted": row.deal_accepted,
    }))
    return student_consent_public(row, state)


def complete_onboarding(db: Session, user: User, *, goal: str = "unsure", timezone: str = "UTC",
                        input_preference: str = "text", birth_year: int | None = None,
                        guardian_email: str | None = None, guardian_consented: bool | None = None,
                        deal_accepted: bool | None = None, grant_tiers: list[str] | None = None,
                        level: str | None = None, field: str | None = None, exam_date: str | None = None,
                        prior_confidence: int | None = None, study_times: list[str] | None = None,
                        hours_per_week: float | None = None, first_session_slot: str | None = None,
                        interests: list[str] | None = None) -> dict:
    """10-step onboarding architecture (under 3 minutes). Every field has a named consumer."""
    if birth_year is not None:
        apply_age_gate(db, user.id, birth_year, guardian_email=guardian_email)
    if grant_tiers is not None or guardian_consented is not None or deal_accepted is not None:
        update_tracking_consent(db, user.id, grant=grant_tiers or [], guardian_consented=guardian_consented,
                                guardian_email=guardian_email, deal_accepted=deal_accepted)
    if prior_confidence is not None and not (1 <= prior_confidence <= 5):
        raise ValidationFailed("Rate prior confidence from 1 to 5.", field="prior_confidence")
    user.goal = goal
    user.timezone = (timezone or "UTC")[:64]
    update_preferences(user, {"input_preference": input_preference})
    user.setup_complete = True

    row = get_or_create_student_consent(db, user.id)
    data = dict(row.onboarding_data or {})
    norm_goal = {"understand": "mastery", "self_study": "certification"}.get(goal, goal)
    starting_theta = elo.prior_theta(level or data.get("level"), norm_goal)
    data.update({
        "goal": goal,
        "exam_date": exam_date if exam_date is not None else data.get("exam_date"),
        "level": level or data.get("level") or "university",
        "field": field if field is not None else data.get("field", ""),
        "prior_confidence": prior_confidence if prior_confidence is not None else data.get("prior_confidence", 3),
        "prior_theta": starting_theta,
        "rhythm": {
            "study_times": study_times if study_times is not None else data.get("rhythm", {}).get("study_times", []),
            "hours_per_week": hours_per_week if hours_per_week is not None else data.get("rhythm", {}).get("hours_per_week", 5),
            "first_session_slot": first_session_slot if first_session_slot is not None else data.get("rhythm", {}).get("first_session_slot"),
        },
        "comfort": {
            "language": user.preferences.get("language", "en"),
            "voice_enabled": input_preference == "voice",
            "interests": interests if interests is not None else data.get("comfort", {}).get("interests", []),
        },
    })
    row.onboarding_data = data
    db.flush()
    events.publish(db, events.Event(events.PROFILE_SEEDED, user.id, {
        "level": data["level"], "field": data["field"], "prior_theta": starting_theta,
        "prior_confidence": data["prior_confidence"], "interests": data["comfort"]["interests"],
    }))
    events.publish(db, events.Event(events.GOAL_SET, user.id, {
        "goal": goal, "exam_date": data["exam_date"], "rhythm": data["rhythm"],
    }))
    return student_consent_public(row, consent_state(db, user.id))
