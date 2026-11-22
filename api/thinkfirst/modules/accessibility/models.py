from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, utcnow


class AccessibilityProfile(Base):
    __tablename__ = "accessibility_profile"
    __table_args__ = {"schema": "identity"}

    student_id: Mapped[str] = mapped_column(
        ForeignKey("identity.users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    font: Mapped[str | None] = mapped_column(String(40), nullable=True)
    font_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_spacing: Mapped[float | None] = mapped_column(Float, nullable=True)
    letter_spacing: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_spacing: Mapped[float | None] = mapped_column(Float, nullable=True)
    theme: Mapped[str | None] = mapped_column(String(24), nullable=True)
    line_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tts_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tts_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    speech_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    stt_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra_time_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    hide_timer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    arabic_diacritics: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    spelling_suggestions: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    word_prediction: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    language_subject_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
