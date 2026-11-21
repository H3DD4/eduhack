"""assessment: rubrics, attempts, assessments (criterion results with null scoring), disputes (M3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id

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
