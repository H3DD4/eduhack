"""explain_back: audio takes and transcript versions (original ASR / corrected / typed / supplement)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id

SCHEMA = {"schema": "explain_back"}


class AudioTake(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "audio_takes"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    take_no: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    capture_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # stored, never scored
    storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # uploaded | transcribing | transcribed | deleted
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    retention: Mapped[str] = mapped_column(String(32), default="delete_after_confirmation")
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)


class TranscriptVersion(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "transcript_versions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    take_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))  # original_asr | corrected | typed | supplement
    text: Mapped[str] = mapped_column(Text)
    uncertain_spans: Mapped[list] = mapped_column(JSON, default=list)  # [{id, text, reason}]
    resolved_span_ids: Mapped[list] = mapped_column(JSON, default=list)
    based_on_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_label: Mapped[str] = mapped_column(String(300), default="")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
