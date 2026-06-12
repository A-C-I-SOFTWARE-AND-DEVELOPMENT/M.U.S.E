"""Tests for the open-data-sources capability clusters.

Behavioral (not change-detector): no exact source/cluster counts are asserted —
only structural invariants, referential integrity, and a few flagship sources.
"""

from __future__ import annotations

from muse_cli.jarvis_prime import open_data_sources as ods
from muse_cli.jarvis_prime.research_vault import ResearchVault


def test_registry_and_clusters_load() -> None:
    sources = ods.load_registry()
    clusters = ods.load_clusters()
    assert sources and clusters
    # Every source carries a cluster, and it references a defined cluster id.
    cluster_id_set = {c.id for c in clusters}
    for s in sources:
        assert s.cluster, f"{s.key} has no cluster"
        assert s.cluster in cluster_id_set, f"{s.key} -> unknown cluster {s.cluster}"


def test_no_core_and_wall_overlap_and_license_set() -> None:
    for s in ods.load_registry():
        assert not (s.core_ingest and s.benchmark_wall), s.key
        assert s.legal_posture, s.key


def test_by_cluster_and_cluster_ids() -> None:
    sources = ods.load_registry()
    ids = ods.cluster_ids(sources)
    assert "agentic-tool-use" in ids
    agentic = ods.by_cluster("agentic-tool-use", sources=sources)
    assert agentic and all(s.cluster == "agentic-tool-use" for s in agentic)


def test_flagship_sources_present_with_permissive_posture() -> None:
    toucan = ods.get("toucan-1_5m")
    assert toucan is not None
    assert toucan.cluster == "agentic-tool-use"
    assert toucan.core_ingest and toucan.trainable
    assert toucan.legal_posture == "apache_2_0"

    xlam = ods.get("xlam-function-calling-60k")
    assert xlam is not None and xlam.legal_posture == "cc_by_4_0" and xlam.core_ingest


def test_every_cluster_has_at_least_one_source() -> None:
    sources = ods.load_registry()
    for c in ods.load_clusters():
        assert ods.by_cluster(c.id, sources=sources), f"cluster {c.id} is empty"


def test_new_cluster_sources_conservative_posture() -> None:
    # For the new (non-code) clusters, only clearly permissive licenses are
    # core-ingest. (The legacy code-github cluster keeps its own subset-based
    # conventions, e.g. The Stack v2 = mixed-but-core via permissive subsets.)
    for s in ods.load_registry():
        if s.cluster == "code-github":
            continue
        if s.legal_posture in ("verify_at_ingest", "mixed", "no_llm_training"):
            assert not s.core_ingest, f"{s.key} ({s.legal_posture}) must not be core_ingest"


def test_to_dict_includes_cluster() -> None:
    toucan = ods.get("toucan-1_5m")
    assert toucan is not None
    assert toucan.to_dict()["cluster"] == "agentic-tool-use"


def test_register_in_vault_tags_cluster() -> None:
    toucan = ods.get("toucan-1_5m")
    assert toucan is not None
    vault = ResearchVault()  # in-memory
    artifact = toucan.register_in_vault(vault, persist=False)
    assert "cluster:agentic-tool-use" in artifact.tags
    assert "open-data-source" in artifact.tags
