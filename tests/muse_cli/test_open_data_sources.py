"""Tests for the open data sources registry + Research Vault bridge."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import pytest

from muse_cli.jarvis_prime.open_data_sources import (
    NO_LLM_TRAINING,
    DatasetRole,
    DataSource,
    DEFAULT_REGISTRY_PATH,
    benchmark_wall_sources,
    core_ingest_sources,
    eval_only_sources,
    get,
    load_registry,
    register_all_in_vault,
)
from muse_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC = _REPO_ROOT / "docs" / "ai-intelligence" / "top-open-data-sources-for-training.md"


@pytest.fixture(scope="module")
def registry() -> list[DataSource]:
    return load_registry()


# --- registry integrity -----------------------------------------------------


def test_registry_loads_and_is_rank_sorted(registry):
    assert registry, "registry should not be empty"
    ranks = [s.rank for s in registry]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)  # unique ranks
    assert len({s.key for s in registry}) == len(registry)  # unique keys


def test_every_entry_has_valid_enums(registry):
    for s in registry:
        assert isinstance(s.role, DatasetRole)
        assert isinstance(s.evidence_strength, EvidenceStrength)
        assert s.name and s.key and s.legal_posture


def test_default_registry_path_points_at_shipped_yaml():
    assert DEFAULT_REGISTRY_PATH.exists()
    assert DEFAULT_REGISTRY_PATH.name == "open-data-sources.yaml"


def test_env_override_resolves_registry(tmp_path, monkeypatch):
    from muse_cli.jarvis_prime import open_data_sources as ods

    custom = tmp_path / "custom.yaml"
    custom.write_text(
        "sources:\n"
        "  - {rank: 1, key: only, name: Only, role: train, "
        "legal_posture: mit, evidence_strength: strong}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(ods.REGISTRY_PATH_ENV, str(custom))
    sources = load_registry()  # no explicit path -> uses env
    assert [s.key for s in sources] == ["only"]


def test_missing_registry_raises_actionable_error(monkeypatch):
    from muse_cli.jarvis_prime import open_data_sources as ods

    monkeypatch.delenv(ods.REGISTRY_PATH_ENV, raising=False)
    monkeypatch.setattr(ods, "_PACKAGED_REGISTRY_PATH", Path("/no/such/packaged.yaml"))
    monkeypatch.setattr(ods, "DEFAULT_REGISTRY_PATH", Path("/no/such/docs.yaml"))
    with pytest.raises(FileNotFoundError, match="open-data registry not found"):
        ods.resolve_registry_path()


def test_missing_required_field_raises():
    with pytest.raises(ValueError):
        DataSource.from_dict({"key": "x", "name": "X"})  # missing rank/role/etc.


def test_duplicate_rank_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "sources:\n"
        "  - {rank: 1, key: a, name: A, role: train, legal_posture: mit, evidence_strength: strong}\n"
        "  - {rank: 1, key: b, name: B, role: eval, legal_posture: mit, evidence_strength: strong}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate rank"):
        load_registry(bad)


# --- partitions -------------------------------------------------------------


def test_core_ingest_and_wall_are_nonempty(registry):
    assert core_ingest_sources(registry)
    assert benchmark_wall_sources(registry)
    assert eval_only_sources(registry)


def test_core_ingest_and_benchmark_wall_are_disjoint(registry):
    # A training source must never double as an eval-wall benchmark.
    core = {s.key for s in core_ingest_sources(registry)}
    wall = {s.key for s in benchmark_wall_sources(registry)}
    assert core.isdisjoint(wall)


def test_documented_core_and_wall_members_present(registry):
    keys = {s.key for s in registry}
    expected_core = {
        # code-github cluster
        "the-stack-v2",
        "github-bigquery",
        "gh-archive",
        "software-heritage-graph",
        "swe-smith",
        "project-codenet",
        "the-vault",
        "commitpackft",
        "d2a",
        "travistorrent",
        # v2 capability clusters (permissive core-ingest sources)
        "toucan-1_5m",
        "xlam-function-calling-60k",
        "smoltalk",
        "openr1-math-220k",
        "openthoughts2-1m",
        "numinamath-cot",
        "asqa",
        "helpsteer3",
    }
    expected_wall = {
        "swe-bench",
        "aacr-bench",
        "repobench",
        "crosscodeeval",
        "bigcodebench",
        "evalplus",
    }
    assert expected_core <= keys
    assert expected_wall <= keys
    assert {s.key for s in core_ingest_sources(registry)} == expected_core
    assert {s.key for s in benchmark_wall_sources(registry)} == expected_wall


def test_get_returns_known_source_and_none_for_unknown(registry):
    stack = get("the-stack-v2", sources=registry)
    assert stack is not None
    assert stack.name == "The Stack v2"
    assert get("does-not-exist", sources=registry) is None


def test_benchmark_wall_sources_are_not_trainable(registry):
    for s in benchmark_wall_sources(registry):
        assert not s.trainable


# --- Research Vault bridge ---------------------------------------------------


def test_register_in_vault_sets_type_and_evidence(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    stack = get("the-stack-v2", sources=registry)
    assert stack is not None
    art = stack.register_in_vault(vault, persist=False)
    assert art.source_type == SourceType.REPO
    assert art.evidence_strength == stack.evidence_strength
    assert art.source_uri == stack.source_uris[0]
    assert "open-data-source" in art.tags

    wall_src = get("swe-bench", sources=registry)
    assert wall_src is not None
    wart = wall_src.register_in_vault(vault, persist=False)
    assert wart.source_type == SourceType.BENCHMARK
    assert "benchmark-wall" in wart.tags


def test_source_without_uri_uses_registry_placeholder(registry):
    aacr = get("aacr-bench", sources=registry)
    assert aacr is not None
    assert aacr.source_uris == ()
    assert aacr.vault_source_uri == "registry://open-data/aacr-bench"


def test_register_all_skips_no_llm_training_by_default(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    result = register_all_in_vault(vault, sources=registry, persist=True)

    skipped_keys = {k for k, _ in result.skipped}
    assert "stackexchange-dump" in skipped_keys
    # The skipped source is the no_llm_training one.
    so = get("stackexchange-dump", sources=registry)
    assert so is not None
    assert so.legal_posture == NO_LLM_TRAINING
    # Everything else got registered.
    assert len(result.registered) == len(registry) - len(skipped_keys)


def test_register_all_include_restricted(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    result = register_all_in_vault(
        vault, sources=registry, include_restricted=True, persist=True
    )
    assert not result.skipped
    assert len(result.registered) == len(registry)


def test_register_all_persists_with_0600(tmp_path, registry):
    target = tmp_path / "rvault.jsonl"
    vault = ResearchVault(path=target)
    register_all_in_vault(vault, sources=registry, persist=True)
    assert target.exists()
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600


# --- doc / registry consistency ---------------------------------------------


def test_doc_references_every_registry_key(registry):
    """Guards drift between the prose table and the YAML registry: every key
    in the registry must appear in the narrative doc."""
    text = _DOC.read_text(encoding="utf-8")
    for s in registry:
        assert f"`{s.key}`" in text, f"{s.key} missing from {_DOC.name}"


def test_doc_has_no_research_tool_citation_tokens():
    text = _DOC.read_text(encoding="utf-8")
    assert not re.search(r"cite\s*turn", text)
    assert "citeturn" not in text
