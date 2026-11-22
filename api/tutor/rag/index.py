"""Hybrid retrieval: BM25 + dense vectors, fused with Reciprocal Rank Fusion, optional cross-encoder rerank,
then MMR for diversity. Course chunks outrank web chunks (source priors) so material stays course-shaped."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..textutil import tokens

SOURCE_PRIOR = {"course": 1.0, "slides": 1.0, "notes": 0.95, "exercises": 1.0, "past_exam": 1.0,
                "solutions": 0.95, "other": 0.9, "web": 0.7}


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.72):
        self.k1, self.b = k1, b
        self.docs = docs
        self.n = len(docs)
        self.avgdl = sum(map(len, docs)) / self.n if self.n else 0.0
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, q: list[str]) -> list[float]:
        out = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i]) or 1
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out.append(s)
        return out


@dataclass
class Hit:
    chunk: dict[str, Any]
    score: float
    why: dict[str, float] = field(default_factory=dict)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


class HybridIndex:
    """In-memory index over a track's chunks. Rebuilt when the chunk set changes (cheap at course scale)."""

    def __init__(self, chunks: list[dict[str, Any]], embedder, reranker=None):
        self.chunks = chunks
        self.embedder = embedder
        self.reranker = reranker
        self.bm25 = BM25([tokens(c["text"] + " " + c.get("section", "")) for c in chunks])

    def search(self, query: str, *, k: int = 8, origin: str | None = None, doc_types: set[str] | None = None,
               concept_key: str | None = None, mmr_lambda: float = 0.72, rrf_k: int = 60) -> list[Hit]:
        if not self.chunks:
            return []
        idx = [i for i, c in enumerate(self.chunks)
               if (origin is None or c.get("origin") == origin)
               and (doc_types is None or c.get("doc_type") in doc_types)]
        if not idx:
            return []
        qv = self.embedder.embed([query], query=True)[0]
        bm = self.bm25.scores(tokens(query))
        dense = {i: _dot(qv, self.chunks[i]["embedding"]) for i in idx if self.chunks[i].get("embedding")}
        lex = {i: bm[i] for i in idx}
        rank_d = {i: r for r, i in enumerate(sorted(dense, key=lambda i: -dense[i]))}
        rank_l = {i: r for r, i in enumerate(sorted(lex, key=lambda i: -lex[i]))}
        fused: dict[int, float] = {}
        for i in idx:
            s = 0.0
            if i in rank_d:
                s += 1.0 / (rrf_k + rank_d[i])
            if lex[i] > 0:
                s += 1.0 / (rrf_k + rank_l[i])
            c = self.chunks[i]
            prior = SOURCE_PRIOR.get("web" if c.get("origin") == "web" else c.get("doc_type", "course"), 0.9)
            if concept_key and concept_key in (c.get("concept_ids") or []):
                prior *= 1.25
            fused[i] = s * prior
        pool = sorted(fused, key=lambda i: -fused[i])[: max(k * 4, 20)]
        if self.reranker is not None and pool:
            rr = self.reranker.score(query, [self.chunks[i]["text"] for i in pool])
            for i, s in zip(pool, rr, strict=False):
                fused[i] = fused[i] * 0.3 + s * 0.7
            pool.sort(key=lambda i: -fused[i])
        # MMR: relevance vs redundancy with already picked chunks
        picked: list[int] = []
        while pool and len(picked) < k:
            best, best_s = None, -1e9
            top = max(fused[i] for i in pool) or 1.0
            for i in pool:
                red = max((_dot(self.chunks[i].get("embedding") or [], self.chunks[j].get("embedding") or [])
                           for j in picked), default=0.0)
                s = mmr_lambda * (fused[i] / top) - (1 - mmr_lambda) * red
                if s > best_s:
                    best, best_s = i, s
            picked.append(best)  # type: ignore[arg-type]
            pool.remove(best)  # type: ignore[arg-type]
        return [Hit(self.chunks[i], fused[i], {"dense": dense.get(i, 0.0), "bm25": lex.get(i, 0.0)}) for i in picked]


class CrossEncoderReranker:
    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model)

    def score(self, query: str, texts: list[str]) -> list[float]:
        raw = self.model.predict([(query, t) for t in texts])
        return [1 / (1 + math.exp(-float(x))) for x in raw]


def build_reranker(s) -> CrossEncoderReranker | None:
    if s.reranker == "none":
        return None
    try:
        return CrossEncoderReranker(s.rerank_model)
    except Exception:  # noqa: BLE001
        if s.reranker == "cross-encoder":
            raise
        return None
