"""Unit tests for the optional dense-embedding layer (pure-Python paths)."""

from __future__ import annotations

import math

from plugins.memory.holographic import embeddings as emb


def test_vector_byte_roundtrip():
    vec = [0.1, -0.5, 0.25, 1.0, -1.0]
    data = emb.vector_to_bytes(vec)
    back = emb.bytes_to_vector(data)
    assert len(back) == len(vec)
    for a, b in zip(vec, back):
        assert math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)


def test_bytes_to_vector_empty():
    assert emb.bytes_to_vector(b"") == []


def test_cosine_identity_and_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert math.isclose(emb.cosine(a, a), 1.0, abs_tol=1e-6)
    assert math.isclose(emb.cosine(a, b), 0.0, abs_tol=1e-6)
    # mismatched / empty inputs are safe
    assert emb.cosine([], a) == 0.0
    assert emb.cosine([1.0, 0.0], a) == 0.0


def test_make_backend_disabled_by_default():
    # No config, empty config, and explicitly-disabled config all yield None.
    assert emb.make_backend(None) is None
    assert emb.make_backend({}) is None
    assert emb.make_backend({"embeddings": {"enabled": False}}) is None


def test_make_backend_selects_named_backend():
    st = emb.make_backend({"embeddings": {"enabled": True, "backend": "sentence-transformers"}})
    assert isinstance(st, emb.SentenceTransformerBackend)

    api = emb.make_backend(
        {"embeddings": {"enabled": True, "backend": "openai", "base_url": "http://localhost:1234/v1"}}
    )
    assert isinstance(api, emb.OpenAIEmbeddingBackend)
    # A custom base_url is treated as available even without an API key.
    assert api.is_available() is True
