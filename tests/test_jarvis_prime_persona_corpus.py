"""Tests for hermes_cli.jarvis_prime.persona_corpus.

The bridge makes the Breadstick Ricky voice corpus retrievable: parse the
committed transcripts, bridge each into the Research Vault as a WEAK-evidence,
source-cited artifact, and keyword-search for quotable bits. These tests pin:

- parsing (title / video_id / url / transcript / character + theme tags);
- the vault bridge (source_uri = YouTube URL, video id as citation anchor,
  WEAK evidence, persona-corpus tag, license note);
- search scopes to persona-corpus artifacts and cites the right video;
- the real repo corpus loads and bridges without loss.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.persona_corpus import (
    CHANNEL_TAG,
    CORPUS_TAG,
    PersonaTranscript,
    load_corpus,
    parse_transcript,
    register_all_in_vault,
    resolve_corpus_dir,
    search_corpus,
)
from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)

_SAMPLE = """# A raise?! Best I can do is a honeybun Ricky.

- video_id: dptPjIPokNg
- url: https://www.youtube.com/watch?v=dptPjIPokNg
- channel: Breadstick Ricky & The Boss
- published: 2023-11-29
- length: 01:18
- views: 229.6K

## Transcript

listen boss I need a raise a raise go grab that 8ft ladder you can get as
high as you want to no no I need a raise in pay best I can do is a honey bun
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_transcript_extracts_metadata_and_body() -> None:
    t = parse_transcript(_SAMPLE, corpus_path="x.md")
    assert t is not None
    assert t.video_id == "dptPjIPokNg"
    assert t.title == "A raise?! Best I can do is a honeybun Ricky."
    assert t.url == "https://www.youtube.com/watch?v=dptPjIPokNg"
    assert t.published == "2023-11-29"
    assert t.transcript.startswith("listen boss I need a raise")
    assert t.word_count > 5


def test_parse_infers_characters_and_themes() -> None:
    t = parse_transcript(_SAMPLE, corpus_path="x.md")
    assert t is not None
    assert "ricky" in t.characters
    assert "pay" in t.themes  # "raise" / "pay" keyword


def test_parse_returns_none_without_transcript_section() -> None:
    assert parse_transcript("# Title\n\n- video_id: abc\n\nno section here") is None


def test_parse_returns_none_on_empty_transcript_body() -> None:
    assert parse_transcript("# T\n\n## Transcript\n\n   \n") is None


def test_video_id_hint_falls_back_when_metadata_missing() -> None:
    text = "# Untitled\n\n## Transcript\n\nsome words here that exist\n"
    t = parse_transcript(text, video_id_hint="ABC123hint")
    assert t is not None
    assert t.video_id == "ABC123hint"
    assert t.url == "https://www.youtube.com/watch?v=ABC123hint"


def test_register_in_vault_produces_cited_weak_artifact() -> None:
    t = parse_transcript(_SAMPLE, corpus_path="x.md")
    assert t is not None
    vault = ResearchVault(path=None)
    art = t.register_in_vault(vault, persist=False)
    assert art.source_uri == "https://www.youtube.com/watch?v=dptPjIPokNg"
    assert art.source_type == SourceType.BLOG
    assert art.evidence_strength == EvidenceStrength.WEAK
    assert art.citation_anchors == ("dptPjIPokNg",)
    assert CORPUS_TAG in art.tags and CHANNEL_TAG in art.tags
    assert "John Micheal Stewart" in art.license_notes
    # The transcript itself is the excerpt, so search can recall specific lines.
    assert "honey bun" in art.excerpt


def test_register_all_in_vault_from_a_temp_corpus(tmp_path: Path) -> None:
    _write(tmp_path, "dptPjIPokNg__raise.md", _SAMPLE)
    _write(
        tmp_path,
        "B1BDT3LOeuY__arthritis.md",
        "# Roscoe's arthritis!\n\n- video_id: B1BDT3LOeuY\n"
        "- url: https://www.youtube.com/watch?v=B1BDT3LOeuY\n\n"
        "## Transcript\n\nit's called arthritis okay and what is that\n",
    )
    vault = ResearchVault(path=None)
    result = register_all_in_vault(vault, corpus_dir=tmp_path, persist=False)
    assert result.count == 2
    assert not result.skipped
    assert len(vault.artifacts) == 2


def test_search_scopes_to_corpus_and_cites_video(tmp_path: Path) -> None:
    _write(tmp_path, "dptPjIPokNg__raise.md", _SAMPLE)
    # A non-corpus artifact must not leak into corpus search results.
    vault = ResearchVault(path=None)
    register_all_in_vault(vault, corpus_dir=tmp_path, persist=False)
    vault.add(
        title="Unrelated paper on honey production",
        source_uri="https://example.com/honey",
        excerpt="a honey bun is unrelated to apiculture honey research",
    )
    hits = search_corpus("honey bun raise", vault=vault, limit=5)
    assert hits, "expected at least one corpus hit"
    assert all(CORPUS_TAG in a.tags for a in hits)
    assert hits[0].citation_anchors == ("dptPjIPokNg",)


def test_search_builds_ephemeral_vault_when_none_given(tmp_path: Path) -> None:
    _write(tmp_path, "dptPjIPokNg__raise.md", _SAMPLE)
    hits = search_corpus("honey bun", corpus_dir=tmp_path, limit=3)
    assert hits and hits[0].citation_anchors == ("dptPjIPokNg",)


def test_corpus_dir_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_PERSONA_CORPUS_DIR", str(tmp_path))
    assert resolve_corpus_dir() == tmp_path


def test_load_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert load_corpus(tmp_path / "does-not-exist") == []


def test_real_repo_corpus_loads_and_bridges_without_loss() -> None:
    # Integration: the committed corpus should parse and bridge cleanly.
    transcripts = load_corpus()
    assert len(transcripts) >= 100, f"expected the full corpus, got {len(transcripts)}"
    assert all(t.transcript and t.video_id and t.url for t in transcripts)
    vault = ResearchVault(path=None)
    result = register_all_in_vault(vault, transcripts=transcripts, persist=False)
    assert result.count == len(transcripts)
    # A known skit is retrievable by its signature line.
    hits = search_corpus("honeybun raise", vault=vault, limit=5)
    assert any(a.citation_anchors == ("dptPjIPokNg",) for a in hits)


def test_persona_transcript_tags_are_flat_strings() -> None:
    t = PersonaTranscript(
        video_id="x", title="Ricky and Roscoe", url="u", transcript="hi there words",
        characters=("ricky", "roscoe"), themes=("pay",),
    )
    tags = t.tags()
    assert tags[0] == CORPUS_TAG and CHANNEL_TAG in tags
    assert "ricky" in tags and "roscoe" in tags and "pay" in tags
    assert all(isinstance(x, str) for x in tags)
