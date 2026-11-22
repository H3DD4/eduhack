"""Database plumbing.

- One Postgres database, one schema per module (ARCHITECTURE §Data). On SQLite the schemas are
  translated away so the same models run in tests.
- Row-level security: every request/job sets ``app.user_id`` for the transaction (Postgres only);
  RLS policies created by the migration restrict private tables to ``owner_id = app.user_id``.
"""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON, TypeDecorator

from thinkfirst.config import get_settings

MODULE_SCHEMAS = [
    "core",
    "identity",
    "workspaces",
    "ingestion",
    "tutor",
    "assessment",
    "explain_back",
    "learner_model",
    "billing",
    "llm_gateway",
    "knowledge_library",
    "admin",
    "memory",
    "adaptation",
]

current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_user_id", default=None)


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes on every backend (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Embedding(TypeDecorator):
    """pgvector column on Postgres, JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 256):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(x) for x in value]


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UTCDateTime()}


class OwnedMixin:
    """Private student data. Every row carries its owner; RLS + owned() helpers enforce isolation."""

    owner_id: Mapped[str] = mapped_column(String(36), index=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


_engine = None
_SessionLocal: sessionmaker | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def normalize_database_url(url: str) -> str:
    """Accept Render/Heroku-style postgres:// or postgresql:// URLs and route them through psycopg3."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def make_engine(url: str | None = None):
    url = normalize_database_url(url or get_settings().database_url)
    if _is_sqlite(url):
        raw_path = url.split("sqlite:///", 1)[1] if "sqlite:///" in url else ":memory:"
        is_mem = raw_path in ("", ":memory:")
        tutor_db = ":memory:" if is_mem else f"{raw_path}.tutor_tracks.sqlite"
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            execution_options={"schema_translate_map": {s: None for s in MODULE_SCHEMAS}},
        )

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            dbapi_conn.execute("PRAGMA busy_timeout=30000")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            if not is_mem:
                row = dbapi_conn.execute("PRAGMA journal_mode").fetchone()
                if not row or str(row[0]).lower() != "wal":
                    dbapi_conn.execute("PRAGMA journal_mode=WAL")
                dbapi_conn.execute("PRAGMA synchronous=NORMAL")
            dbapi_conn.execute(f"ATTACH DATABASE '{tutor_db}' AS tutor_tracks")
            if not is_mem:
                row = dbapi_conn.execute("PRAGMA tutor_tracks.journal_mode").fetchone()
                if not row or str(row[0]).lower() != "wal":
                    dbapi_conn.execute("PRAGMA tutor_tracks.journal_mode=WAL")
                dbapi_conn.execute("PRAGMA tutor_tracks.synchronous=NORMAL")

    else:
        engine = create_engine(url, pool_pre_ping=True)
    return engine


def configure(url: str | None = None):
    global _engine, _SessionLocal
    _engine = make_engine(url)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    _install_rls_hook(_SessionLocal)
    return _engine


def get_engine():
    if _engine is None:
        configure()
    return _engine


def session_factory() -> sessionmaker:
    if _SessionLocal is None:
        configure()
    assert _SessionLocal is not None
    return _SessionLocal


def _install_rls_hook(factory: sessionmaker) -> None:
    @event.listens_for(factory, "after_begin")
    def _set_app_user(session: Session, transaction, connection):
        if connection.dialect.name != "postgresql":
            return
        uid = session.info.get("user_id") or current_user_id.get()
        # set_config(..., true) == SET LOCAL: scoped to this transaction only.
        connection.execute(text("select set_config('app.user_id', :uid, true)"), {"uid": uid or ""})


def get_db() -> Iterator[Session]:
    db = session_factory()()
    db.info["is_request_session"] = True
    try:
        yield db
        db.commit()
        pending = db.info.pop("after_commit_jobs", [])
        if pending:  # arq mode: hand committed job IDs to the Redis worker
            import asyncio

            from thinkfirst.core.jobs import enqueue_remote

            asyncio.run(enqueue_remote(pending))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all_for_tests(engine) -> None:
    import thinkfirst.models  # noqa: F401  (register all module models)
    from tutor.store.sqlalchemy_store import metadata as tutor_tracks_metadata

    Base.metadata.create_all(engine)
    tutor_tracks_metadata.create_all(engine)
