"""assessment: rubrics, attempts, assessments (criterion results with null scoring), disputes (M3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id, utcnow

SCHEMA = {"schema": "assessment"}


class Rubric(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "rubrics"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_key: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer, default=1)
    template: Mapped[str] = mapped_column(String(64))  # e.g. distributive-v1 | generic-v1
    approval: Mapped[str] = mapped_column(String(64), default="demo-not-domain-approved")
    explain_prompt: Mapped[str] = mapped_column(Text)
    criteria: Mapped[list] = mapped_column(JSON)  # [{criterion, applicable, essentials:[{id, description, patterns}], contradictions}]
    followup_bank: Mapped[dict] = mapped_column(JSON, default=dict)
    source_citation: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Attempt(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "attempts"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    task_revision: Mapped[int] = mapped_column(Integer)
    response_kind: Mapped[str] = mapped_column(String(16))  # text | audio
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # confirmed text only
    supplement_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    spelling_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mode_at_submit: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="submitted")  # submitted | committed | deleted
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Assessment(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "assessments"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(String(36), index=True)
    rubric_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    method: Mapped[str] = mapped_column(String(32))  # symbolic | simulated | ai
    method_label: Mapped[str] = mapped_column(String(200))
    criteria: Mapped[list] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(24))  # demonstrated | partial | not_demonstrated | unscored
    sufficiency: Mapped[str] = mapped_column(String(24))  # sufficient | limited | needs-verification
    reason: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")
    misconception: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class DiagnosticItemRow(Base, OwnedMixin, TimestampMixin):
    """Calibrated item bank entry linked to 1-3 skills via the Q-matrix, with misconception distractors."""

    __tablename__ = "diagnostic_items"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    item_key: Mapped[str] = mapped_column(String(64), index=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)  # Q-matrix row: 1-3 skill keys
    prompt: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), default="mcq")  # mcq | expand | equation
    expression: Mapped[str | None] = mapped_column(String(200), nullable=True)
    answer_key: Mapped[str] = mapped_column(String(200))
    options: Mapped[list] = mapped_column(JSON, default=list)  # [{id, text, misconception, feedback}]
    difficulty: Mapped[float] = mapped_column(Float, default=1000.0)
    typical_ms: Mapped[int] = mapped_column(Integer, default=45000)
    diagnostic: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    generated: Mapped[bool] = mapped_column(Boolean, default=False)
    calibrated: Mapped[bool] = mapped_column(Boolean, default=True)
    n_answers: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(8), default="en")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DiagnosticSessionRow(Base, OwnedMixin, TimestampMixin):
    """Adaptive diagnostic session (CAT + KST + BKT + Elo + behavioral signals)."""

    __tablename__ = "diagnostic_sessions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(24), default="active")  # active | completed | skipped
    starting_theta: Mapped[float] = mapped_column(Float, default=1000.0)
    current_theta: Mapped[float] = mapped_column(Float, default=1000.0)
    current_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    answers: Mapped[list] = mapped_column(JSON, default=list)
    stop_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
