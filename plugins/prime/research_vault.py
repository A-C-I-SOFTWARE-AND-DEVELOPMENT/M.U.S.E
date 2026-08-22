"""Research Vault — an evidence store for cited, strength-graded artifacts.

Holds papers, official docs, OSS practices, benchmark notes and courses as
source-cited artifacts. It summarizes **only** from stored citation text or
caller-provided excerpts — it never fabricates a summary, downloads
copyrighted/private material, or makes network calls.

Stdlib-only, local JSONL persistence with atomic writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceType(str, Enum):
    PAPER = "paper"
    OFFICIAL_DOC = "official_doc"
    BLOG = "blog"
    REPO = "repo"
    COURSE = "course"
    BENCHMARK = "benchmark"
    OSS_PRACTICE = "oss_practice"
    MANUAL = "manual"


class EvidenceStrength(str, Enum):
    PRIMARY = "primary"  # primary source / official spec / peer-reviewed
    STRONG = "strong"  # reputable secondary, reproduced
    MODERATE = "moderate"  # reputable but unverified
    WEAK = "weak"  # community / anecdotal
    VENDOR_REPORTED = "vendor_reported"  # vendor benchmark claim, unverified


def _checksum(text: str) -> str:
    """Stable sha256 of the canonicalized excerpt — integrity / dedupe anchor."""

    canonical = " ".join((text or "").split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ResearchArtifact:
    id: str
    title: str
    source_uri: str
    source_type: SourceType = SourceType.MANUAL
    evidence_strength: EvidenceStrength = EvidenceStrength.MODERATE
    excerpt: str = ""  # the stored citation text we summarize from
    summary: str = ""
    tags: tuple[str, ...] = ()
    freshness_due: Optional[str] = None
    added_at: str = field(default_factory=_now_iso)
    # Evidence-engine provenance fields (all optional / back-compatible).
    license_notes: str = ""  # usage/licensing constraints on the source text
    retrieved_at: str = field(default_factory=_now_iso)  # when the excerpt was captured
    checksum: str = ""  # sha256 of the canonical excerpt (filled in by ResearchVault.add)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "source_uri": self.source_uri,
            "source_type": self.source_type.value,
            "evidence_strength": self.evidence_strength.value,
            "excerpt": self.excerpt,
            "summary": self.summary,
            "tags": list(self.tags),
            "freshness_due": self.freshness_due,
            "added_at": self.added_at,
            "license_notes": self.license_notes,
            "retrieved_at": self.retrieved_at,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchArtifact":
        return cls(
            id=d["id"],
            title=d.get("title", ""),
            source_uri=d.get("source_uri", ""),
            source_type=SourceType(d.get("source_type", "manual")),
            evidence_strength=EvidenceStrength(d.get("evidence_strength", "moderate")),
            excerpt=d.get("excerpt", ""),
            summary=d.get("summary", ""),
            tags=tuple(d.get("tags", []) or []),
            freshness_due=d.get("freshness_due"),
            added_at=d.get("added_at", _now_iso()),
            license_notes=d.get("license_notes", ""),
            # Old records predate retrieved_at — fall back to added_at, never invent "now".
            retrieved_at=d.get("retrieved_at") or d.get("added_at") or _now_iso(),
            checksum=d.get("checksum", ""),
        )

    def audit_card(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "source_uri": self.source_uri,
            "source_type": self.source_type.value,
            "evidence_strength": self.evidence_strength.value,
            "claim": self.summary or self.excerpt[:160],
            "freshness_due": self.freshness_due,
            "added_at": self.added_at,
            "retrieved_at": self.retrieved_at,
            "checksum": self.checksum,
            "license_notes": self.license_notes,
        }


def _default_vault_path() -> Path:
    """Vault location, honoring ``HERMES_HOME`` like the rest of the stack
    (otherwise the vault leaks across the real home dir and isn't isolated)."""

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "prime" / "research_vault.jsonl"


@dataclass
class ResearchVault:
    path: Optional[Path] = None
    artifacts: dict[str, ResearchArtifact] = field(default_factory=dict)
    load_diagnostics: list[str] = field(default_factory=list)

    def add(
        self,
        title: str,
        source_uri: str,
        *,
        source_type: SourceType = SourceType.MANUAL,
        evidence_strength: EvidenceStrength = EvidenceStrength.MODERATE,
        excerpt: str = "",
        summary: str = "",
        tags: Iterable[str] = (),
        freshness_due: Optional[str] = None,
        license_notes: str = "",
        retrieved_at: Optional[str] = None,
        persist: bool = True,
    ) -> ResearchArtifact:
        # Summaries come only from the stored excerpt or an explicit summary.
        effective_summary = summary.strip() or _excerpt_summary(excerpt)
        clean_excerpt = excerpt.strip()
        art = ResearchArtifact(
            id=hashlib.sha1(f"{title}|{source_uri}".encode()).hexdigest()[:16],
            title=title.strip(),
            source_uri=source_uri.strip(),
            source_type=source_type,
            evidence_strength=evidence_strength,
            excerpt=clean_excerpt,
            summary=effective_summary,
            tags=tuple(tags),
            freshness_due=freshness_due,
            license_notes=license_notes.strip(),
            retrieved_at=retrieved_at or _now_iso(),
            checksum=_checksum(clean_excerpt),
        )
        self.artifacts[art.id] = art
        if persist:
            self.save()
        return art

    def entries(
        self, *, source_type: Optional[SourceType] = None
    ) -> list[ResearchArtifact]:
        items = list(self.artifacts.values())
        if source_type:
            items = [a for a in items if a.source_type == source_type]
        return sorted(items, key=lambda a: a.added_at)

    def search(self, query: str, *, limit: int = 10) -> list[ResearchArtifact]:
        terms = {t for t in query.lower().split() if len(t) > 2}
        scored = []
        for art in self.artifacts.values():
            hay = (
                f"{art.title} {art.summary} {art.excerpt} {' '.join(art.tags)}".lower()
            )
            score = sum(1 for t in terms if t in hay)
            if score:
                scored.append((score, art))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:limit]]

    def export_audit_cards(self) -> list[dict]:
        return [a.audit_card() for a in self.entries()]

    def export_markdown(self) -> str:
        lines = ["# Research Vault", ""]
        for art in self.entries():
            lines.append(f"## {art.title}")
            lines.append(
                f"- source: {art.source_uri} "
                f"({art.source_type.value}, {art.evidence_strength.value})"
            )
            if art.freshness_due:
                lines.append(f"- freshness due: {art.freshness_due}")
            if art.summary:
                lines.append(f"- summary: {art.summary}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # -- persistence --------------------------------------------------------

    def _resolve_path(self) -> Path:
        return Path(self.path) if self.path else _default_vault_path()

    def save(self) -> Path:
        target = self._resolve_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(a.to_dict(), sort_keys=True) + "\n"
            for a in self.artifacts.values()
        )
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".rvault-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ResearchVault":
        vault = cls(path=path)
        target = vault._resolve_path()
        if not target.exists():
            return vault
        with open(target, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    art = ResearchArtifact.from_dict(json.loads(raw))
                    vault.artifacts[art.id] = art
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    vault.load_diagnostics.append(f"line {lineno}: {exc}")
        return vault


def _excerpt_summary(excerpt: str) -> str:
    excerpt = " ".join((excerpt or "").split())
    return excerpt[:200]
