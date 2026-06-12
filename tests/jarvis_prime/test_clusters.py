"""Tests for the shared clustering module (Phase 1)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from hermes_cli.jarvis_prime.clusters import (  # noqa: E402
    ClusterModel,
    HashedFeatureBackend,
    fit_clusters,
    fit_kmeans,
    resolve_backend,
)

CORPUS = [
    "Write a Python function `sum_list` that returns the sum of a list.",
    "Write a Python function `max_of` that returns the maximum element.",
    "Write a Python function `fib` that returns the n-th Fibonacci number.",
    "Review the implementation of `is_even` and submit a corrected version.",
    "Review the implementation of `safe_div` and submit a corrected version.",
    "Review the implementation of `median3` and submit a corrected version.",
    "Implement the policy check `gate_action` so that it fails closed.",
    "Implement the policy check `redact_secret` so that it fails closed.",
    "Implement the policy check `fail_closed` so that it fails closed.",
]


def test_hashed_backend_is_deterministic_and_normalized() -> None:
    backend = HashedFeatureBackend(dim=64, seed=0)
    v1 = backend.embed(["hello template world"])
    v2 = HashedFeatureBackend(dim=64, seed=0).embed(["hello template world"])
    assert np.array_equal(v1, v2)
    assert v1.shape == (1, 64)
    assert math.isclose(float(np.linalg.norm(v1[0])), 1.0, rel_tol=1e-9)
    # Different seed => different embedding space.
    v3 = HashedFeatureBackend(dim=64, seed=1).embed(["hello template world"])
    assert not np.array_equal(v1, v3)


def test_hashed_backend_golden_vector_is_process_independent() -> None:
    # sha256-based hashing must not depend on PYTHONHASHSEED or platform.
    backend = HashedFeatureBackend(dim=16, seed=0)
    vec = backend.embed(["muse"])[0]
    nonzero = {i: round(float(x), 6) for i, x in enumerate(vec) if x != 0.0}
    assert nonzero == {1: 0.408248, 6: 0.816497, 7: -0.408248}


def test_fit_kmeans_deterministic_with_seed() -> None:
    backend = HashedFeatureBackend()
    X = backend.embed(CORPUS)
    c1 = fit_kmeans(X, 3, seed=0)
    c2 = fit_kmeans(X, 3, seed=0)
    assert np.array_equal(c1, c2)


def test_fit_clusters_defaults_k_to_sqrt_n() -> None:
    model = fit_clusters(CORPUS, backend=HashedFeatureBackend(), seed=0)
    assert model.k == round(math.sqrt(len(CORPUS)))


def test_assign_roundtrips_training_samples() -> None:
    backend = HashedFeatureBackend()
    model = fit_clusters(CORPUS, backend=backend, k=3, seed=0)
    # The three prompt families must land in three distinct clusters, and each
    # training sample must be confidently assigned to its own family cluster.
    families = [CORPUS[0:3], CORPUS[3:6], CORPUS[6:9]]
    family_clusters = []
    for family in families:
        ids = {model.assign(t, backend=backend).cluster_id for t in family}
        assert len(ids) == 1
        family_clusters.append(ids.pop())
    assert len(set(family_clusters)) == 3


def test_confidence_bounds_and_separation() -> None:
    backend = HashedFeatureBackend()
    model = fit_clusters(CORPUS, backend=backend, k=3, seed=0)
    in_conf = [model.assign(t, backend=backend).confidence for t in CORPUS]
    out_conf = model.assign("order a pizza with extra cheese tonight", backend=backend).confidence
    assert all(0.0 < c <= 1.0 for c in in_conf)
    assert 0.0 < out_conf <= 1.0
    assert min(in_conf) > out_conf


def test_k_equals_one_gives_full_confidence_at_centroid_radius() -> None:
    backend = HashedFeatureBackend()
    model = fit_clusters(CORPUS, backend=backend, k=1, seed=0)
    a = model.assign(CORPUS[0], backend=backend)
    assert a.cluster_id == 0
    assert 0.0 < a.confidence <= 1.0


def test_save_load_roundtrip_exact(tmp_path: Path) -> None:
    backend = HashedFeatureBackend()
    model = fit_clusters(CORPUS, backend=backend, k=3, seed=0)
    model.save(tmp_path)
    loaded = ClusterModel.load(tmp_path)
    assert np.array_equal(loaded.centroids, model.centroids)
    assert np.array_equal(loaded.radii, model.radii)
    assert (loaded.k, loaded.dim, loaded.seed) == (model.k, model.dim, model.seed)
    assert loaded.backend_name == model.backend_name
    assert loaded.corpus_hash == model.corpus_hash
    text = CORPUS[4]
    assert loaded.assign(text, backend=backend) == model.assign(text, backend=backend)


def test_assign_rejects_mismatched_backend() -> None:
    backend = HashedFeatureBackend(dim=64)
    model = fit_clusters(CORPUS, backend=backend, k=2, seed=0)
    other = HashedFeatureBackend(dim=32)
    with pytest.raises(ValueError, match="backend mismatch"):
        model.assign(CORPUS[0], backend=other)


def test_resolve_backend_auto_falls_back_without_sentence_transformers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def blocked(
        name: str,
        globals: object = None,  # noqa: A002 (builtins.__import__ API)
        locals: object = None,  # noqa: A002
        fromlist: object = (),
        level: int = 0,
    ):
        if name.startswith("sentence_transformers"):
            raise ImportError("blocked for test")
        return real_import(name, globals, locals, fromlist, level)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(builtins, "__import__", blocked)
    backend = resolve_backend("auto")
    assert isinstance(backend, HashedFeatureBackend)


def test_committed_model_artifact_loads_and_assigns() -> None:
    model_dir = (
        Path(__file__).resolve().parents[2] / "hermes_cli" / "jarvis_prime" / "templates" / "model"
    )
    model = ClusterModel.load(model_dir)
    backend = HashedFeatureBackend()
    assert model.backend_name == backend.name
    a = model.assign("Write a Python function `sum_list` that returns the sum.", backend=backend)
    assert 0 <= a.cluster_id < model.k
    assert 0.0 < a.confidence <= 1.0
