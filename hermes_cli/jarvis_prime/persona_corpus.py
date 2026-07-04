"""Persona corpus bridge — make the Breadstick Ricky transcripts retrievable.

The voice corpus at ``docs/persona/ricky-and-the-boss/transcripts/`` (106
verbatim video transcripts, see ``docs/persona/ricky-and-the-boss/README.md``)
teaches muse *how to talk* (the default "Breadstick Ricky" register wired in
``persona.py``). This module makes muse able to *quote or riff on specific
bits* by bridging each transcript into the **Research Vault** as a
source-cited artifact — exactly the pattern ``open_data_sources`` uses for the
open-data registry. Once in the vault, the corpus is reachable via
``ResearchVault.search`` (BM25-style keyword recall) and, because the evidence
indexer pulls the vault into GraphRAG, via ``graph_query`` too.

Thin registry + bridge, mirroring ``open_data_sources``: it does **not**
download anything, re-implement the vault, or make network calls. It parses the
markdown transcripts already committed to the repo and reuses
``research_vault`` for storage/provenance.

The comedic material is the property of John Micheal Stewart (Breadstick Ricky
& The Boss); artifacts are graded WEAK evidence and carry a license note — they
are private voice-reference, not authoritative claims and not for republication.

Clean-room, stdlib-only. No network calls.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchArtifact,
    ResearchVault,
    SourceType,
)

# parents[2] climbs hermes_cli/jarvis_prime/ -> hermes_cli/ -> repo root,
# matching open_data_sources so the corpus resolves with or without HERMES_HOME.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_DIR = (
    _REPO_ROOT / "docs" / "persona" / "ricky-and-the-boss" / "transcripts"
)
# Escape hatch for non-standard installs / relocated corpora.
CORPUS_DIR_ENV = "HERMES_PERSONA_CORPUS_DIR"

# Every persona-corpus artifact carries this tag so vault search / the graph can
# scope to (or exclude) the voice corpus without matching unrelated evidence.
CORPUS_TAG = "persona-corpus"
CHANNEL_TAG = "ricky-and-the-boss"

_LICENSE_NOTES = (
    "Comedic material © John Micheal Stewart (Breadstick Ricky & The Boss). "
    "Stored for private voice-reference use only — not authoritative evidence "
    "and not for republication."
)

# Character detection from the title (the on-screen framing names who's in it).
# Order matters only for the default when nothing matches.
_CHARACTER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("roscoe", "roscoe"),
    ("ricky", "ricky"),
    ("bossman", "bossman"),
    ("boss", "bossman"),
    ("new guy", "new-guy"),
    ("new hire", "new-guy"),
    ("sparky", "sparky"),
)

# Lightweight theme tagging from title + transcript keywords. Kept small and
# explainable — a keyword hit adds a tag, nothing fancier.
_THEME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pay", ("raise", "underpaid", "paycheck", "bonus", "tip", " pay ", "wage")),
    ("time-off", ("pto", "vacation", "day off", "off time", "call in sick", "layoff", "laid off")),
    ("overtime", ("overtime", "ot pay", "work late", "twelve", "12s", "14s")),
    ("safety", ("safety", "ppe", "osha", "drug test", "confined space", "electrocut", "tazed", "tased")),
    ("holiday", ("christmas", "thanksgiving", "new year", "labor day", "july", "valentine", "birthday", "beach")),
    ("hiring", ("interview", "new hire", "fired", "hire", "quit", "laid off", "employee")),
    ("trades", ("weld", "electrician", "plumber", "electrical", "forklift", "concrete", "pump")),
    ("truck", ("truck", "forklift", "trailer", "giveaway", "diesel", "intake")),
    ("tools", ("tool", "ratchet", "wrench", "milwaukee", "stolen")),
    ("pranks", ("prank", "revenge", "trick", "petty", "frame", "hr")),
)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _infer_characters(title: str) -> tuple[str, ...]:
    low = f" {title.lower()} "
    found: list[str] = []
    for needle, tag in _CHARACTER_PATTERNS:
        if needle in low and tag not in found:
            found.append(tag)
    # The core duo carries most sketches; if the title names nobody, mark it
    # ensemble rather than guessing a lead.
    return tuple(found) if found else ("ensemble",)


def _infer_themes(title: str, transcript: str) -> tuple[str, ...]:
    hay = f" {title.lower()} \n {transcript.lower()} "
    themes: list[str] = []
    for theme, needles in _THEME_KEYWORDS:
        if any(n in hay for n in needles) and theme not in themes:
            themes.append(theme)
    return tuple(themes)


@dataclass
class PersonaTranscript:
    """One parsed transcript file from the voice corpus."""

    video_id: str
    title: str
    url: str
    transcript: str
    corpus_path: str = ""  # repo-relative path to the source markdown
    published: str = ""
    length: str = ""
    views: str = ""
    characters: tuple[str, ...] = ()
    themes: tuple[str, ...] = ()

    @property
    def word_count(self) -> int:
        return len(self.transcript.split())

    def tags(self) -> list[str]:
        return [CORPUS_TAG, CHANNEL_TAG, *self.characters, *self.themes]

    def register_in_vault(
        self, vault: ResearchVault, *, persist: bool = False
    ) -> ResearchArtifact:
        """Record this transcript as a WEAK-evidence Research Vault artifact.

        The full transcript is stored as the ``excerpt`` so vault search can
        recall specific lines; ``source_uri`` is the YouTube URL (provenance)
        and ``citation_anchors`` carries the video id. Nothing is fabricated —
        the summary is an explicit one-liner, not an invented paraphrase.
        """

        who = ", ".join(self.characters) if self.characters else "ensemble"
        summary = f"{self.title} — {who} (Breadstick Ricky & The Boss transcript)"
        return vault.add(
            title=self.title,
            source_uri=self.url,
            source_type=SourceType.BLOG,
            evidence_strength=EvidenceStrength.WEAK,
            excerpt=self.transcript,
            summary=summary,
            tags=self.tags(),
            license_notes=_LICENSE_NOTES,
            citation_anchors=(self.video_id,),
            persist=persist,
        )


def resolve_corpus_dir(path: Optional[Path] = None) -> Path:
    """Resolve the transcript directory (explicit > env > repo default)."""

    if path is not None:
        return Path(path)
    env = os.environ.get(CORPUS_DIR_ENV)
    if env:
        return Path(env)
    return DEFAULT_CORPUS_DIR


def parse_transcript(text: str, *, video_id_hint: str = "", corpus_path: str = "") -> Optional[PersonaTranscript]:
    """Parse one transcript markdown blob into a :class:`PersonaTranscript`.

    Returns ``None`` if the blob has no ``## Transcript`` section or the
    transcript body is empty (e.g. a stub that never got filled in).
    """

    parts = re.split(r"^##\s+Transcript\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(parts) != 2:
        return None
    header, body = parts
    transcript = body.strip()
    if not transcript:
        return None

    title = ""
    m = re.search(r"^#\s+(.+?)\s*$", header, flags=re.MULTILINE)
    if m:
        title = m.group(1).strip()

    def field_value(name: str) -> str:
        fm = re.search(rf"^-\s*{re.escape(name)}:\s*(.+?)\s*$", header, flags=re.MULTILINE)
        return fm.group(1).strip() if fm else ""

    video_id = field_value("video_id") or video_id_hint
    url = field_value("url") or (
        f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    )
    return PersonaTranscript(
        video_id=video_id,
        title=title or (corpus_path or video_id),
        url=url,
        transcript=transcript,
        corpus_path=corpus_path,
        published=field_value("published"),
        length=field_value("length"),
        views=field_value("views"),
        characters=_infer_characters(title),
        themes=_infer_themes(title, transcript),
    )


def load_corpus(corpus_dir: Optional[Path] = None) -> list[PersonaTranscript]:
    """Load and parse every transcript markdown file in the corpus directory.

    Files that fail to parse or have empty transcripts are skipped silently
    (best-effort, mirroring the graphrag indexers' non-blocking contract).
    Sorted by video id for deterministic ordering.
    """

    directory = resolve_corpus_dir(corpus_dir)
    out: list[PersonaTranscript] = []
    if not directory.is_dir():
        return out
    for md in sorted(directory.glob("*.md")):
        vid_hint = md.name.split("__", 1)[0]
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            rel = str(md.relative_to(_REPO_ROOT))
        except ValueError:
            rel = md.name
        parsed = parse_transcript(text, video_id_hint=vid_hint, corpus_path=rel)
        if parsed is not None:
            out.append(parsed)
    out.sort(key=lambda t: t.video_id)
    return out


@dataclass
class CorpusRegistration:
    registered: list[ResearchArtifact] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.registered)


def register_all_in_vault(
    vault: ResearchVault,
    *,
    transcripts: Optional[Iterable[PersonaTranscript]] = None,
    corpus_dir: Optional[Path] = None,
    persist: bool = True,
) -> CorpusRegistration:
    """Bridge every transcript into ``vault`` in one pass, saving once at end.

    Idempotent at the artifact level: the vault keys artifacts by a hash of
    ``title|source_uri``, so re-running replaces rather than duplicates.
    """

    pool = list(transcripts) if transcripts is not None else load_corpus(corpus_dir)
    result = CorpusRegistration()
    for t in pool:
        if not t.transcript:
            result.skipped.append((t.video_id, "empty transcript"))
            continue
        result.registered.append(t.register_in_vault(vault, persist=False))
    if persist and result.registered:
        vault.save()
    return result


def search_corpus(
    query: str,
    *,
    vault: Optional[ResearchVault] = None,
    corpus_dir: Optional[Path] = None,
    limit: int = 5,
) -> list[ResearchArtifact]:
    """Keyword-search the persona corpus and return matching vault artifacts.

    If ``vault`` is given, searches it (scoped to persona-corpus artifacts). If
    not, builds an ephemeral in-memory vault from the corpus files first — so
    quoting works even before ``register-vault`` has been run against a
    persistent store. Never persists.
    """

    if vault is None:
        vault = ResearchVault(path=None)
        register_all_in_vault(vault, corpus_dir=corpus_dir, persist=False)
    hits = vault.search(query, limit=max(limit * 3, limit))
    scoped = [a for a in hits if CORPUS_TAG in a.tags]
    return scoped[:limit]
