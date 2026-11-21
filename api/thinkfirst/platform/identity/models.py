"""identity: users, roles, auth sessions, settings, consent grants, access audit log."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, TimestampMixin, new_id

SCHEMA = {"schema": "identity"}

DEFAULT_PREFERENCES = {
    "audio_retention": "delete_after_confirmation",  # default per override §3.3
    "quiet_mode": False,
    "xp_visible": False,
    "reduced_motion": "system",
    "input_preference": "text",
    "language": "en",
}


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(300), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="student")  # student | admin
    display_name: Mapped[str] = mapped_column(String(120), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    goal: Mapped[str | None] = mapped_column(String(32), nullable=True)  # understand|exam|self_study|unsure
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    preferences: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_PREFERENCES))


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of the cookie token
    user_id: Mapped[str] = mapped_column(ForeignKey("identity.users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime]
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ConsentGrant(Base, TimestampMixin):
    """Student consent for admin access: scoped, purpose-specific, expiring, revocable (override §3.9)."""

    __tablename__ = "consent_grants"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(String(36), index=True)
    grantee_role: Mapped[str] = mapped_column(String(16), default="admin")
    purpose: Mapped[str] = mapped_column(String(300))
    scope_items: Mapped[list] = mapped_column(JSON, default=list)  # [{"type": "evidence", "id": "..."}]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AccessAuditLog(Base, TimestampMixin):
    """Append-only. The service layer exposes no update/delete; Postgres trigger blocks them too."""

    __tablename__ = "access_audit_log"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(String(36), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))
    actor_role: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(64))  # e.g. access_granted, access_denied, consent_created
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    consent_grant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(300), nullable=True)
