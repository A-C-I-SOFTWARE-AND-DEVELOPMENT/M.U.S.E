"""Short-term + long-term memory with recollection for JARVIS Prime.

The user asked for JARVIS to be "a true friend and partner, with
short term and long term memory as well as memory recollection,
being able to truly learn and adapt." This module gives him that.

Three tiers:

| Tier | TTL | Backend | Use case |
|---|---|---|---|
| working (STM) | minutes — one turn | in-process dict | within-conversation context |
| session | one conversation | in-process + journal | this chat's facts |
| durable (LTM) | forever | plugins/memory/* | preferences, mission, lessons |

Recollection ranks recent + relevant + durable hits, returns the top
N. Recollection runs before classify/decide so JARVIS's persona
prompt includes the right context. All writes to durable memory
require an explicit ``durability="durable"`` tag — temporary emotions
default to "session" and never leak to LTM (per the
memory-and-personality-policy doc).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

LOGGER = logging.getLogger("hermes.jarvis_prime.memory")


# Patterns we NEVER write to memory (mirrors memory-and-personality-policy.md).
# Coverage expanded during final-launch review: SSN, credit cards, AWS access
# keys, PEM/SSH private keys, and JWT-shaped tokens were missing.
_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_ -]?key|secret|password|token|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-zA-Z0-9_-]{20,}"),  # OpenAI-style secrets
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{20,}"),    # GitHub tokens
    re.compile(r"(?i)xox[a-z]-[a-zA-Z0-9-]{10,}"),  # Slack tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),         # AWS access key id
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),        # US SSN
    re.compile(                                  # major-brand credit card numbers
        r"(?<!\d)(?:4\d{12}(?:\d{3})?"           #   Visa
        r"|5[1-5]\d{14}"                          #   Mastercard
        r"|3[47]\d{13}"                           #   AmEx
        r"|6(?:011|5\d{2})\d{12})(?!\d)"          #   Discover
    ),
    re.compile(
        r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP|ENCRYPTED) PRIVATE KEY-----"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),  # JWT
)


# Phrases that suggest temporary emotion — never durable.
_EMOTIONAL_HINTS: tuple[str, ...] = (
    "i'm tired", "feeling stressed", "frustrated today", "rough day",
    "anxious right now", "burnt out", "i hate", "i love",
    "this sucks", "i'm angry",
)


@dataclass
class MemoryRecord:
    key: str
    value: str
    durability: str  # "working" | "session" | "durable"
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_recalled_at: Optional[datetime] = None
    tags: tuple[str, ...] = ()
    source: str = "user"  # "user" | "agent" | "system"
    confidence: float = 1.0
    citations: tuple[str, ...] = ()
    # Cockpit-facing classification (canonical contract). Optional and
    # additive: legacy/agent-written records leave it None and the
    # cockpit projects an honest "uncategorized" rather than guessing.
    category: Optional[str] = None
    hidden: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "value": self.value,
            "durability": self.durability,
            "captured_at": self.captured_at.isoformat(),
            "last_recalled_at": self.last_recalled_at.isoformat() if self.last_recalled_at else None,
            "tags": list(self.tags),
            "source": self.source,
            "confidence": self.confidence,
            "citations": list(self.citations),
            "category": self.category,
            "hidden": self.hidden,
        }


def _contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _FORBIDDEN_PATTERNS)


def _is_temporary_emotion(text: str) -> bool:
    low = text.lower()
    return any(hint in low for hint in _EMOTIONAL_HINTS)


def _default_journal_path() -> Path:
    """Journal location, honoring ``HERMES_HOME`` like the rest of the stack.

    Defaults to ``~/.hermes`` when unset, so production behavior is
    unchanged — but tests / Termux / the cockpit can relocate the whole
    store by setting ``HERMES_HOME`` (otherwise memory leaks across the
    real home dir and isn't test-isolated).
    """
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "memory.jsonl"


@dataclass
class MemoryStore:
    """In-process layered memory store with persistence to disk.

    Working memory lives only in this process. Session and durable
    memory journal to ``~/.hermes/jarvis_prime/memory.jsonl`` so a
    restarted process can warm-start. Real backends (sqlite/honcho/
    mem0/supermemory) are wired by reading the same journal — kept
    decoupled here so the package stays stdlib-only at import time.
    """

    journal_path: Path = field(default_factory=_default_journal_path)
    working: list[MemoryRecord] = field(default_factory=list)
    session: list[MemoryRecord] = field(default_factory=list)
    durable: list[MemoryRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._load_journal()

    def _load_journal(self) -> None:
        if not self.journal_path.is_file():
            return
        _tighten_perms(self.journal_path)
        try:
            with self.journal_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    captured_at = _parse_iso(data.get("captured_at")) or datetime.now(timezone.utc)
                    record = MemoryRecord(
                        key=data.get("key", ""),
                        value=data.get("value", ""),
                        durability=data.get("durability", "session"),
                        captured_at=captured_at,
                        last_recalled_at=_parse_iso(data.get("last_recalled_at")),
                        tags=tuple(data.get("tags") or ()),
                        source=data.get("source", "user"),
                        confidence=float(data.get("confidence", 1.0)),
                        citations=tuple(data.get("citations") or ()),
                        category=data.get("category"),
                        hidden=bool(data.get("hidden", False)),
                    )
                    if record.durability == "durable":
                        self.durable.append(record)
                    elif record.durability == "session":
                        self.session.append(record)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("memory journal load failed: %s", exc)

    def _journal(self, record: MemoryRecord) -> None:
        if record.durability == "working":
            return
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record.to_dict()) + "\n")
            # Memory may include user context the OS umask would leave
            # world-readable; force 0o600 owner-only after every write.
            _tighten_perms(self.journal_path)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("memory journal write failed: %s", exc)

    def remember(
        self,
        key: str,
        value: str,
        durability: str = "session",
        tags: Iterable[str] = (),
        source: str = "user",
        confidence: float = 1.0,
        citations: Iterable[str] = (),
        category: Optional[str] = None,
        hidden: bool = False,
    ) -> Optional[MemoryRecord]:
        """Capture a memory. Returns the record, or None if rejected.

        Rejection rules (per memory-and-personality-policy.md):
        - Never store secrets.
        - Never store temporary emotion as durable.
        - Reject unverified claims when durability=durable and confidence<0.6.
        """

        if _contains_secret(key) or _contains_secret(value):
            LOGGER.info("memory: rejected — contains secret-like text")
            return None
        if durability == "durable":
            if _is_temporary_emotion(value):
                LOGGER.info("memory: downgraded durable→session (temporary emotion)")
                durability = "session"
            elif confidence < 0.6:
                LOGGER.info("memory: rejected — durable claim below confidence floor")
                return None

        record = MemoryRecord(
            key=key,
            value=value,
            durability=durability,
            tags=tuple(tags),
            source=source,
            confidence=confidence,
            citations=tuple(citations),
            category=category,
            hidden=hidden,
        )
        getattr(self, durability).append(record)
        self._journal(record)
        return record

    def recollect(
        self,
        query: str,
        limit: int = 5,
        include_working: bool = True,
    ) -> list[MemoryRecord]:
        """Rank-and-return the top memory hits for the query.

        Ranking is deterministic: term overlap + recency boost +
        durability weight. Higher score = better hit. The function
        also updates ``last_recalled_at`` for the returned records
        so the next ranking knows what was recently surfaced.
        """

        all_records: list[MemoryRecord] = []
        if include_working:
            all_records.extend(self.working)
        all_records.extend(self.session)
        all_records.extend(self.durable)
        if not all_records:
            return []

        terms = _tokenize(query)
        now_ts = time.time()
        scored: list[tuple[float, MemoryRecord]] = []
        for r in all_records:
            text = (r.key + " " + r.value).lower()
            score = sum(1 for t in terms if t in text)
            if score == 0:
                continue
            age_hours = max(0.01, (now_ts - r.captured_at.timestamp()) / 3600.0)
            recency_boost = 1.0 / (1.0 + age_hours / 24.0)  # 1.0 today, 0.5 tomorrow
            weight = {"durable": 1.5, "session": 1.0, "working": 0.7}.get(r.durability, 1.0)
            scored.append((score * weight + recency_boost, r))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [r for _, r in scored[:limit]]
        now = datetime.now(timezone.utc)
        for r in top:
            r.last_recalled_at = now
        return top

    def forget(self, key: str) -> int:
        """Remove all records with a given key. Returns count.

        Persists the removal: the journal is rewritten so a forget is
        durable across processes (a fresh ``MemoryStore`` won't reload the
        forgotten record). Without this, per-request stores — like the
        cockpit DELETE handler — would never actually delete anything.
        """

        removed = 0
        for collection_name in ("working", "session", "durable"):
            collection = getattr(self, collection_name)
            new_collection = [r for r in collection if r.key != key]
            removed += len(collection) - len(new_collection)
            setattr(self, collection_name, new_collection)
        if removed:
            self._rewrite_journal()
        return removed

    def _rewrite_journal(self) -> None:
        """Atomically rewrite the journal from the persisted tiers.

        Working memory is never journaled, so only session + durable are
        written. Used after a forget (and any other mutation that removes
        a previously-journaled record).
        """
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.journal_path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for record in list(self.session) + list(self.durable):
                    fh.write(json.dumps(record.to_dict()) + "\n")
            os.replace(tmp, self.journal_path)
            _tighten_perms(self.journal_path)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.debug("memory journal rewrite failed: %s", exc)

    def summarize_for_prompt(self, query: str, limit: int = 5) -> str:
        """Render the top recollections as a compact string for the persona prompt."""

        hits = self.recollect(query, limit=limit)
        if not hits:
            return ""
        lines = ["RECOLLECTION (top relevant memories):"]
        for r in hits:
            tag = f"[{r.durability}]"
            if r.confidence < 1.0:
                tag += f"(conf={r.confidence:.2f})"
            lines.append(f"- {tag} {r.key}: {r.value[:200]}")
        return "\n".join(lines)


def _tokenize(text: str) -> set[str]:
    return {w for w in re.split(r"\W+", text.lower()) if len(w) > 2}


def _tighten_perms(path: Path) -> None:
    """Best-effort chmod 0o600 on the journal file. No-op on platforms
    where the call fails (Windows native, restricted FS)."""
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent
        pass


def _parse_iso(value: object) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
