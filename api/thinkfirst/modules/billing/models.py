"""billing: entitlements (mock provider), quota reservations, idempotent usage charges."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id

SCHEMA = {"schema": "billing"}


class Entitlement(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "entitlements"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    provider: Mapped[str] = mapped_column(String(32), default="mock")  # labeled mock entitlement provider
    period_units: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[datetime]
    period_days: Mapped[int] = mapped_column(Integer)


class Reservation(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "reservations"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32))  # validation_bundle | professor_question
    units_reserved: Mapped[int] = mapped_column(Integer)
    units_consumed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="reserved")  # reserved|consumed|released
    purpose_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)  # e.g. session id
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)


class UsageCharge(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "usage_charges"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reservation_id: Mapped[str] = mapped_column(String(36), index=True)
    units: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(64))  # e.g. explanation, followup, transfer
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
