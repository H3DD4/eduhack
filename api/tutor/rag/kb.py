"""Knowledge base per track: stores chunks with embeddings and serves grounded CONTEXT to every agent."""

from __future__ import annotations

import threading
from typing import Any

from .index import Hit, HybridIndex


class KnowledgeBase:
    def __init__(self, store, embedder, reranker=None):
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self._idx: dict[str, tuple[int, HybridIndex]] = {}
        self._lock = threading.Lock()

    def add(self, chunks: list[dict[str, Any]], batch: int = 32) -> None:
        for i in range(0, len(chunks), batch):
            part = chunks[i: i + batch]
            vecs = self.embedder.embed([c["text"] for c in part])
            for c, v in zip(part, vecs):
                c["embedding"] = v
        self.store.put_many("chunks", chunks)
        for tid in {c["track_id"] for c in chunks}:
            self._idx.pop(tid, None)

    def chunks(self, track_id: str) -> list[dict[str, Any]]:
        return self.store.list("chunks", track_id=track_id)

    def index(self, track_id: str) -> HybridIndex:
        with self._lock:
            chunks = self.chunks(track_id)
            cached = self._idx.get(track_id)
            if cached and cached[0] == len(chunks):
                return cached[1]
            for c in chunks:  # chunks stored without vectors (e.g. imported) get embedded now
                if not c.get("embedding"):
                    c["embedding"] = self.embedder.embed([c["text"]])[0]
            idx = HybridIndex(chunks, self.embedder, self.reranker)
            self._idx[track_id] = (len(chunks), idx)
            return idx

    def invalidate(self, track_id: str) -> None:
        self._idx.pop(track_id, None)

    def search(self, track_id: str, query: str, **kw) -> list[Hit]:
        return self.index(track_id).search(query, **kw)

    def context(self, track_id: str, query: str, *, k: int = 8, **kw) -> list[dict[str, Any]]:
        """Prompt-ready context: id, text, section, page, origin, source label."""
        docs = {d["id"]: d for d in self.store.list("documents", track_id=track_id)}
        webs = {w["id"]: w for w in self.store.list("web_sources", track_id=track_id)}
        out = []
        for h in self.search(track_id, query, k=k, **kw):
            c = h.chunk
            if c.get("origin") == "web":
                w = webs.get(c.get("web_source_id") or "", {})
                src, url = f"{w.get('domain', 'web')} ({w.get('licence', 'unknown')})", w.get("url")
            else:
                d = docs.get(c.get("document_id") or "", {})
                src, url = d.get("title") or d.get("filename", "course"), None
            out.append({"id": c["id"], "text": c["text"], "section": c.get("section", ""), "page": c.get("page"),
                        "origin": c.get("origin", "course"), "doc_type": c.get("doc_type"), "source": src, "url": url})
        return out
