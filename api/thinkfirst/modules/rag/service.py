"""Module RAG — retrieval-augmented grounding for the tutor, lessons and checks.

Stack: Hugging Face Inference embedder (multilingual MiniLM, 384-d) + Qdrant vector DB (docker service `qdrant`).
Fallback when either is unavailable: labelled demo hashing embedder + pgvector/in-memory (vector_store.py).
Postgres stays the source of truth for text; Qdrant only holds vectors + ids + filter fields.

Two collections, always cited:
1. the student's own course files (private chunks in the vector store, page-level citations);
2. "cours officiels" / open courses gathered by the resource agent (openly licensed text with attribution).
Retrieved text is passed to models as untrusted data (never instructions).
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from thinkfirst.config import get_settings
from thinkfirst.modules.rag import qdrant
from thinkfirst.modules.rag.embedder import DemoEmbedder, EmbeddingError, get_embedder
from thinkfirst.modules.rag.ingestion.extract import demo_embed
from thinkfirst.modules.rag.vector_store import store_for

log = logging.getLogger("thinkfirst.rag")


def embed(text: str) -> list[float]:
    """Postgres fallback vector (demo, 256-d). Always stored so search keeps working if Qdrant/HF are down."""
    return demo_embed(text)


def qdrant_active() -> bool:
    s = get_settings()
    if s.vector_backend == "postgres":
        return False
    return qdrant.healthy()


def stack() -> dict:
    e = get_embedder()
    return {"embedder": e.id, "dim": e.dim, "vector_db": "qdrant" if qdrant_active() else "pgvector/in-memory (fallback)"}


def _space() -> str:
    return "demo" if isinstance(get_embedder(), DemoEmbedder) else "semantic"


def thresholds(space: str) -> tuple[float, float]:
    """Score cut-offs depend on the embedding space (multilingual MiniLM cosine vs hashed bag-of-words)."""
    return (0.35, 0.40) if space == "semantic" else (0.12, 0.18)


# ---- indexing (called by ingestion and the resource agent) ----

def index_course_chunks(db: Session, chunks: list) -> int:
    if not chunks or not qdrant_active():
        return 0
    e = get_embedder()
    name = qdrant.collection_name(qdrant.COURSE, e.id, e.dim)
    try:
        qdrant.ensure_collection(name, e.dim, ("owner_id", "subject_id", "revision_id"))
        vecs = e.embed([c.text for c in chunks])
        qdrant.upsert(name, [{"id": c.id, "vector": v, "payload": {"owner_id": c.owner_id, "subject_id": c.subject_id,
                                                                    "revision_id": c.revision_id, "page": c.page_no}}
                             for c, v in zip(chunks, vecs, strict=True)])
        return len(chunks)
    except (EmbeddingError, qdrant.QdrantError, Exception) as exc:  # noqa: BLE001 — fallback keeps working
        log.info("course indexing fallback", extra={"error_code": type(exc).__name__})
        return 0


def index_library_chunks(db: Session, item, chunks: list) -> int:
    if not chunks or not qdrant_active():
        return 0
    e = get_embedder()
    name = qdrant.collection_name(qdrant.LIBRARY, e.id, e.dim)
    try:
        qdrant.ensure_collection(name, e.dim, ("licensed_content_id",))
        vecs = e.embed([f"{item.title}. {c.text}" for c in chunks])
        qdrant.upsert(name, [{"id": c.id, "vector": v, "payload": {"licensed_content_id": item.id}}
                             for c, v in zip(chunks, vecs, strict=True)])
        return len(chunks)
    except Exception as exc:  # noqa: BLE001
        log.info("library indexing fallback", extra={"error_code": type(exc).__name__})
        return 0


def delete_course_revision(revision_id: str) -> None:
    if not qdrant_active():
        return
    e = get_embedder()
    try:
        qdrant.delete(qdrant.collection_name(qdrant.COURSE, e.id, e.dim), {"revision_id": revision_id})
    except Exception as exc:  # noqa: BLE001
        log.info("qdrant delete failed", extra={"error_code": type(exc).__name__})


# ---- search ----

def _course(db: Session, owner_id: str, subject_id: str, query: str, k: int):
    """Returns (hits, space). Qdrant first; Postgres fallback (demo space) if Qdrant is down or has nothing yet."""
    if qdrant_active():
        from thinkfirst.modules.rag.ingestion.models import SourceChunk

        e = get_embedder()
        try:
            hits = qdrant.search(qdrant.collection_name(qdrant.COURSE, e.id, e.dim), e.embed([query])[0], k,
                                 {"owner_id": owner_id, "subject_id": subject_id})
            out = [(sc, row) for sc, cid in hits if (row := db.get(SourceChunk, cid)) is not None and row.owner_id == owner_id]
            if out:
                return out, _space()
        except Exception as exc:  # noqa: BLE001
            log.info("qdrant search fallback", extra={"error_code": type(exc).__name__})
    return store_for(db).search(db, owner_id, subject_id, embed(query), k), "demo"


def search_course(db: Session, owner_id: str, subject_id: str, query: str, k: int = 3):
    return _course(db, owner_id, subject_id, query, k)[0]


def search_open_courses(db: Session, owner_id: str, subject_id: str, query: str, max_chars: int = 3500) -> tuple[str, list[dict]]:
    from thinkfirst.modules.rag.agent import service as resources

    items = resources.for_subject(db, owner_id, subject_id)
    words = set(re.findall(r"\w{4,}", query.lower()))
    scored = sorted(items, key=lambda i: -len(words & set(re.findall(r"\w{4,}", (i.body or "").lower()))))
    text, cites = "", []
    for i in scored[:2]:
        if i.body:
            text += f"[{i.title}]\n{i.body[: max_chars // 2]}\n\n"
            cites.append(resources.public(i))
    return text.strip(), cites


def ground(db: Session, owner_id: str, subject_id: str, query: str) -> tuple[str, list[dict]]:
    """Course chunks first (if any), then open courses. Returns (context text, citations)."""
    hits = [(s, c) for s, c in search_course(db, owner_id, subject_id, query, k=3) if s >= 0.12]
    if hits:
        text = "\n\n".join(f"[page {c.page_no}]\n{c.text}" for _, c in hits)
        return text, [{"kind": "course", "chunk_id": c.id, "page": c.page_no, "quote": c.text[:240]} for _, c in hits]
    return search_open_courses(db, owner_id, subject_id, query)


# ---------------- hybrid retrieval: local course -> shared library -> live fetch ----------------



def search_library(db: Session, query: str, k: int = 4) -> list[tuple[float, object]]:
    return _library(db, query, k)[0]


def _library(db: Session, query: str, k: int = 4):
    """Vector search over the SHARED open library (public, openly licensed content only). Returns (hits, space)."""
    from sqlalchemy import select, text

    from thinkfirst.modules.rag.library.models import SharedChunk

    if qdrant_active():
        e = get_embedder()
        try:
            hits = qdrant.search(qdrant.collection_name(qdrant.LIBRARY, e.id, e.dim), e.embed([query])[0], k)
            rows = [(s, db.get(SharedChunk, cid)) for s, cid in hits]
            rows = [(s, r) for s, r in rows if r is not None]
            if rows:
                return rows, _space()
        except Exception as exc:  # noqa: BLE001
            log.info("qdrant library fallback", extra={"error_code": type(exc).__name__})
    vec = embed(query)
    if db.get_bind().dialect.name == "postgresql":
        lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        rows = db.execute(text("select id, 1 - (embedding <=> cast(:q as vector)) from knowledge_library.shared_chunks "
                               "where embedding is not null order by embedding <=> cast(:q as vector) limit :k"),
                          {"q": lit, "k": k}).all()
        return [(float(sc), db.get(SharedChunk, cid)) for cid, sc in rows], "demo"
    rows = db.scalars(select(SharedChunk)).all()
    return sorted(((sum(x * y for x, y in zip(vec, r.embedding or [], strict=False)), r) for r in rows), key=lambda t: -t[0])[:k], "demo"


def hybrid(db: Session, owner_id: str, subject_id: str, query: str, fetch_query: str | None = None) -> dict:
    """1) the student's own course chunks; 2) the shared library built from earlier fetches (any user);
    3) only if nothing relevant exists, the resource agent fetches open content live, stores it for everyone, and we
    search again. `fetch_query` must be a concept/topic name — never the student's own text."""
    from thinkfirst.modules.rag.agent import service as resources
    from thinkfirst.modules.rag.library.models import LicensedContent

    hits_c, space = _course(db, owner_id, subject_id, query, 3)
    local = [(s, c) for s, c in hits_c if s >= thresholds(space)[0]]
    if local:
        return {"route": "course", "text": "\n\n".join(f"[page {c.page_no}]\n{c.text}" for _, c in local),
                "citations": [{"kind": "course", "chunk_id": c.id, "page": c.page_no, "quote": c.text[:240]} for _, c in local]}
    lib, space = _library(db, query)
    hits = [(s, c) for s, c in lib if c is not None and s >= thresholds(space)[1]]
    route = "library"
    if not hits and fetch_query:
        if resources.discover(db, owner_id, subject_id, fetch_query):
            route = "live-fetch"
            lib, space = _library(db, query)
            hits = [(s, c) for s, c in lib if c is not None and s >= thresholds(space)[1] * 0.75]
    if not hits:
        return {"route": "none", "text": "", "citations": []}
    seen, cites, text = set(), [], []
    for _, c in hits[:3]:
        item = db.get(LicensedContent, c.licensed_content_id)
        if item is None:
            continue
        resources.link(db, owner_id, subject_id, item, fetch_query or query)
        text.append(f"[{item.title}]\n{c.text}")
        if item.id not in seen:
            seen.add(item.id)
            cites.append({**resources.public(item), "kind": "open", "chunk_id": c.id, "quote": c.text[:240]})
    return {"route": route, "text": "\n\n".join(text), "citations": cites}


def store_name(db: Session) -> str:
    return store_for(db).name
