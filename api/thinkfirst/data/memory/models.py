"""memory (Historique & mémoire): append-only per-student learning history — answers, errors, misconceptions,
help used, reveals, conversions. Private (RLS). Used by the adaptation engine and the tutor."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id, utcnow


class LearningEvent(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "learning_events"
    __table_args__ = {"schema": "memory"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # answer | error | misconception | help | reveal | conversion | unscored
    kind: Mapped[str] = mapped_column(String(24))
    stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    # learner-engine fields (modules/adaptation/engine) — one row == one engine LearningEvent
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)        # correct|partial|incorrect|unscored
    assistance: Mapped[str] = mapped_column(String(24), default="none")
    evidence: Mapped[str] = mapped_column(String(24), default="sufficient")
    is_fresh: Mapped[bool] = mapped_column(Boolean, default=True)
    misconception_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    misconception_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    context_key: Mapped[str | None] = mapped_column(String(96), nullable=True)
    propensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward: Mapped[float | None] = mapped_column(Float, nullable=True)


class BehavioralEvent(Base, OwnedMixin, TimestampMixin):
    """Layer 1 xAPI behavioral tracking event (pseudonymous actor, consent-redacted result & context)."""

    __tablename__ = "behavioral_events"
    __table_args__ = {"schema": "memory"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)  # pseudonymous id (stu_...)
    verb: Mapped[str] = mapped_column(String(32), index=True)
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(120), index=True)
    subject_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    event_ts: Mapped[datetime] = mapped_column(default=utcnow)


class BehaviorIndicator(Base, OwnedMixin, TimestampMixin):
    """Layer 3 derived learning-analytics indicator (probability + confidence, never a label shown to the student)."""

    __tablename__ = "behavior_indicators"
    __table_args__ = {"schema": "memory"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(48), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
