"""Shared clustering for the template fast path (and any future routing).

One module owns: text embedding (swappable backend), deterministic KMeans
fitting (``k = round(sqrt(N))`` default), confidence-scored assignment, and
persistence. Used by template mining (Phase 2) and the runtime fast-path gate
(Phase 3) so both always agree on cluster ids.

Backends:

- ``MiniLMBackend`` — sentence-transformers ``all-MiniLM-L6-v2`` when the
  package and weights are available.
- ``HashedFeatureBackend`` — offline-deterministic char-n-gram/token hashing
  (sha256-based, hash-seed independent); the fallback wherever model weights
  cannot be downloaded (this container, Termux).

KMeans is implemented on numpy directly (scikit-learn is not a repo
dependency): kmeans++ seeding from ``np.random.default_rng(seed)``, ``n_init``
restarts with ``seed + i``, lowest inertia wins, ties broken by restart index —
fully deterministic. HDBSCAN is deliberately not the default: on text
embeddings it discards too many points as noise.

numpy ships in the ``[embeddings]`` extra; install with
``uv pip install -e ".[embeddings]"`` if :class:`ClustersUnavailableError`
is raised.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol, Sequence

if TYPE_CHECKING:  # pragma: no cover - typing only
    import numpy as np

MODEL_NPZ = "centroids.npz"
MODEL_META = "meta.json"


class ClustersUnavailableError(RuntimeError):
    """numpy (the ``[embeddings]`` extra) is not installed."""


def _np() -> Any:
    try:
        import numpy
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise ClustersUnavailableError(
            "clusters requires numpy — install the embeddings extra: "
            'uv pip install -e ".[embeddings]"'
        ) from exc
    return numpy


class EmbeddingBackend(Protocol):
    """Maps texts to L2-normalized vectors of a fixed dimension."""

    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> "np.ndarray": ...


class HashedFeatureBackend:
    """Offline-deterministic embedding: hashed char 3–5-grams + word tokens.

    sha256 bucket hashing with a sign bit, then L2 normalization. Independent
    of ``PYTHONHASHSEED`` and identical across processes/platforms — the
    backend of record wherever sentence-transformers weights are unavailable.
    """

    def __init__(self, *, dim: int = 256, seed: int = 0) -> None:
        self.dim = dim
        self.seed = seed
        self.name = f"hashed-ngram-d{dim}-s{seed}"

    def _features(self, text: str) -> list[str]:
        low = " ".join(text.lower().split())
        feats = [f"w:{tok}" for tok in low.split()]
        for n in (3, 4, 5):
            feats.extend(f"g{n}:{low[i:i + n]}" for i in range(max(0, len(low) - n + 1)))
        return feats

    def embed(self, texts: Sequence[str]) -> "np.ndarray":
        np = _np()
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for row, text in enumerate(texts):
            for feat in self._features(text):
                digest = hashlib.sha256(f"{self.seed}:{feat}".encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dim
                sign = 1.0 if digest[4] & 1 else -1.0
                out[row, bucket] += sign
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return out / norms


class MiniLMBackend:
    """sentence-transformers backend (lazy import; weights need network/HF)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # ty: ignore[unresolved-import]

        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension() or 384)
        self.name = f"minilm:{model_name}"

    def embed(self, texts: Sequence[str]) -> "np.ndarray":
        np = _np()
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float64)


def resolve_backend(prefer: str = "auto") -> EmbeddingBackend:
    """Return the preferred embedding backend, falling back deterministically.

    ``"minilm"`` forces sentence-transformers (raises if unavailable);
    ``"hashed"`` forces the offline backend; ``"auto"`` tries MiniLM and falls
    back to hashed on any import/download failure.
    """

    if prefer == "hashed":
        return HashedFeatureBackend()
    if prefer == "minilm":
        return MiniLMBackend()
    if prefer != "auto":
        raise ValueError(f"unknown backend preference {prefer!r}")
    try:
        return MiniLMBackend()
    except Exception:
        return HashedFeatureBackend()


@dataclass(frozen=True)
class ClusterAssignment:
    cluster_id: int
    confidence: float  # in (0, 1]; normalized inverse centroid distance
    distance: float


def fit_kmeans(
    X: "np.ndarray",
    k: int,
    *,
    seed: int = 0,
    n_init: int = 4,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> "np.ndarray":
    """Deterministic kmeans++ KMeans; returns the (k, dim) centroid matrix."""

    np = _np()
    X = np.asarray(X, dtype=np.float64)
    n = X.shape[0]
    if not 1 <= k <= n:
        raise ValueError(f"k={k} out of range for {n} points")

    def one_run(run_seed: int) -> tuple[float, "np.ndarray"]:
        rng = np.random.default_rng(run_seed)
        # kmeans++ seeding
        centroids = [X[rng.integers(n)]]
        for _ in range(1, k):
            d2 = np.min(
                ((X[:, None, :] - np.asarray(centroids)[None, :, :]) ** 2).sum(axis=2),
                axis=1,
            )
            total = float(d2.sum())
            if total <= 0.0:
                centroids.append(X[rng.integers(n)])
                continue
            centroids.append(X[np.searchsorted(np.cumsum(d2 / total), rng.random())])
        C = np.asarray(centroids)
        for _ in range(max_iter):
            d2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
            labels = d2.argmin(axis=1)
            new_C = C.copy()
            for j in range(k):
                members = X[labels == j]
                if len(members):
                    new_C[j] = members.mean(axis=0)
            shift = float(((new_C - C) ** 2).sum())
            C = new_C
            if shift <= tol:
                break
        inertia = float(((X - C[labels]) ** 2).sum())
        return inertia, C

    best: Optional[tuple[float, "np.ndarray"]] = None
    for i in range(n_init):
        inertia, C = one_run(seed + i)
        if best is None or inertia < best[0]:
            best = (inertia, C)
    assert best is not None
    return best[1]


@dataclass(frozen=True)
class ClusterModel:
    centroids: "np.ndarray"  # (k, dim)
    radii: "np.ndarray"  # (k,) mean member→centroid distance at fit time
    k: int
    dim: int
    seed: int
    backend_name: str
    n_texts: int
    corpus_hash: str
    created_at: str

    def assign_vector(self, vec: "np.ndarray") -> ClusterAssignment:
        """Assign with radius-calibrated confidence.

        ``confidence = r / (r + max(d - r, 0))`` where ``r`` is the cluster's
        fitted radius (typical member→centroid distance) and ``d`` the query's
        distance — an inverse distance normalized per cluster, in (0, 1]:
        1.0 at-or-inside the typical radius, 0.75 at ``d = 4r/3``, 0.5 at
        ``d = 2r``. This keeps the spec's τ=0.75 gate meaningful (a raw
        softmax over inverse distances compresses everything to ≈1/k).
        """

        np = _np()
        distances = np.linalg.norm(self.centroids - np.asarray(vec, dtype=np.float64), axis=1)
        nearest = int(distances.argmin())
        d = float(distances[nearest])
        positive = self.radii[self.radii > 0.0]
        floor = float(positive.min()) if len(positive) else 1e-6
        r = max(float(self.radii[nearest]), floor, 1e-6)
        confidence = r / (r + max(d - r, 0.0))
        return ClusterAssignment(nearest, float(confidence), d)

    def assign(self, text: str, *, backend: EmbeddingBackend) -> ClusterAssignment:
        if backend.name != self.backend_name:
            raise ValueError(
                f"backend mismatch: model fitted with {self.backend_name!r}, "
                f"got {backend.name!r}"
            )
        return self.assign_vector(backend.embed([text])[0])

    def save(self, directory: Path) -> None:
        np = _np()
        directory.mkdir(parents=True, exist_ok=True)
        np.savez(directory / MODEL_NPZ, centroids=self.centroids, radii=self.radii)
        meta = {
            "v": 1,
            "k": self.k,
            "dim": self.dim,
            "seed": self.seed,
            "backend_name": self.backend_name,
            "n_texts": self.n_texts,
            "corpus_hash": self.corpus_hash,
            "created_at": self.created_at,
        }
        (directory / MODEL_META).write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path) -> "ClusterModel":
        np = _np()
        meta = json.loads((directory / MODEL_META).read_text(encoding="utf-8"))
        with np.load(directory / MODEL_NPZ) as data:
            centroids = data["centroids"]
            radii = data["radii"]
        return cls(
            centroids=centroids,
            radii=radii,
            k=int(meta["k"]),
            dim=int(meta["dim"]),
            seed=int(meta["seed"]),
            backend_name=str(meta["backend_name"]),
            n_texts=int(meta["n_texts"]),
            corpus_hash=str(meta["corpus_hash"]),
            created_at=str(meta["created_at"]),
        )


def fit_clusters(
    texts: Sequence[str],
    *,
    backend: Optional[EmbeddingBackend] = None,
    k: Optional[int] = None,
    seed: int = 0,
) -> ClusterModel:
    """Embed ``texts`` and fit a deterministic KMeans cluster model."""

    if not texts:
        raise ValueError("cannot fit clusters on an empty corpus")
    backend = backend or resolve_backend()
    X = backend.embed(texts)
    n = len(texts)
    k_eff = k if k is not None else max(1, round(math.sqrt(n)))
    k_eff = min(k_eff, n)
    np = _np()
    centroids = fit_kmeans(X, k_eff, seed=seed)
    distances = np.linalg.norm(X[:, None, :] - centroids[None, :, :], axis=2)
    labels = distances.argmin(axis=1)
    radii = np.zeros(k_eff, dtype=np.float64)
    for j in range(k_eff):
        member_d = distances[labels == j, j]
        if len(member_d):
            radii[j] = float(member_d.mean())
    corpus_hash = hashlib.sha256("\x00".join(texts).encode("utf-8")).hexdigest()
    return ClusterModel(
        centroids=centroids,
        radii=radii,
        k=k_eff,
        dim=int(X.shape[1]),
        seed=seed,
        backend_name=backend.name,
        n_texts=n,
        corpus_hash=corpus_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


__all__ = [
    "ClustersUnavailableError",
    "EmbeddingBackend",
    "HashedFeatureBackend",
    "MiniLMBackend",
    "resolve_backend",
    "ClusterAssignment",
    "ClusterModel",
    "fit_kmeans",
    "fit_clusters",
]
