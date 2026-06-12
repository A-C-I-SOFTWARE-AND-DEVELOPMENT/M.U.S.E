"""Conversational pacing + when-to-speak rules for MUSE.

The user asked: "research websites… human psychology, human
interactions, how we speak and patterns, knowing when it should
stop talking, when it should interrupt — this should feel like a
real person."

This module captures conversational competence as code:

- **TurnTakingPolicy** — when to speak, when to listen, when to
  interrupt.
- **PacingDecision** — for each turn, decide length / tone / cadence.
- **Backchannel detection** — recognize "uh-huh" / "right" /
  "go on" as continuance signals, not as content.
- **Topic-shift detection** — when the user changes topic, do not
  finish the prior thread unless they ask.

The rules here are *defaults* drawn from public-knowledge sources
on dialogue pragmatics. The runtime should call ``decide_pacing``
before composing a response; the persona prompt then honors the
decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class SpeakingPosture(Enum):
    SPEAK = "speak"
    LISTEN = "listen"
    BACKCHANNEL = "backchannel"  # acknowledge briefly, do not take the floor
    INTERRUPT = "interrupt"      # only for emergencies / safety / large factual error


class Cadence(Enum):
    BRIEF = "brief"          # 1-2 sentences, urgent or mobile
    NORMAL = "normal"        # paragraph
    DEEP = "deep"            # full structured response


_BACKCHANNEL_HINTS: tuple[str, ...] = (
    "uh huh", "uh-huh", "mhm", "right", "yeah", "go on", "i see",
    "okay", "ok", "got it", "interesting", "tell me more",
)

_INTERRUPT_TRIGGERS: tuple[str, ...] = (
    # Factual safety triggers
    "credentials in", "api key", "password is", "private key",
    # Action safety triggers
    "rm -rf", "drop database", "force push to main",
    # Hallucination triggers when the user states something contradicted by memory
)

_TOPIC_SHIFT_MARKERS: tuple[str, ...] = (
    "anyway", "moving on", "another thing", "different question",
    "switching gears", "on a different note", "btw", "by the way",
    "actually", "wait",
)


@dataclass(frozen=True)
class PacingContext:
    """Signals the pacing decision draws from."""

    user_text_length: int = 0
    user_appears_moving: bool = False   # mobile / voice surface
    user_recently_interrupted: bool = False
    surface: Optional[str] = None
    prior_response_length: int = 0
    topic_shift_signal: bool = False
    safety_triggered: bool = False


@dataclass(frozen=True)
class PacingDecision:
    posture: SpeakingPosture
    cadence: Cadence
    max_sentences: int
    rationale: str


def is_backchannel(text: str) -> bool:
    low = (text or "").lower().strip()
    if len(low) > 30:
        return False
    return any(hint == low or hint in low.split() for hint in _BACKCHANNEL_HINTS) or low in _BACKCHANNEL_HINTS


def is_topic_shift(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _TOPIC_SHIFT_MARKERS)


def needs_interrupt(text: str) -> bool:
    low = (text or "").lower()
    return any(trigger in low for trigger in _INTERRUPT_TRIGGERS)


def decide_pacing(user_text: str, context: Optional[PacingContext] = None) -> PacingDecision:
    """Map (user text + context) → PacingDecision.

    Decision tree (in order):
    1. Safety trigger → INTERRUPT.
    2. Backchannel from user → BACKCHANNEL (acknowledge, don't take floor).
    3. User is on mobile/voice → BRIEF cadence regardless of mode.
    4. Topic shift → respond on new topic; do not finish old thread.
    5. User text is very short (< 12 chars) and we just spoke a lot → BRIEF.
    6. Otherwise NORMAL or DEEP based on user text length.
    """

    context = context or PacingContext()
    text = user_text or ""

    if needs_interrupt(text) or context.safety_triggered:
        return PacingDecision(
            posture=SpeakingPosture.INTERRUPT,
            cadence=Cadence.BRIEF,
            max_sentences=2,
            rationale="safety trigger — interrupt and surface risk briefly",
        )

    if is_backchannel(text):
        return PacingDecision(
            posture=SpeakingPosture.BACKCHANNEL,
            cadence=Cadence.BRIEF,
            max_sentences=1,
            rationale="user backchanneled — acknowledge, don't take the floor",
        )

    if context.user_appears_moving or context.surface == "voice":
        return PacingDecision(
            posture=SpeakingPosture.SPEAK,
            cadence=Cadence.BRIEF,
            max_sentences=2,
            rationale="user on mobile/voice — keep it short",
        )

    if context.topic_shift_signal or is_topic_shift(text):
        return PacingDecision(
            posture=SpeakingPosture.SPEAK,
            cadence=Cadence.NORMAL,
            max_sentences=6,
            rationale="topic shift — respond on the new thread, drop the old",
        )

    if len(text.strip()) < 12 and context.prior_response_length > 400:
        return PacingDecision(
            posture=SpeakingPosture.SPEAK,
            cadence=Cadence.BRIEF,
            max_sentences=2,
            rationale="we just over-explained — match user's compact reply",
        )

    if len(text.strip()) > 240 or _looks_like_question(text):
        return PacingDecision(
            posture=SpeakingPosture.SPEAK,
            cadence=Cadence.DEEP,
            max_sentences=18,
            rationale="user wrote a lot or asked a substantive question — go deep",
        )

    return PacingDecision(
        posture=SpeakingPosture.SPEAK,
        cadence=Cadence.NORMAL,
        max_sentences=8,
        rationale="default conversational cadence",
    )


def _looks_like_question(text: str) -> bool:
    return "?" in text or re.search(r"^(what|how|why|when|where|who|which|can|should|will|do|does)\b", text.strip().lower()) is not None


@dataclass
class TurnTakingPolicy:
    """The full policy — used by the runtime to gate each turn."""

    backchannel_text: str = "Mm."

    def evaluate(self, user_text: str, context: Optional[PacingContext] = None) -> PacingDecision:
        return decide_pacing(user_text, context)


HUMAN_INTERACTION_RESEARCH_NOTES: str = """\
Public-knowledge anchors for JARVIS's conversational pragmatics
(treat these as priors, not citations — research deeper when the
user asks for a specific claim):

- **Turn-taking**: speakers offer floor cues (falling intonation,
  pause length > ~700ms, eye gaze in person). In text, equivalent
  cues are sentence-final punctuation, blank lines, and explicit
  hand-offs ("what do you think?").
- **Backchannels** ("mhm", "yeah") do not constitute floor-taking;
  treat them as continuance signals.
- **Latency norms** in instant messaging tolerate 5-60s; sub-1s
  replies can feel intrusive. In voice, < 500ms is normal.
- **Topic management**: prefer marked transitions ("anyway",
  "switching gears") over abrupt drops. Honor the user's topic
  shifts; do not finish stale threads unless asked.
- **Disagreement**: state the strongest objection plainly; do not
  capitulate at the first pushback. Re-check evidence first.
- **Repair**: when the user corrects you, acknowledge the
  correction, update memory, and explain what changed.
- **Empathy**: validate emotion, then separate from technical
  judgment ("that sounds rough — and the deploy still needs the
  rollback plan documented").

When unsure, JARVIS should ask one clarifying question rather
than guess. Asking ≤ 1 question per turn is the default; multi-
question pile-ons feel inquisitorial.
"""
