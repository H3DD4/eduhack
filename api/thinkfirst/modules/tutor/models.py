"""tutor: sessions (revisioned + owner lease), tasks (server-only solutions), help events, reflections."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id, utcnow

SCHEMA = {"schema": "tutor"}


class StudySession(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "sessions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_id: Mapped[str] = mapped_column(String(36))
    concept_key: Mapped[str] = mapped_column(String(32))
    graph_revision_id: Mapped[str] = mapped_column(String(36))  # frozen at creation
    kind: Mapped[str] = mapped_column(String(16), default="learn")  # learn | practice
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|active|paused|completed|abandoned
    stage: Mapped[str] = mapped_column(String(16), default="setup")  # setup|recall|learn|practice|explanation|followup|transfer|summary
    revision: Mapped[int] = mapped_column(Integer, default=1)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_device: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)  # drafts, phase, return_phase, cursor
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # input mode, focus prefs, retention choice
    parent_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # foundation detour bookmark
    reservation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Task(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    stage: Mapped[str] = mapped_column(String(16))  # practice | explanation | followup | transfer
    kind: Mapped[str] = mapped_column(String(24))  # expand | equivalent_forms | explain | open
    prompt: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)  # public details (citation, objective...)
    origin: Mapped[str] = mapped_column(String(24))  # verified-source | unverified-source | ai-generated
    origin_detail: Mapped[str] = mapped_column(String(200), default="")
    task_family_id: Mapped[str] = mapped_column(String(64))
    novelty: Mapped[dict] = mapped_column(JSON, default=dict)
    rubric_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # SERVER-ONLY: never serialized unless an authorized reveal happened.
    solution: Mapped[dict] = mapped_column(JSON, default=dict)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    # practice | pending-commit | independent-transfer | guided-transfer
    mode: Mapped[str] = mapped_column(String(24), default="practice")
    help_level: Mapped[int] = mapped_column(Integer, default=0)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False)
    corrective_feedback_shown: Mapped[bool] = mapped_column(Boolean, default=False)
    # open | committed | ended_assisted | abandoned
    status: Mapped[str] = mapped_column(String(16), default="open")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    parent_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    followup_question_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    targets_criterion: Mapped[str | None] = mapped_column(String(32), nullable=True)


class HelpEvent(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "help_events"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    level: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))  # clarify|strategy|substep|worked_example|reveal|professor
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)


class Reflection(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "reflections"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)


class ConceptPack(Base, OwnedMixin, TimestampMixin):
    """AI-generated study pack for one concept (lesson, practice, rubric essentials, follow-ups, transfer).
    Always labelled ai-generated; hints/solutions inside are SERVER-ONLY until disclosed through the ladder."""

    __tablename__ = "concept_packs"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | ready | failed
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    label: Mapped[str] = mapped_column(String(200), default="")
    provider: Mapped[str] = mapped_column(String(32), default="")
