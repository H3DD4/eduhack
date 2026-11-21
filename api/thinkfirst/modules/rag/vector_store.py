"""Base vectorielle. Default: pgvector inside PostgreSQL (project stack, RLS-protected per student).
Fallbacks: in-memory cosine (SQLite/tests). Optional: FAISS when `faiss` is installed (`pip install faiss-cpu`),
built per query from the student's own chunks so isolation is preserved. ChromaDB would plug in the same way.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from thinkfirst.modules.ingestion.models import SourceChunk


class VectorStore(Protocol):
    name: str

    def search(self, db: Session, owner_id: str, subject_id: str, vec: list[float], k: int) -> list[tuple[float, SourceChunk]]: ...


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


class InMemoryStore:
    name = "in-memory cosine"

    def search(self, db, owner_id, subject_id, vec, k):
        rows = db.scalars(select(SourceChunk).where(SourceChunk.owner_id == owner_id, SourceChunk.subject_id == subject_id)).all()
        return sorted(((_cos(vec, r.embedding or []), r) for r in rows), key=lambda t: -t[0])[:k]


class PgVectorStore:
    name = "pgvector"

    def search(self, db, owner_id, subject_id, vec, k):
        lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        ids = db.execute(text(
            "select id, 1 - (embedding <=> cast(:q as vector)) as score from ingestion.source_chunks "
            "where owner_id = :o and subject_id = :s and embedding is not null order by embedding <=> cast(:q as vector) limit :k"),
            {"q": lit, "o": owner_id, "s": subject_id, "k": k}).all()
        out = []
        for cid, score in ids:
            row = db.get(SourceChunk, cid)
            if row is not None:
                out.append((float(score), row))
        return out


class FaissStore:
    name = "faiss"

    def search(self, db, owner_id, subject_id, vec, k):
        import faiss  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]

        rows = db.scalars(select(SourceChunk).where(SourceChunk.owner_id == owner_id, SourceChunk.subject_id == subject_id)).all()
        rows = [r for r in rows if r.embedding]
        if not rows:
            return []
        mat = np.array([r.embedding for r in rows], dtype="float32")
        index = faiss.IndexFlatIP(mat.shape[1])
        index.add(mat)
        scores, idx = index.search(np.array([vec], dtype="float32"), min(k, len(rows)))
        return [(float(s), rows[i]) for s, i in zip(scores[0], idx[0], strict=False) if i >= 0]


def store_for(db: Session) -> VectorStore:
    try:
        import faiss  # type: ignore[import-not-found]  # noqa: F401

        return FaissStore()
    except ImportError:
        pass
    return PgVectorStore() if db.get_bind().dialect.name == "postgresql" else InMemoryStore()
