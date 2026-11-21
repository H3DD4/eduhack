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
from thinkfirst.core.db import utcnow
from thinkfirst.core.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from thinkfirst.platform.identity.models import (
    DEFAULT_PREFERENCES,
    AccessAuditLog,
    AuthSession,
    ConsentGrant,
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
