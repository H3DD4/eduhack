"""SQLite store (stdlib only). One table per collection: id, owner_id, track_id, data (JSON), created_at.
Good for development, tests and single-server pilots. Use SQLAlchemyStore for Postgres in production."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .base import COLLECTIONS, matches


class SQLiteStore:
    def __init__(self, path: str = "./tutor-dev.db", blob_dir: str = "./.tutor-blobs"):
        self.path = path
        self.blob_dir = Path(blob_dir)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL" if path != ":memory:" else "PRAGMA journal_mode=MEMORY")
        for c in COLLECTIONS:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {c} (id TEXT PRIMARY KEY, owner_id TEXT, track_id TEXT, "
                               f"data TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            self._conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{c}_track ON {c}(track_id)")
            self._conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{c}_owner ON {c}(owner_id)")

    @staticmethod
    def _coll(c: str) -> str:
        if c not in COLLECTIONS:
            raise KeyError(c)
        return c

    def put(self, coll: str, obj: dict[str, Any]) -> dict[str, Any]:
        self.put_many(coll, [obj])
        return obj

    def put_many(self, coll: str, objs: list[dict[str, Any]]) -> None:
        c = self._coll(coll)
        rows = [(o["id"], o.get("owner_id"), o.get("track_id") if coll != "tracks" else o["id"],
                 json.dumps(o, ensure_ascii=False, default=str)) for o in objs]
        with self._lock:
            self._conn.execute("BEGIN")
            self._conn.executemany(f"INSERT INTO {c}(id, owner_id, track_id, data) VALUES (?,?,?,?) "
                                   f"ON CONFLICT(id) DO UPDATE SET data=excluded.data, owner_id=excluded.owner_id, "
                                   f"track_id=excluded.track_id", rows)
            self._conn.execute("COMMIT")

    def get(self, coll: str, obj_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(f"SELECT data FROM {self._coll(coll)} WHERE id=?", (obj_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, coll: str, *, track_id: str | None = None, owner_id: str | None = None,
             where: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        q, args = f"SELECT data FROM {self._coll(coll)} WHERE 1=1", []
        if track_id is not None:
            q += " AND track_id=?"
            args.append(track_id)
        if owner_id is not None:
            q += " AND owner_id=?"
            args.append(owner_id)
        q += " ORDER BY rowid"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        out = [o for o in (json.loads(r[0]) for r in rows) if matches(o, where)]
        return out[:limit] if limit else out

    def delete(self, coll: str, obj_id: str) -> None:
        with self._lock:
            self._conn.execute(f"DELETE FROM {self._coll(coll)} WHERE id=?", (obj_id,))

    def delete_track(self, track_id: str) -> None:
        with self._lock:
            for d in self.list("documents", track_id=track_id):
                p = self.blob_dir / d.get("blob_key", "__none__")
                if d.get("blob_key") and p.exists():
                    os.remove(p)
            for c in COLLECTIONS:
                self._conn.execute(f"DELETE FROM {c} WHERE track_id=?", (track_id,))

    def put_blob(self, key: str, data: bytes) -> None:
        p = self.blob_dir / key.replace("..", "_")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_blob(self, key: str) -> bytes:
        return (self.blob_dir / key.replace("..", "_")).read_bytes()
