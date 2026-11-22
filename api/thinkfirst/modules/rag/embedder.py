"""Embedders for RAG.

- LocalEmbedder (default when `fastembed` is installed): the SAME model, run on this machine with ONNX Runtime
  (no cloud call, no credits, no token; ~0.22 GB downloaded once into MODEL_CACHE_DIR). Course text never leaves
  the server.
- HFEmbedder (when HF_TOKEN is set and no local runtime): Hugging Face Inference, model
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


_LOCAL: dict[str, object] = {}


class LocalEmbedder:
    def __init__(self, model: str, dim: int, cache_dir: str | None):
        from fastembed import TextEmbedding  # optional dependency

        self.model, self.dim = model, dim
        self.id = f"local:{model}"
        if model not in _LOCAL:  # load once per process (a few seconds; downloads the model the first time)
            _LOCAL[model] = TextEmbedding(model_name=model, cache_dir=cache_dir)
        self._m = _LOCAL[model]

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vecs = [_norm([float(x) for x in v]) for v in self._m.embed([t[:2000] for t in texts], batch_size=32)]
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingError("LOCAL_MODEL_ERROR") from exc
        if any(len(v) != self.dim for v in vecs):
            raise EmbeddingError("DIM_MISMATCH")
        return vecs


class DemoEmbedder:
    id, dim = "demo:hash-bow-256", 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [demo_embed(t) for t in texts]


def get_embedder() -> Embedder:
    """auto: local model > Hugging Face cloud (HF_TOKEN) > labelled demo embedder."""
    s = get_settings()
    if s.embedding_provider in ("auto", "local"):
        try:
            return LocalEmbedder(s.hf_embed_model, s.hf_embed_dim, s.model_cache_dir)
        except Exception as exc:  # noqa: BLE001 - fastembed not installed / model not downloadable
            log.warning("local embedder unavailable", extra={"error_code": type(exc).__name__})
    if s.embedding_provider in ("auto", "hf") and s.hf_token:
        return HFEmbedder(s.hf_token, s.hf_embed_model, s.hf_embed_dim)
    return DemoEmbedder()
