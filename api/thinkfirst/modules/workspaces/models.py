"""workspaces: subjects, goals, exam dates (private)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id


class Subject(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "subjects"
    __table_args__ = {"schema": "workspaces"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(16), default="upload")  # upload | guided_topic
    # processing | awaiting_confirmation | needs_attention | ready
    status: Mapped[str] = mapped_column(String(32), default="processing")
    goal: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_graph_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_concept_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
