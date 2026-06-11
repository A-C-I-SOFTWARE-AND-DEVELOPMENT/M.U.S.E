"""Optional dense-embedding backends for holographic semantic recall.

This module is **fully optional**. If no backend is configured (the default),
or the chosen backend's dependencies are missing, the store and retriever
behave exactly as before: no embedding column is written and the hybrid
scorer adds no dense term. Semantic recall is purely additive.

Two backends are offered behind a config switch:

* :class:`OpenAIEmbeddingBackend` — reuses the already-present ``openai`` SDK
  (or any OpenAI-compatible ``base_url``). Zero new heavy dependencies.
* :class:`SentenceTransformerBackend` — fully offline local embeddings via the
  lazy ``memory.embeddings_local`` feature (``sentence-transformers``).

Vectors are stored unit-normalized as float32 blobs (mirroring the byte
serialization style of :mod:`holographic`), and similarity is a plain dot
product, so brute-force cosine over the small FTS5 candidate set is cheap and
needs no native vector-search extension.
"""

from __future__ import annotations

import logging
import math
import os
import struct
from abc import ABC, abstractmethod
from typing import Any

try:  # numpy is optional everywhere in this plugin
    import numpy as _np  # ty: ignore[unresolved-import]

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - exercised in numpy-absent CI
    _HAS_NUMPY = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialization + math helpers
# ---------------------------------------------------------------------------

def vector_to_bytes(vec: "list[float]") -> bytes:
    """Pack a float vector as little-endian float32 bytes."""
    return struct.pack(f"<{len(vec)}f", *vec)


def bytes_to_vector(data: bytes) -> "list[float]":
    """Unpack float32 bytes back into a Python list of floats."""
    if not data:
        return []
    return list(struct.unpack(f"<{len(data) // 4}f", data))


def _normalize(vec: "list[float]") -> "list[float]":
    """Return a unit-length copy of ``vec`` (no-op for a zero vector)."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm <= 0.0:
        return list(vec)
    return [x / norm for x in vec]


def cosine(a: "list[float]", b: "list[float]") -> float:
    """Cosine similarity. Assumes inputs are (or are near) unit-normalized.

    Falls back to a pure-Python dot product when numpy is unavailable.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    if _HAS_NUMPY:
        va = _np.asarray(a, dtype=_np.float64)
        vb = _np.asarray(b, dtype=_np.float64)
        na = float(_np.linalg.norm(va))
        nb = float(_np.linalg.norm(vb))
        if na <= 0.0 or nb <= 0.0:
            return 0.0
        return float(_np.dot(va, vb) / (na * nb))
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Backend interface
# ---------------------------------------------------------------------------

class EmbeddingBackend(ABC):
    """Pluggable text→vector backend. Implementations must be cheap to
    construct (no model load / network in ``__init__``); heavy work is
    deferred to the first :meth:`embed` call."""

    name: str = "base"
    dim: int = 0

    @abstractmethod
    def is_available(self) -> bool:
        """True if this backend can actually produce embeddings right now."""

    @abstractmethod
    def embed(self, text: str) -> "list[float] | None":
        """Return a unit-normalized vector, or ``None`` if unavailable/failed."""

    def embed_batch(self, texts: "list[str]") -> "list[list[float] | None]":
        return [self.embed(t) for t in texts]


class SentenceTransformerBackend(EmbeddingBackend):
    """Local, offline embeddings via ``sentence-transformers`` (lazy)."""

    name = "sentence-transformers"

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model
        self._model: Any = None
        self.dim = 0

    def is_available(self) -> bool:
        try:
            from tools.lazy_deps import is_available as _avail

            return _avail("memory.embeddings_local")
        except Exception:
            return False

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from tools.lazy_deps import ensure

        ensure("memory.embeddings_local", prompt=False)
        from sentence_transformers import SentenceTransformer  # ty: ignore[unresolved-import]

        self._model = SentenceTransformer(self.model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> "list[float] | None":
        if not text:
            return None
        try:
            self._ensure_model()
            vec = self._model.encode(text, normalize_embeddings=True)
            return [float(x) for x in vec]
        except Exception as exc:  # never let embedding break a memory write
            logger.debug("SentenceTransformer embed failed: %s", exc)
            return None


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """Embeddings via the OpenAI SDK or any OpenAI-compatible endpoint.

    Reuses the ``openai`` package that ships as a core dependency, so this
    backend adds no new install footprint.
    """

    name = "openai"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        base_url: "str | None" = None,
        api_key_env: str = "OPENAI_API_KEY",
    ) -> None:
        self.model_name = model
        self.base_url = base_url
        self.api_key_env = api_key_env
        self._client = None
        self.dim = 0

    def _api_key(self) -> "str | None":
        return os.environ.get(self.api_key_env) or os.environ.get("OPENAI_API_KEY")

    def is_available(self) -> bool:
        # A custom base_url may front a keyless local server, so only require
        # a key when talking to the default OpenAI endpoint.
        if self.base_url:
            return True
        return bool(self._api_key())

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI

        kwargs: dict = {}
        key = self._api_key()
        if key:
            kwargs["api_key"] = key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def embed(self, text: str) -> "list[float] | None":
        if not text:
            return None
        try:
            client = self._ensure_client()
            resp = client.embeddings.create(model=self.model_name, input=text)
            vec = list(resp.data[0].embedding)
            self.dim = len(vec)
            return _normalize([float(x) for x in vec])
        except Exception as exc:  # graceful: a failed call disables the term
            logger.debug("OpenAI embed failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_backend(config: "dict | None") -> "EmbeddingBackend | None":
    """Build the configured embedding backend, or ``None`` when disabled.

    ``config`` is the ``plugins.hermes-memory-store`` block. Embeddings live
    under an ``embeddings`` sub-key::

        embeddings:
          enabled: true
          backend: auto            # auto | openai | sentence-transformers
          model: ...               # backend-specific default if omitted
          base_url: null           # OpenAI-compatible endpoint (openai backend)
          api_key_env: OPENAI_API_KEY

    ``backend: auto`` prefers the API backend when a key/endpoint is present,
    otherwise the local backend when its deps are installed, otherwise returns
    ``None`` (semantic recall stays off).
    """
    emb = ((config or {}).get("embeddings") or {})
    if not emb.get("enabled", False):
        return None

    backend = str(emb.get("backend", "auto")).strip().lower()
    model = emb.get("model")
    base_url = emb.get("base_url")
    api_key_env = emb.get("api_key_env", "OPENAI_API_KEY")

    def _api() -> OpenAIEmbeddingBackend:
        return OpenAIEmbeddingBackend(
            model=model or "text-embedding-3-small",
            base_url=base_url,
            api_key_env=api_key_env,
        )

    def _local() -> SentenceTransformerBackend:
        return SentenceTransformerBackend(model=model or "all-MiniLM-L6-v2")

    if backend in ("openai", "api"):
        return _api()
    if backend in ("sentence-transformers", "local", "st"):
        return _local()

    # auto: API first (cheap, no model download) if it can run, else local.
    api_backend = _api()
    if api_backend.is_available():
        return api_backend
    local_backend = _local()
    if local_backend.is_available():
        return local_backend
    # Neither ready — leave a configured-but-not-installed local backend so a
    # first embed attempt can trigger the lazy install; if even that is
    # impossible the store simply records no embeddings.
    return local_backend
