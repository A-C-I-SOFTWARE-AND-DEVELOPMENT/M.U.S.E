"""prime research_vault — the evidence store's public entry points."""

from __future__ import annotations

import json

import pytest

from plugins.prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
    _checksum,
)


@pytest.fixture
def vault(tmp_path):
    return ResearchVault(path=tmp_path / "research_vault.jsonl")


def test_add_returns_a_stable_id_from_title_and_uri(vault):
    a = vault.add("GraphRAG", "https://example.invalid/p", persist=False)
    b = vault.add("GraphRAG", "https://example.invalid/p", persist=False)
    c = vault.add("GraphRAG", "https://example.invalid/other", persist=False)
    assert a.id == b.id != c.id
    assert len(vault.artifacts) == 2  # the re-add merged onto the same id


def test_summary_derives_only_from_the_stored_excerpt(vault):
    art = vault.add(
        "Paper",
        "https://example.invalid/p",
        excerpt="  Graphs   improve retrieval accuracy.  ",
        persist=False,
    )
    assert art.summary == "Graphs improve retrieval accuracy."
    assert art.excerpt == "Graphs   improve retrieval accuracy."


def test_an_explicit_summary_wins_over_the_excerpt(vault):
    art = vault.add(
        "Paper",
        "u",
        excerpt="a long verbatim quotation",
        summary="my own words",
        persist=False,
    )
    assert art.summary == "my own words"


def test_no_excerpt_means_no_summary_is_invented(vault):
    art = vault.add("Paper", "https://example.invalid/p", persist=False)
    assert art.summary == ""
    assert art.excerpt == ""


def test_long_excerpts_are_capped_not_paraphrased(vault):
    art = vault.add("Paper", "u", excerpt="word " * 200, persist=False)
    assert len(art.summary) == 200
    assert art.summary in " ".join(["word"] * 200)


def test_checksum_is_whitespace_canonical(vault):
    art = vault.add("Paper", "u", excerpt=" a  b \n c ", persist=False)
    assert art.checksum == _checksum("a b c")
    assert len(art.checksum) == 64


def test_defaults_are_conservative(vault):
    art = vault.add("Paper", "u", persist=False)
    assert art.source_type == SourceType.MANUAL
    assert art.evidence_strength == EvidenceStrength.MODERATE
    assert art.retrieved_at


def test_entries_are_ordered_and_filterable(vault):
    vault.add("Paper", "u1", source_type=SourceType.PAPER, persist=False)
    vault.add("Blog", "u2", source_type=SourceType.BLOG, persist=False)
    assert [a.title for a in vault.entries()] == ["Paper", "Blog"]
    assert [
        a.title for a in vault.entries(source_type=SourceType.BLOG)
    ] == ["Blog"]


def test_search_scores_across_title_summary_excerpt_and_tags(vault):
    vault.add(
        "GraphRAG paper",
        "u1",
        excerpt="Graphs improve retrieval.",
        tags=["retrieval"],
        persist=False,
    )
    vault.add("Unrelated", "u2", excerpt="Painting sheds.", persist=False)

    hits = vault.search("graphs retrieval")
    assert [a.title for a in hits] == ["GraphRAG paper"]
    assert vault.search("nothing matches here") == []
    assert len(vault.search("graphs", limit=1)) == 1


def test_persistence_round_trip(tmp_path):
    path = tmp_path / "research_vault.jsonl"
    vault = ResearchVault(path=path)
    art = vault.add(
        "Paper",
        "pkg/client.py",
        excerpt="Timeouts default to 30s.",
        evidence_strength=EvidenceStrength.PRIMARY,
        source_type=SourceType.REPO,
        tags=["timeout"],
        license_notes="CC-BY",
    )

    reloaded = ResearchVault.load(path)
    stored = reloaded.artifacts[art.id]
    assert stored.title == "Paper"
    assert stored.evidence_strength == EvidenceStrength.PRIMARY
    assert stored.source_type == SourceType.REPO
    assert stored.tags == ("timeout",)
    assert stored.license_notes == "CC-BY"
    assert stored.checksum == art.checksum
    assert reloaded.load_diagnostics == []


def test_loading_a_missing_file_is_empty(tmp_path):
    assert ResearchVault.load(tmp_path / "absent.jsonl").artifacts == {}


def test_malformed_lines_are_reported_not_fatal(tmp_path):
    path = tmp_path / "research_vault.jsonl"
    good = ResearchVault(path=path)
    good.add("Paper", "u")
    path.write_text(path.read_text() + "not json\n", encoding="utf-8")

    vault = ResearchVault.load(path)
    assert len(vault.artifacts) == 1
    assert len(vault.load_diagnostics) == 1


def test_old_records_without_retrieved_at_fall_back_to_added_at(tmp_path):
    path = tmp_path / "research_vault.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "abc",
                "title": "Legacy",
                "source_uri": "u",
                "added_at": "2020-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    art = ResearchVault.load(path).artifacts["abc"]
    assert art.retrieved_at == "2020-01-01T00:00:00+00:00"


def test_default_path_follows_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    ResearchVault().add("Paper", "u")
    assert (tmp_path / "prime" / "research_vault.jsonl").exists()


def test_export_markdown_lists_source_and_grade(vault):
    vault.add(
        "GraphRAG paper",
        "https://example.invalid/p",
        excerpt="Graphs improve retrieval.",
        evidence_strength=EvidenceStrength.PRIMARY,
        source_type=SourceType.PAPER,
        freshness_due="2030-01-01T00:00:00+00:00",
        persist=False,
    )
    md = vault.export_markdown()
    assert "# Research Vault" in md
    assert "## GraphRAG paper" in md
    assert "https://example.invalid/p (paper, primary)" in md
    assert "summary: Graphs improve retrieval." in md
    assert "freshness due: 2030-01-01" in md


def test_audit_cards_expose_the_reviewable_fields(vault):
    art = vault.add("Paper", "u", excerpt="A claim.", persist=False)
    card = vault.export_audit_cards()[0]
    assert card["id"] == art.id
    assert card["claim"] == "A claim."
    assert card["checksum"] == art.checksum
    assert set(card) >= {"source_uri", "evidence_strength", "retrieved_at"}


def test_artifact_dict_round_trips(vault):
    art = vault.add("Paper", "u", excerpt="A claim.", persist=False)
    from plugins.prime.research_vault import ResearchArtifact

    assert ResearchArtifact.from_dict(art.to_dict()).to_dict() == art.to_dict()
