"""student_profile (Profil élève, PostgreSQL schema `learner_model`): evidence receipts and review dates."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id, utcnow

SCHEMA = {"schema": "learner_model"}

# Evidence labels (override §3.2). 'explained' is the separate explain-back stage record.
LABELS = {
    "introduced": "Introduced",
    "practised_with_support": "Practised with support",
    "explained": "Explained back",
    "applied_independently": "Applied independently (no in-app help)",
    "recalled_later": "Recalled later on {date}",
    "insufficient_evidence": "Insufficient evidence",
}


class EvidenceRecord(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "evidence_records"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    concept_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    stage: Mapped[str] = mapped_column(String(24))  # recall|learn|practice|explanation|followup|transfer|diagnostic|review
    label: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(24))  # demonstrated | partial | not_demonstrated | unscored | exposure
    status: Mapped[str] = mapped_column(String(16), default="accepted")  # accepted | disputed | superseded | deleted
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(24), nullable=True)
    method_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assistance: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ReviewSchedule(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "review_schedules"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled | completed | cancelled
    basis: Mapped[str] = mapped_column(String(200), default="Adjustable 3-day default (a scheduling hypothesis, not an optimum)")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
