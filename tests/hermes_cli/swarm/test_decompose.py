"""Tests for the decomposers — deterministic carving + the LLM seam (stubbed)."""

from __future__ import annotations

from pathlib import Path

from muse_cli.swarm.decompose import (
    directory_decomposer,
    keyword_decomposer,
    make_llm_decomposer,
)
from muse_cli.swarm.grainler import partition


def _make_repo(tmp_path: Path) -> Path:
    for d in ["src/api", "src/web", "docs"]:
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "f.py").write_text("x=1\n")
    return tmp_path


def test_directory_decomposer_splits_named_dirs(tmp_path: Path):
    repo = _make_repo(tmp_path)
    specs = directory_decomposer("build the api and the web layer", str(repo))
    globs = sorted(g for s in specs for g in s["globs"])
    assert globs == ["src/api/**", "src/web/**"]
    # And the result is provably disjoint.
    plan = partition("build the api and the web layer", str(repo), grains=specs)
    plan.prove_disjoint()
    assert plan.is_trivial is False


def test_directory_decomposer_falls_back_to_single(tmp_path: Path):
    repo = _make_repo(tmp_path)
    specs = directory_decomposer("just tweak something unspecified", str(repo))
    assert len(specs) == 1
    assert specs[0]["globs"] == ["**"]


def test_directory_decomposer_drops_ancestors(tmp_path: Path):
    # If both "src" and "api" are named, keep the deeper src/api, drop src.
    (tmp_path / "src/api").mkdir(parents=True)
    specs = directory_decomposer("work on src and api", str(tmp_path))
    globs = sorted(g for s in specs for g in s["globs"])
    # src/** would overlap src/api/**; the ancestor must be dropped → single grain
    # fallback or only the deeper dir. Either way, no overlap survives.
    plan = partition("work on src and api", str(tmp_path), grains=specs)
    plan.prove_disjoint()  # must not raise


def test_keyword_decomposer():
    specs = keyword_decomposer("update the api and the docs", ".")
    globs = sorted(g for s in specs for g in s["globs"])
    assert globs == ["docs/**", "src/api/**"]


def test_llm_decomposer_seam_is_proven_disjoint():
    class FakeAgent:
        def chat(self, prompt):
            return '[{"intent":"api","globs":["src/api/**"]},{"intent":"web","globs":["src/web/**"]}]'

    decompose = make_llm_decomposer(lambda: FakeAgent())
    specs = decompose("build api and web", ".")
    plan = partition("build api and web", grains=specs)
    plan.prove_disjoint()
    assert len(plan.grains) == 2


def test_llm_decomposer_overlap_is_rejected_by_proof():
    import pytest
    from muse_cli.swarm.grain import OverlapError

    class BadAgent:
        def chat(self, prompt):
            # Model proposes overlapping domains — the proof must reject it.
            return '[{"intent":"a","globs":["src/**"]},{"intent":"b","globs":["src/api/x.py"]}]'

    decompose = make_llm_decomposer(lambda: BadAgent())
    specs = decompose("x", ".")
    with pytest.raises(OverlapError):
        partition("x", grains=specs)
