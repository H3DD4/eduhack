"""ingestion: uploads, extraction revisions, pages, chunks+embeddings, concept graph, extracted items.

All rows here are category (c) private student material (override §3.8).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from thinkfirst.core.db import Base, Embedding, OwnedMixin, TimestampMixin, new_id

SCHEMA = {"schema": "ingestion"}


class Source(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(16), default="course")  # course | notes | past_exam
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # C02 phases: queued | extracting | awaiting_confirmation | needs_attention | cancelled | ready | excluded
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_category: Mapped[str] = mapped_column(String(16), default="private")
    rights_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    generation: Mapped[int] = mapped_column(Integer, default=1)  # bumps on cancel/replace; late callbacks rejected
    current_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(nullable=True)  # tombstone


class SourceRevision(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "source_revisions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    checksum: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[int] = mapped_column(Integer, default=1)


class SourcePage(Base, OwnedMixin):
    __tablename__ = "source_pages"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(String(36), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class SourceChunk(Base, OwnedMixin):
    __tablename__ = "source_chunks"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    span_start: Mapped[int] = mapped_column(Integer)
    span_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Embedding(256), nullable=True)


class ConceptGraphRevision(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "concept_graph_revisions"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed | confirmed | superseded
    basis: Mapped[str] = mapped_column(String(32))  # extracted-heuristic | extracted-ai | generated
    extraction_label: Mapped[str] = mapped_column(String(200))
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Concept(Base, OwnedMixin):
    __tablename__ = "concepts"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    graph_revision_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    key: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str] = mapped_column(Text, default="")
    unit_no: Mapped[int] = mapped_column(Integer, default=1)
    unit_title: Mapped[str] = mapped_column(String(300), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)  # concept keys
    citations: Mapped[list] = mapped_column(JSON, default=list)  # [{source_id, revision_id, page, span:[s,e], quote}]
    is_foundation: Mapped[bool] = mapped_column(Boolean, default=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)


class SourceItem(Base, OwnedMixin):
    """Exercises extracted from an uploaded source. Origin is always 'unverified-source' (uploads start unverified)."""

    __tablename__ = "source_items"
    __table_args__ = SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_id: Mapped[str] = mapped_column(String(36), index=True)
    concept_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kind: Mapped[str] = mapped_column(String(16))  # expand | simplify | open
    prompt: Mapped[str] = mapped_column(Text)
    expression: Mapped[str | None] = mapped_column(String(200), nullable=True)
    page_no: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(24), default="unverified-source")
