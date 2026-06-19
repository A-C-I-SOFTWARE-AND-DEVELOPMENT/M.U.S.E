"""Six muse modes + intent classifier.

The mode set is the contract from
``docs/jarvis-prime-operating-system.md`` § Modes and the SKILL
front-matter "When to use" section. The classifier is heuristic
only — keyword + surface + risk signals. The runtime can still
override its choice (e.g. `/strategy` pins Strategy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class Mode(Enum):
    """The six canonical muse operating modes."""

    COMPANION = "companion"
    STRATEGY = "strategy"
    CRITIC = "critic"
    OPERATOR = "operator"
    BUILDER = "builder"
    MOBILE_VOICE = "mobile_voice"

    @property
    def name(self) -> str:
        return self.value


@dataclass(frozen=True)
class ModeClassification:
    mode: Mode
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "confidence": self.confidence,
            "reason": self.reason,
        }


# Keyword sets for each mode. Lowercased. Multi-word phrases checked
# as substrings of the lowered intent.
_BUILDER_KEYWORDS: tuple[str, ...] = (
    "build", "implement", "fix", "patch", "refactor", "test",
    "claude code", "codex", "pr", "pull request", "branch",
    "diff", "merge conflict", "rollback", "commit", "git status",
    "repo audit", "code review", "review packet",
)
_OPERATOR_KEYWORDS: tuple[str, ...] = (
    "route", "dispatch", "task packet", "operator", "issue plan",
    "kanban", "orchestrate", "delegate", "council", "next action",
    "ship it", "execute", "scope this", "audit", "blocker", "blockers",
    "plan this", "what should i do",
)
_STRATEGY_KEYWORDS: tuple[str, ...] = (
    "strategy", "positioning", "pricing", "investor", "promotion",
    "career", "monetize", "market", "tradeoff", "leverage",
    "should i", "best path", "go big", "narrow scope", "what to focus on",
)
_CRITIC_KEYWORDS: tuple[str, ...] = (
    "critique", "weakness", "blind spot", "tear apart", "red team",
    "challenge this", "disagree", "what would go wrong", "fatal flaw",
    "is this dumb", "play devil's advocate", "counter argument",
)
_COMPANION_KEYWORDS: tuple[str, ...] = (
    "i'm tired", "feeling", "stressed", "anxious", "frustrated",
    "rough day", "burnt out", "lonely", "vent", "talk to me",
    "encourage", "morale", "honest support",
)
_MOBILE_VOICE_KEYWORDS: tuple[str, ...] = (
    "jogging", "walking", "driving", "in the car", "voice memo",
    "voice note", "on my phone", "away from desk", "quick idea",
    "capture this", "remind me", "while i drive", "while i walk",
)


# Surface hints — when known, they upweight specific modes.
_MOBILE_SURFACES: frozenset[str] = frozenset({"telegram", "signal", "whatsapp", "voice", "termux"})


@dataclass(frozen=True)
class ClassifierContext:
    """Context the classifier consults beyond the intent string."""

    surface: Optional[str] = None  # e.g. "telegram", "slack", "voice"
    is_voice_input: bool = False
    repo_root: Optional[str] = None  # set → builder upweight
    risk_class: Optional[str] = None  # RC0..RC4 from executive-operator
    explicit_mode: Optional[Mode] = None  # `/strategy` etc.
    history: Sequence[str] = field(default_factory=tuple)


@dataclass
class ModeClassifier:
    """Heuristic mode classifier.

    The classifier is deterministic and stdlib-only. It does not call
    an LLM; downstream code may override via ``ClassifierContext.explicit_mode``.
    """

    keyword_sets: dict[Mode, tuple[str, ...]] = field(
        default_factory=lambda: {
            Mode.BUILDER: _BUILDER_KEYWORDS,
            Mode.OPERATOR: _OPERATOR_KEYWORDS,
            Mode.STRATEGY: _STRATEGY_KEYWORDS,
            Mode.CRITIC: _CRITIC_KEYWORDS,
            Mode.COMPANION: _COMPANION_KEYWORDS,
            Mode.MOBILE_VOICE: _MOBILE_VOICE_KEYWORDS,
        }
    )

    def classify(
        self,
        intent: str,
        context: Optional[ClassifierContext] = None,
    ) -> ModeClassification:
        context = context or ClassifierContext()
        if context.explicit_mode is not None:
            return ModeClassification(
                mode=context.explicit_mode,
                confidence=1.0,
                reason=f"explicit override via {context.explicit_mode.value}",
            )

        text = (intent or "").lower().strip()
        if not text:
            return ModeClassification(
                mode=Mode.OPERATOR,
                confidence=0.3,
                reason="empty intent — default to operator (routing)",
            )

        scores: dict[Mode, int] = {m: 0 for m in Mode}

        for mode, keywords in self.keyword_sets.items():
            for kw in keywords:
                if kw in text:
                    scores[mode] += 1

        # Surface and voice signals.
        if context.is_voice_input or (context.surface == "voice"):
            scores[Mode.MOBILE_VOICE] += 3
        if context.surface and context.surface.lower() in _MOBILE_SURFACES:
            scores[Mode.MOBILE_VOICE] += 1
        if context.repo_root:
            scores[Mode.BUILDER] += 1
        if context.risk_class in {"RC3", "RC4"}:
            scores[Mode.CRITIC] += 1

        # Tie-breaker priority — picks more deterministic mode when scores tie.
        priority = [
            Mode.MOBILE_VOICE,
            Mode.BUILDER,
            Mode.OPERATOR,
            Mode.CRITIC,
            Mode.STRATEGY,
            Mode.COMPANION,
        ]

        best = max(priority, key=lambda m: (scores[m], -priority.index(m)))
        best_score = scores[best]
        if best_score == 0:
            # Nothing matched — companion as conversational fallback.
            return ModeClassification(
                mode=Mode.COMPANION,
                confidence=0.4,
                reason="no keywords matched — companion conversational fallback",
            )

        total = sum(scores.values()) or 1
        confidence = min(0.99, 0.5 + 0.5 * (best_score / total))

        matched = [k for k in self.keyword_sets[best] if k in text]
        reason_bits = []
        if matched:
            reason_bits.append(f"keywords={matched[:3]}")
        if context.is_voice_input:
            reason_bits.append("voice input")
        if context.surface:
            reason_bits.append(f"surface={context.surface}")
        if context.repo_root and best == Mode.BUILDER:
            reason_bits.append(f"repo={context.repo_root}")

        return ModeClassification(
            mode=best,
            confidence=confidence,
            reason="; ".join(reason_bits) or "keyword match",
        )


def mode_from_slash_command(command: str) -> Optional[Mode]:
    """Map a slash command like ``/strategy`` to a Mode (or None)."""

    cmd = command.lstrip("/").strip().lower()
    mapping = {
        "companion": Mode.COMPANION,
        "strategy": Mode.STRATEGY,
        "critic": Mode.CRITIC,
        "operator": Mode.OPERATOR,
        "builder": Mode.BUILDER,
        "mobile-voice": Mode.MOBILE_VOICE,
        "mobile_voice": Mode.MOBILE_VOICE,
        "voice": Mode.MOBILE_VOICE,
        # Aliases for the apex slash commands also default-route to
        # auto-classify (caller passes Mode=None then).
        "jarvis": None,  # signal: auto-classify
        "jarvis-prime": None,
        "jp": None,
    }
    return mapping.get(cmd)
