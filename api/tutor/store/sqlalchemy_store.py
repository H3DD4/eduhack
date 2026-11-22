"""Postgres (+pgvector) store with SQLAlchemy 2. Same generic shape as SQLiteStore, one table per collection
in schema `tutor_tracks`, data in JSONB, chunk embeddings also in a pgvector column for large tracks.

Pass ThinkFirst's own `session_factory()` so its row-level-security hook (app.user_id) applies:

    from thinkfirst.core.db import session_factory
    store = SQLAlchemyStore(session_factory(), blob=get_storage())
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, DateTime, MetaData, String, Table, delete, func, select
from sqlalchemy.types import JSON

from .base import COLLECTIONS, matches

SCHEMA = "tutor_tracks"
EMBED_DIM = 1024  # bge-m3; the hashing embedder (512) is zero-padded

try:  # pragma: no cover - optional
    from pgvector.sqlalchemy import Vector

    _VEC = Vector(EMBED_DIM)
except Exception:  # noqa: BLE001
    _VEC = None

try:  # pragma: no cover
    from sqlalchemy.dialects.postgresql import JSONB

    _JSON = JSON().with_variant(JSONB(), "postgresql")
except Exception:  # noqa: BLE001
    _JSON = JSON()

metadata = MetaData(schema=SCHEMA)
TABLES: dict[str, Table] = {}
for _name in COLLECTIONS:
    cols = [Column("id", String(64), primary_key=True), Column("owner_id", String(36), index=True),
            Column("track_id", String(64), index=True), Column("data", _JSON, nullable=False),
            Column("created_at", DateTime(timezone=True), server_default=func.now())]
    if _name == "chunks" and _VEC is not None:
        cols.append(Column("embedding", _VEC.with_variant(JSON(), "sqlite"), nullable=True))
    TABLES[_name] = Table(_name, metadata, *cols)


def _pad(v: list[float] | None) -> list[float] | None:
    if not v:
        return None
    return (v + [0.0] * EMBED_DIM)[:EMBED_DIM]


class SQLAlchemyStore:
    def __init__(self, session_factory, blob=None):
        """session_factory: a sessionmaker (or any callable returning a Session context manager).
        blob: object with put(key, data, content_type) / get(key) (ThinkFirst BlobStorage) or None for local."""
        self.sf = session_factory
        self.blob = blob

    def create_all(self, engine) -> None:
        if engine.dialect.name == "postgresql":
            with engine.begin() as c:
                c.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
                c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        metadata.create_all(engine)

    def _upsert(self, s, table: Table, rows: list[dict[str, Any]]) -> None:
        dialect = s.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:  # pragma: no cover
            for r in rows:
                s.execute(delete(table).where(table.c.id == r["id"]))
                s.execute(table.insert().values(**r))
            return
        stmt = insert(table).values(rows)
        upd = {c: stmt.excluded[c] for c in rows[0] if c != "id"}
        s.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=upd))

    def put(self, coll: str, obj: dict[str, Any]) -> dict[str, Any]:
        self.put_many(coll, [obj])
        return obj

    def put_many(self, coll: str, objs: list[dict[str, Any]]) -> None:
        if not objs:
            return
        t = TABLES[coll]
        rows = []
        for o in objs:
            r = {"id": o["id"], "owner_id": o.get("owner_id"),
                 "track_id": o["id"] if coll == "tracks" else o.get("track_id"), "data": o}
            if coll == "chunks" and "embedding" in t.c:
                r["embedding"] = _pad(o.get("embedding"))
            rows.append(r)
        with self.sf() as s:
            for i in range(0, len(rows), 500):
                self._upsert(s, t, rows[i: i + 500])
            s.commit()

    def get(self, coll: str, obj_id: str) -> dict[str, Any] | None:
        t = TABLES[coll]
        with self.sf() as s:
            row = s.execute(select(t.c.data).where(t.c.id == obj_id)).first()
        return dict(row[0]) if row else None

    def list(self, coll: str, *, track_id: str | None = None, owner_id: str | None = None,
             where: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        t = TABLES[coll]
        q = select(t.c.data)
        if track_id is not None:
            q = q.where(t.c.track_id == track_id)
        if owner_id is not None:
            q = q.where(t.c.owner_id == owner_id)
        q = q.order_by(t.c.created_at, t.c.id)
        with self.sf() as s:
            rows = s.execute(q).all()
        out = [o for o in (dict(r[0]) for r in rows) if matches(o, where)]
        return out[:limit] if limit else out

    def vector_search(self, track_id: str, vec: list[float], k: int = 40) -> list[dict[str, Any]]:
        """Server-side ANN prefilter for very large tracks (pgvector cosine distance)."""
        t = TABLES["chunks"]
        if "embedding" not in t.c:
            return self.list("chunks", track_id=track_id)
        with self.sf() as s:
            if s.get_bind().dialect.name != "postgresql":
                return self.list("chunks", track_id=track_id)
            rows = s.execute(select(t.c.data).where(t.c.track_id == track_id)
                             .order_by(t.c.embedding.cosine_distance(_pad(vec))).limit(k)).all()
        return [dict(r[0]) for r in rows]

    def delete(self, coll: str, obj_id: str) -> None:
        t = TABLES[coll]
        with self.sf() as s:
            s.execute(delete(t).where(t.c.id == obj_id))
            s.commit()

    def delete_track(self, track_id: str) -> None:
        docs = self.list("documents", track_id=track_id)
        with self.sf() as s:
            for t in TABLES.values():
                s.execute(delete(t).where(t.c.track_id == track_id))
            s.commit()
        for d in docs:
            if d.get("blob_key") and self.blob is not None:
                try:
                    self.blob.delete(d["blob_key"])
                except Exception:  # noqa: BLE001
                    pass

    def put_blob(self, key: str, data: bytes) -> None:
        if self.blob is None:
            raise RuntimeError("no blob storage configured")
        self.blob.put(key, data, "application/octet-stream")

    def get_blob(self, key: str) -> bytes:
        if self.blob is None:
            raise RuntimeError("no blob storage configured")
        return self.blob.get(key)
