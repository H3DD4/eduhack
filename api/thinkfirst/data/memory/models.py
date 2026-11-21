"""memory (Historique & mémoire): append-only per-student learning history — answers, errors, misconceptions,
help used, reveals, conversions. Private (RLS). Used by the adaptation engine and the tutor."""

from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id


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
