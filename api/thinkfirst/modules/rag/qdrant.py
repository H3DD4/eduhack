"""Minimal Qdrant REST client (no extra dependency). Points hold vectors + ids + filter fields only — the text stays
in Postgres. Course points carry owner_id/subject_id and EVERY course search filters on both (Qdrant has no RLS)."""

from __future__ import annotations

import re
import time

import httpx

from thinkfirst.config import get_settings

COURSE, LIBRARY = "course_chunks", "open_library"
_ready: dict[str, float] = {}
_health: tuple[float, bool] = (0.0, False)


class QdrantError(Exception):
    pass


def _client() -> httpx.Client:
    s = get_settings()
    headers = {"api-key": s.qdrant_api_key} if s.qdrant_api_key else {}
    return httpx.Client(base_url=s.qdrant_url or "", headers=headers, timeout=20)


def collection_name(kind: str, embedder_id: str, dim: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", embedder_id.split("/")[-1].lower()).strip("-")
    return f"{kind}__{slug}_{dim}"  # embedder-specific: switching models never mixes vector spaces


def healthy() -> bool:
    global _health
    if not get_settings().qdrant_url:
        return False
    if time.time() - _health[0] < 30:
        return _health[1]
    try:
        with _client() as c:
            ok = c.get("/readyz").status_code == 200
    except httpx.HTTPError:
        ok = False
    _health = (time.time(), ok)
    return ok


def ensure_collection(name: str, dim: int, keyword_fields: tuple[str, ...]) -> None:
    if _ready.get(name):
        return
    with _client() as c:
        r = c.get(f"/collections/{name}")
        if r.status_code == 404:
            r = c.put(f"/collections/{name}", json={"vectors": {"size": dim, "distance": "Cosine"}})
            if r.status_code >= 400:
                raise QdrantError(f"CREATE_{r.status_code}")
            for f in keyword_fields:
                c.put(f"/collections/{name}/index", json={"field_name": f, "field_schema": "keyword"})
        elif r.status_code >= 400:
            raise QdrantError(f"GET_{r.status_code}")
    _ready[name] = time.time()


def upsert(name: str, points: list[dict]) -> None:
    if not points:
        return
    with _client() as c:
        for i in range(0, len(points), 128):
            r = c.put(f"/collections/{name}/points", params={"wait": "true"}, json={"points": points[i:i + 128]})
            if r.status_code >= 400:
                raise QdrantError(f"UPSERT_{r.status_code}")


def _filter(must: dict[str, str]) -> dict:
    return {"must": [{"key": k, "match": {"value": v}} for k, v in must.items()]}


def search(name: str, vector: list[float], k: int, must: dict[str, str] | None = None) -> list[tuple[float, str]]:
    body: dict = {"vector": vector, "limit": k, "with_payload": False}
    if must:
        body["filter"] = _filter(must)
    with _client() as c:
        r = c.post(f"/collections/{name}/points/search", json=body)
        if r.status_code == 404:
            return []
        if r.status_code >= 400:
            raise QdrantError(f"SEARCH_{r.status_code}")
        return [(float(p["score"]), str(p["id"])) for p in r.json().get("result", [])]


def delete(name: str, must: dict[str, str]) -> None:
    with _client() as c:
        r = c.post(f"/collections/{name}/points/delete", params={"wait": "true"}, json={"filter": _filter(must)})
        if r.status_code not in (200, 404):
            raise QdrantError(f"DELETE_{r.status_code}")
