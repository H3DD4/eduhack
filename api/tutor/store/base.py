"""Storage interface. Records are plain dicts (schemas.* dumps); every record has id and owner_id, most have
track_id. Two implementations: SQLiteStore (stdlib, default, tests) and SQLAlchemyStore (Postgres+pgvector)."""

from __future__ import annotations

from typing import Any, Protocol

COLLECTIONS = ("tracks", "documents", "chunks", "concepts", "fingerprints", "web_sources", "artifacts", "attempts",
               "learner", "tutorial", "runs", "plans")


class Store(Protocol):
    def put(self, coll: str, obj: dict[str, Any]) -> dict[str, Any]: ...
    def put_many(self, coll: str, objs: list[dict[str, Any]]) -> None: ...
    def get(self, coll: str, obj_id: str) -> dict[str, Any] | None: ...
    def list(self, coll: str, *, track_id: str | None = None, owner_id: str | None = None,
             where: dict[str, Any] | None = None, limit: int | None = None) -> list[dict[str, Any]]: ...
    def delete(self, coll: str, obj_id: str) -> None: ...
    def delete_track(self, track_id: str) -> None: ...
    def put_blob(self, key: str, data: bytes) -> None: ...
    def get_blob(self, key: str) -> bytes: ...


def matches(obj: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    for k, v in where.items():
        got = obj.get(k)
        if isinstance(v, (list, tuple, set)):
            if got not in v:
                return False
        elif got != v:
            return False
    return True
