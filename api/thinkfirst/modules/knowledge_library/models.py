"""knowledge_library (STUB + data model, M6). Three separate content categories (override §3.8):

(a) SharedResource  — shared metadata, permitted original summaries and links; the product links out.
(b) LicensedContent — stored/embedded ONLY when its license explicitly permits; license/source/attribution per item.
    robots.txt compliance is NOT a content license.
(c) Private student materials live in ingestion/explain_back/assessment and are never shared.

Contribution — a student's opt-in to contribute a past exam/sheet. Stays PRIVATE until an explicit rights
declaration AND admin review approve it; unclear => private.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, OwnedMixin, TimestampMixin, new_id

SCHEMA = {"schema": "knowledge_library"}
ORIGIN_LABELS = ("verified-source", "unverified-source", "ai-generated")


class SharedResource(Base, TimestampMixin):
    __tablename__ = "shared_resources"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(16))
    level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concept_tags: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")  # original short summary, not copied text
    why_recommended: Mapped[str] = mapped_column(Text, default="")
    origin_label: Mapped[str] = mapped_column(String(24), default="unverified-source")
    quality_signals: Mapped[dict] = mapped_column(JSON, default=dict)


class LicensedContent(Base, TimestampMixin):
    __tablename__ = "licensed_content"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(String(1000))
    license_id: Mapped[str] = mapped_column(String(64))  # e.g. CC-BY-4.0
    license_url: Mapped[str] = mapped_column(String(1000))
    attribution: Mapped[str] = mapped_column(Text)
    permits_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    permits_redistribution: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    origin_label: Mapped[str] = mapped_column(String(24), default="verified-source")


class Contribution(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "contributions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32))  # past_exam | exercise_sheet
    source_ref: Mapped[str] = mapped_column(String(36))  # private ingestion source id
    rights_declaration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), default="private")  # private|pending_review|approved|rejected
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)


def can_share(c: Contribution) -> bool:
    """Opt-in alone never grants distribution rights. Requires explicit declaration AND admin approval."""
    d = c.rights_declaration or {}
    return (c.review_status == "approved" and d.get("holder_confirmed") is True
            and d.get("distribution_permitted") is True and bool(d.get("rights_holder")))


def can_store_licensed(item: LicensedContent) -> bool:
    return bool(item.license_id and item.license_url and item.attribution and item.permits_storage)
