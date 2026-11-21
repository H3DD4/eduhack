"""adaptation: population-level bandit statistics. Aggregated counts only (no student id, no content), so the
action bandit learns across all students without exposing anyone's private learning history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, new_id, utcnow


class BanditStat(Base):
    __tablename__ = "bandit_stats"
    __table_args__ = (UniqueConstraint("context_key", "action"), {"schema": "adaptation"})

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    context_key: Mapped[str] = mapped_column(String(96))
    action: Mapped[str] = mapped_column(String(32))
    successes: Mapped[float] = mapped_column(Float, default=0.0)
    failures: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
