"""Mobile and voice surface adapter for the conversation engine.

Mobile-like surfaces (phone DM, Termux, voice in/out) must enforce a
short response by default. The adapter:

- Truncates over-long responses to a line budget with a clear pointer
  to focused-mode expansion.
- Builds the six-field mobile task card.
- Strips code blocks and diffs that should never appear while moving.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hermes_cli.jarvis_prime.communication_style import StyleSurface


_MOBILE_SURFACES: frozenset[StyleSurface] = frozenset(
    {StyleSurface.MOBILE, StyleSurface.TERMUX, StyleSurface.VOICE}
)

_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_DIFF_LINE_RE = re.compile(r"^(\+\+\+|---|@@|\+|-) ", re.MULTILINE)
_EXPANSION_POINTER = "[Expand in focused mode: jarvis focused <task>]"


@dataclass(frozen=True)
class MobileTaskCard:
    """Six-field capture packet used for mobile and voice surfaces."""

    captured_idea: str
    clean_title: str
    short_summary: str
    recommended_route: str
    recommended_worker: str
    next_focused_action: str

    def render(self) -> str:
        lines = [
            f"Captured idea:        {self.captured_idea}",
            f"Clean task title:     {self.clean_title}",
            f"Short summary:        {self.short_summary}",
            f"Recommended route:    {self.recommended_route}",
            f"Recommended worker:   {self.recommended_worker}",
            f"Next focused action:  {self.next_focused_action}",
        ]
        return "\n".join(lines)


def is_mobile_surface(surface: StyleSurface) -> bool:
    """Return True for surfaces that should clamp to short output."""
    return surface in _MOBILE_SURFACES


def slugify(text: str, max_words: int = 6) -> str:
    """Build a clean, hyphenated title from a raw capture."""
    if not text:
        return "untitled-capture"
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return "untitled-capture"
    return "-".join(words[:max_words])


def build_task_card(
    raw_text: str,
    recommended_route: str = "Operator Mode",
    recommended_worker: str = "Focused-mode builder",
) -> MobileTaskCard:
    """Build a six-field task card from a raw mobile or voice capture."""
    cleaned = (raw_text or "").strip()
    if not cleaned:
        cleaned = "(empty capture)"

    short = cleaned
    if len(short) > 120:
        short = short[:117].rstrip() + "..."

    title = slugify(cleaned)
    summary = "Review and expand from a focused surface."
    next_action = f"jarvis focused \"{title}\""

    return MobileTaskCard(
        captured_idea=cleaned,
        clean_title=title,
        short_summary=summary,
        recommended_route=recommended_route,
        recommended_worker=recommended_worker,
        next_focused_action=next_action,
    )


def enforce_mobile_limits(
    response: str,
    surface: StyleSurface,
    max_lines: int = 12,
) -> str:
    """Truncate a response so it fits on a mobile-like surface."""
    if not is_mobile_surface(surface):
        return response

    stripped = _CODE_BLOCK_RE.sub("[code removed for mobile; expand in focused mode]", response)
    stripped = _DIFF_LINE_RE.sub("", stripped)

    lines = [line for line in stripped.splitlines() if line is not None]
    if len(lines) <= max_lines:
        return "\n".join(lines).rstrip()

    head = lines[:max_lines]
    return "\n".join(head).rstrip() + "\n\n" + _EXPANSION_POINTER


def append_expansion_pointer(response: str, surface: StyleSurface) -> str:
    """Append the focused-mode pointer when the response was truncated."""
    if not is_mobile_surface(surface):
        return response
    if _EXPANSION_POINTER in response:
        return response
    return response.rstrip() + "\n\n" + _EXPANSION_POINTER


__all__ = [
    "MobileTaskCard",
    "is_mobile_surface",
    "slugify",
    "build_task_card",
    "enforce_mobile_limits",
    "append_expansion_pointer",
]
