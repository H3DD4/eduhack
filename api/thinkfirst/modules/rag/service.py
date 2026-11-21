"""Module RAG — retrieval-augmented grounding for the tutor, lessons and checks.

Two collections, always cited:
1. the student's own course files (private chunks in the vector store, page-level citations);
2. "cours officiels" / open courses gathered by the resource agent (openly licensed text with attribution).
Retrieved text is passed to models as untrusted data (never instructions).
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from thinkfirst.modules.rag.ingestion.extract import demo_embed
from thinkfirst.modules.rag.vector_store import store_for

EMBEDDING_LABEL = "hashed bag-of-words (demo embedding; swap for a real embedding provider)"


def embed(text: str) -> list[float]:
    return demo_embed(text)


def search_course(db: Session, owner_id: str, subject_id: str, query: str, k: int = 3):
    return store_for(db).search(db, owner_id, subject_id, embed(query), k)


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

LOCAL_MIN, LIBRARY_MIN = 0.12, 0.18


def search_library(db: Session, query: str, k: int = 4) -> list[tuple[float, object]]:
    """Vector search over the SHARED open library (public, openly licensed content only)."""
    from sqlalchemy import select, text

    from thinkfirst.modules.rag.library.models import SharedChunk

    vec = embed(query)
    if db.get_bind().dialect.name == "postgresql":
        lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        rows = db.execute(text("select id, 1 - (embedding <=> cast(:q as vector)) from knowledge_library.shared_chunks "
                               "where embedding is not null order by embedding <=> cast(:q as vector) limit :k"),
                          {"q": lit, "k": k}).all()
        return [(float(sc), db.get(SharedChunk, cid)) for cid, sc in rows]
    rows = db.scalars(select(SharedChunk)).all()
    return sorted(((sum(x * y for x, y in zip(vec, r.embedding or [], strict=False)), r) for r in rows), key=lambda t: -t[0])[:k]


def hybrid(db: Session, owner_id: str, subject_id: str, query: str, fetch_query: str | None = None) -> dict:
    """1) the student's own course chunks; 2) the shared library built from earlier fetches (any user);
    3) only if nothing relevant exists, the resource agent fetches open content live, stores it for everyone, and we
    search again. `fetch_query` must be a concept/topic name — never the student's own text."""
    from thinkfirst.modules.rag.agent import service as resources
    from thinkfirst.modules.rag.library.models import LicensedContent

    local = [(s, c) for s, c in search_course(db, owner_id, subject_id, query, k=3) if s >= LOCAL_MIN]
    if local:
        return {"route": "course", "text": "\n\n".join(f"[page {c.page_no}]\n{c.text}" for _, c in local),
                "citations": [{"kind": "course", "chunk_id": c.id, "page": c.page_no, "quote": c.text[:240]} for _, c in local]}
    hits = [(s, c) for s, c in search_library(db, query) if c is not None and s >= LIBRARY_MIN]
    route = "library"
    if not hits and fetch_query:
        if resources.discover(db, owner_id, subject_id, fetch_query):
            route = "live-fetch"
            hits = [(s, c) for s, c in search_library(db, query) if c is not None and s >= LIBRARY_MIN * 0.75]
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
