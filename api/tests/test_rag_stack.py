"""RAG stack: HF embedder (mocked HTTP) and Qdrant (real, when QDRANT_TEST_URL is set — e.g. the docker service)."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from thinkfirst.modules.rag import embedder as emb


def test_hf_embedder_batches_pools_and_normalises(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(len(json["inputs"]))
        assert headers["Authorization"] == "Bearer hf_test" and "paraphrase-multilingual" in url
        data = [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]] if i % 2 else [3.0, 4.0, 0.0] for i in range(len(json["inputs"]))]
        return httpx.Response(200, json=data)

    monkeypatch.setattr(emb.httpx, "post", fake_post)
    e = emb.HFEmbedder("hf_test", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 3)
    vecs = e.embed([f"t{i}" for i in range(40)])
    assert calls == [32, 8] and len(vecs) == 40
    assert vecs[0] == pytest.approx([0.6, 0.8, 0.0])  # normalised
    assert vecs[1] == pytest.approx([0.7071, 0.7071, 0.0], abs=1e-3)  # token vectors mean-pooled


def test_hf_embedder_errors_are_typed(monkeypatch):
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: httpx.Response(401, json={"error": "bad token"}))
    with pytest.raises(emb.EmbeddingError):
        emb.HFEmbedder("bad", "m", 384).embed(["x"])


def test_without_token_the_demo_embedder_is_used(monkeypatch):
    from thinkfirst.config import get_settings

    monkeypatch.setattr(get_settings(), "hf_token", None)
    assert isinstance(emb.get_embedder(), emb.DemoEmbedder)


QURL = os.environ.get("QDRANT_TEST_URL")


@pytest.mark.skipif(not QURL, reason="QDRANT_TEST_URL not set (real Qdrant test)")
def test_qdrant_filters_by_owner_and_subject(monkeypatch):
    from thinkfirst.config import get_settings
    from thinkfirst.modules.rag import qdrant

    monkeypatch.setattr(get_settings(), "qdrant_url", QURL)
    name = f"test_{uuid.uuid4().hex[:8]}"
    qdrant.ensure_collection(name, 3, ("owner_id", "subject_id"))
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    qdrant.upsert(name, [{"id": a, "vector": [1, 0, 0], "payload": {"owner_id": "u1", "subject_id": "s1"}},
                         {"id": b, "vector": [1, 0, 0], "payload": {"owner_id": "u2", "subject_id": "s1"}}])
    hits = qdrant.search(name, [1, 0, 0], 5, {"owner_id": "u1", "subject_id": "s1"})
    assert [h[1] for h in hits] == [a]  # the other student's identical vector is never returned
    qdrant.delete(name, {"owner_id": "u1"})
    assert qdrant.search(name, [1, 0, 0], 5, {"owner_id": "u1", "subject_id": "s1"}) == []
    with httpx.Client(base_url=QURL) as c:
        c.delete(f"/collections/{name}")
