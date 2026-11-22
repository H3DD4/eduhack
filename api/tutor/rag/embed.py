"""Embedders. Default is a multilingual hashing embedder (no model download, deterministic, offline).

auto picks: sentence-transformers (bge-m3 / multilingual-e5) when installed > Hugging Face Inference when
HF_TOKEN is set > hashing. Vectors are L2-normalised so dot product == cosine.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from ..config import TutorSettings
from ..textutil import norm, tokens


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashingEmbedder:
    """Feature hashing over stemmed words, word bigrams and character 4-grams (handles accents/typos)."""

    name = "hashing"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _h(self, s: str) -> tuple[int, float]:
        h = int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "little")
        return h % self.dim, (1.0 if (h >> 63) & 1 else -1.0)

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            toks = tokens(t)
            for w in toks:
                i, s = self._h("w:" + w)
                v[i] += s * 1.0
            for a, b in zip(toks, toks[1:]):
                i, s = self._h(f"b:{a}_{b}")
                v[i] += s * 0.6
            flat = " ".join(norm(w) for w in toks)
            for k in range(len(flat) - 3):
                g = flat[k: k + 4]
                if " " in g:
                    continue
                i, s = self._h("c:" + g)
                v[i] += s * 0.25
            out.append(_normalize(v))
        return out


class SentenceTransformerEmbedder:
    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model)
        self.name = f"st:{model}"
        self.dim = int(self.model.get_sentence_embedding_dimension())
        self.e5 = "e5" in model.lower()

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if self.e5:
            texts = [("query: " if query else "passage: ") + t for t in texts]
        vecs = self.model.encode(texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False)
        return [list(map(float, v)) for v in vecs]


class HFInferenceEmbedder:
    def __init__(self, model: str, token: str, dim: int = 1024):
        self.model, self.token, self.dim = model, token, dim
        self.name = f"hf:{model}"

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        from .. import http

        r = http.post(f"https://router.huggingface.co/hf-inference/models/{self.model}/pipeline/feature-extraction",
                      headers={"authorization": f"Bearer {self.token}"}, json={"inputs": texts}, timeout=60)
        if r.status >= 400:
            raise RuntimeError(f"HF_{r.status}")
        data = r.json()
        out = []
        for v in data:
            if v and isinstance(v[0], list):  # token embeddings -> mean pool
                v = [sum(col) / len(v) for col in zip(*v)]
            out.append(_normalize([float(x) for x in v]))
        self.dim = len(out[0]) if out else self.dim
        return out


def build_embedder(s: TutorSettings) -> Embedder:
    choice = s.embedder
    if choice in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder(s.embed_model)
        except Exception:  # noqa: BLE001 - not installed or model missing
            if choice == "sentence-transformers":
                raise
    if choice in ("auto", "hf") and s.hf_token:
        return HFInferenceEmbedder(s.embed_model, s.hf_token)
    return HashingEmbedder()
