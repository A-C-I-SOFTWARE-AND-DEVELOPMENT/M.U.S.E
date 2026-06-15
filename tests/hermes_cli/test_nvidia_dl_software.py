"""Tests for the NVIDIA Deep Learning Software registry + Research Vault bridge."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.nvidia_dl_software import (
    DEFAULT_REGISTRY_PATH,
    DevTool,
    ToolCategory,
    by_category,
    by_section,
    get,
    load_registry,
    register_all_in_vault,
    sections,
)
from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOC = _REPO_ROOT / "docs" / "ai-intelligence" / "nvidia-deep-learning-software.md"

_EXPECTED_KEYS = {
    "pytorch",
    "tensorflow",
    "jax",
    "tensorrt",
    "tensorrt-llm",
    "triton-inference-server",
    "tensorrt-model-optimizer",
    "tf-trt",
    "cudnn",
    "nccl",
    "dali",
    "nsight-systems",
    "dlprof",
    "kubernetes-on-nvidia-gpus",
    "nsight-compute",
    "feature-map-explorer",
}


@pytest.fixture(scope="module")
def registry() -> list[DevTool]:
    return load_registry()


# --- registry integrity -----------------------------------------------------


def test_registry_loads_and_is_rank_sorted(registry):
    assert registry, "registry should not be empty"
    ranks = [t.rank for t in registry]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)  # unique ranks
    assert len({t.key for t in registry}) == len(registry)  # unique keys


def test_every_entry_has_valid_enums(registry):
    for t in registry:
        assert isinstance(t.category, ToolCategory)
        assert isinstance(t.evidence_strength, EvidenceStrength)
        assert t.name and t.key and t.section and t.purpose


def test_default_registry_path_points_at_shipped_yaml():
    assert DEFAULT_REGISTRY_PATH.exists()
    assert DEFAULT_REGISTRY_PATH.name == "nvidia-deep-learning-software.yaml"


def test_env_override_resolves_registry(tmp_path, monkeypatch):
    from hermes_cli.jarvis_prime import nvidia_dl_software as nv

    custom = tmp_path / "custom.yaml"
    custom.write_text(
        "tools:\n"
        "  - {rank: 1, key: only, name: Only, section: Libraries, "
        "category: library, evidence_strength: strong, purpose: x}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(nv.REGISTRY_PATH_ENV, str(custom))
    tools = load_registry()  # no explicit path -> uses env
    assert [t.key for t in tools] == ["only"]


def test_missing_registry_raises_actionable_error(monkeypatch):
    from hermes_cli.jarvis_prime import nvidia_dl_software as nv

    monkeypatch.delenv(nv.REGISTRY_PATH_ENV, raising=False)
    monkeypatch.setattr(nv, "_PACKAGED_REGISTRY_PATH", Path("/no/such/packaged.yaml"))
    monkeypatch.setattr(nv, "DEFAULT_REGISTRY_PATH", Path("/no/such/docs.yaml"))
    with pytest.raises(FileNotFoundError, match="nvidia-dl-software registry not found"):
        nv.resolve_registry_path()


def test_missing_required_field_raises():
    with pytest.raises(ValueError):
        DevTool.from_dict({"key": "x", "name": "X"})  # missing rank/section/etc.


def test_duplicate_rank_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "tools:\n"
        "  - {rank: 1, key: a, name: A, section: Libraries, category: library, "
        "evidence_strength: strong}\n"
        "  - {rank: 1, key: b, name: B, section: Libraries, category: library, "
        "evidence_strength: strong}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate rank"):
        load_registry(bad)


def test_duplicate_key_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "tools:\n"
        "  - {rank: 1, key: a, name: A, section: Libraries, category: library, "
        "evidence_strength: strong}\n"
        "  - {rank: 2, key: a, name: B, section: Libraries, category: library, "
        "evidence_strength: strong}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate key"):
        load_registry(bad)


# --- partitions -------------------------------------------------------------


def test_all_expected_tools_present(registry):
    assert {t.key for t in registry} == _EXPECTED_KEYS


def test_developer_devops_tools_present(registry):
    # The five tools from the page section that prompted this capture.
    dev = {t.key for t in by_section("Developer and DevOps Tools", tools=registry)}
    assert dev == {
        "nsight-systems",
        "dlprof",
        "kubernetes-on-nvidia-gpus",
        "nsight-compute",
        "feature-map-explorer",
    }


def test_by_category(registry):
    profilers = {t.key for t in by_category(ToolCategory.PROFILER, tools=registry)}
    assert profilers == {"nsight-systems", "dlprof", "nsight-compute"}
    frameworks = {t.key for t in by_category(ToolCategory.FRAMEWORK, tools=registry)}
    assert frameworks == {"pytorch", "tensorflow", "jax"}


def test_sections_in_rank_order(registry):
    assert sections(registry) == [
        "Frameworks",
        "Inference",
        "Libraries",
        "Developer and DevOps Tools",
    ]


def test_get_returns_known_tool_and_none_for_unknown(registry):
    ncu = get("nsight-compute", tools=registry)
    assert ncu is not None
    assert ncu.name == "NVIDIA Nsight Compute"
    assert get("does-not-exist", tools=registry) is None


# --- Research Vault bridge ---------------------------------------------------


def test_register_in_vault_sets_type_and_evidence(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    ncu = get("nsight-compute", tools=registry)
    assert ncu is not None
    art = ncu.register_in_vault(vault, persist=False)
    assert art.source_type == SourceType.OFFICIAL_DOC
    assert art.evidence_strength == ncu.evidence_strength
    assert art.source_uri == ncu.vault_source_uri
    assert "nvidia-dl-software" in art.tags
    assert "license:proprietary" in art.tags
    assert "category:profiler" in art.tags


def test_register_in_vault_github_source_is_repo(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    trtllm = get("tensorrt-llm", tools=registry)
    assert trtllm is not None
    assert "github.com" in trtllm.vault_source_uri
    art = trtllm.register_in_vault(vault, persist=False)
    assert art.source_type == SourceType.REPO


def test_vault_source_uri_placeholder():
    tool = DevTool(
        rank=99,
        key="placeholder-tool",
        name="Placeholder",
        section="Libraries",
        category=ToolCategory.LIBRARY,
        evidence_strength=EvidenceStrength.VENDOR_REPORTED,
    )
    assert tool.vault_source_uri == "registry://nvidia-dl-software/placeholder-tool"


def test_register_all_registers_every_tool(tmp_path, registry):
    vault = ResearchVault(path=tmp_path / "rvault.jsonl")
    result = register_all_in_vault(vault, tools=registry, persist=True)
    assert not result.skipped
    assert len(result.registered) == len(registry)


def test_register_all_persists_with_0600(tmp_path, registry):
    target = tmp_path / "rvault.jsonl"
    vault = ResearchVault(path=target)
    register_all_in_vault(vault, tools=registry, persist=True)
    assert target.exists()
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600


# --- doc / registry consistency ---------------------------------------------


def test_doc_references_every_registry_key(registry):
    """Guards drift between the prose tables and the YAML registry: every key
    in the registry must appear in the narrative doc."""
    text = _DOC.read_text(encoding="utf-8")
    for t in registry:
        assert f"`{t.key}`" in text, f"{t.key} missing from {_DOC.name}"
