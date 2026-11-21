"""Embedders for RAG.

- HFEmbedder (default when HF_TOKEN is set): Hugging Face Inference, model
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-d, 50+ languages incl. French, English, Arabic —
  "courant" and "current" land close together). Vectors are L2-normalised so dot product == cosine.
- DemoEmbedder (fallback, labelled): hashed bag-of-words, 256-d, lexical only.

Privacy: chunk text is sent to Hugging Face only to compute vectors; nothing else is sent (OPEN_QUESTIONS Q-15).
"""

from __future__ import annotations

import logging
import math
import time
from typing import Protocol

import httpx

from thinkfirst.config import get_settings
from thinkfirst.modules.rag.ingestion.extract import demo_embed

log = logging.getLogger("thinkfirst.rag")
HF_URL = "https://router.huggingface.co/hf-inference/models/{model}/pipeline/feature-extraction"


class Embedder(Protocol):
    id: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingError(Exception):
    pass


def _norm(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _pool(v) -> list[float]:
    """Accept a pooled vector [d] or token vectors [[d]...] (mean-pool them)."""
    if v and isinstance(v[0], list):
        cols = len(v[0])
        return [sum(tok[i] for tok in v) / len(v) for i in range(cols)]
    return v


class HFEmbedder:
    def __init__(self, token: str, model: str, dim: int):
        self.token, self.model, self.dim = token, model, dim
        self.id = f"hf:{model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):  # batch
            batch = [t[:2000] for t in texts[i:i + 32]]
            for attempt in range(3):
                r = httpx.post(HF_URL.format(model=self.model), headers={"Authorization": f"Bearer {self.token}"},
                               json={"inputs": batch, "options": {"wait_for_model": True}}, timeout=60)
                if r.status_code in (429, 503) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if r.status_code >= 400:
                    raise EmbeddingError(f"HF_{r.status_code}")
                data = r.json()
                vecs = [_norm(_pool(v)) for v in data]
                if any(len(v) != self.dim for v in vecs):
                    raise EmbeddingError("DIM_MISMATCH")
                out.extend(vecs)
                break
        return out


class DemoEmbedder:
    id, dim = "demo:hash-bow-256", 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [demo_embed(t) for t in texts]


def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider in ("auto", "hf") and s.hf_token:
        return HFEmbedder(s.hf_token, s.hf_embed_model, s.hf_embed_dim)
    return DemoEmbedder()
