"""Finalizer for the Jarvis Prime conversation engine.

The finalizer is the last pass before user-facing text leaves the engine.
It:

1. Strips internal routing noise (debug lines, route IDs, internal
   handoff markers) unless the user explicitly asked to see it.
2. Runs the brand guard: outside system names must not appear in
   user-facing product copy.
3. Removes fake-human and yes-man phrasing.
4. Enforces a final line budget when a max is supplied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hermes_cli.jarvis_prime.persona import (
    FAKE_HUMAN_PHRASES,
    PRODUCT_NAME,
    YES_MAN_OPENERS,
)
from hermes_cli.jarvis_prime.conversation.response_shapes import RenderedResponse


# Outside product brand names that must not appear in user-facing text.
# Surface names (Slack, Termux, GitHub) are allowed because they describe
# *channels*, not competing AI systems; the conversation engine still
# leans on those as place-references, e.g. "in your Slack workspace".
BLOCKED_BRANDS: tuple[str, ...] = (
    "Claude",
    "Claude Code",
    "Codex",
    "Anthropic",
    "OpenAI",
    "ChatGPT",
    "GPT-4",
    "GPT-5",
    "GPT-3",
    "Gemini",
    "Bard",
    "Copilot",
    "Cursor",
    "Hermes Agent",
)

ALLOWED_SURFACE_NAMES: tuple[str, ...] = (
    "Slack",
    "Termux",
    "GitHub",
    "Discord",
    "Telegram",
    "WhatsApp",
    "Matrix",
    "Signal",
)


# Internal-route markers stripped from user-facing text.
_ROUTE_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\[route:[^\]]+\]\s*$", re.MULTILINE),
    re.compile(r"^\[internal:[^\]]+\]\s*$", re.MULTILINE),
    re.compile(r"^\[trace:[^\]]+\]\s*$", re.MULTILINE),
    re.compile(r"^route_id=[A-Za-z0-9_\-]+\s*$", re.MULTILINE),
    re.compile(r"^handoff_marker:[^\n]+$", re.MULTILINE),
)


@dataclass(frozen=True)
class FinalizationReport:
    """Diagnostic information about what the finalizer changed."""

    stripped_route_noise: bool
    flagged_brands: tuple[str, ...]
    flagged_fake_human: tuple[str, ...]
    flagged_yes_man: tuple[str, ...]
    truncated: bool


def _strip_route_noise(text: str) -> tuple[str, bool]:
    """Remove internal route markers; return cleaned text + whether changes occurred."""
    cleaned = text
    changed = False
    for pattern in _ROUTE_NOISE_PATTERNS:
        if pattern.search(cleaned):
            cleaned = pattern.sub("", cleaned)
            changed = True
    if changed:
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip("\n"), changed


def _scan_brands(text: str) -> tuple[str, ...]:
    """Return blocked brand names found verbatim in the text."""
    found: list[str] = []
    for brand in BLOCKED_BRANDS:
        pattern = re.compile(rf"\b{re.escape(brand)}\b", re.IGNORECASE)
        if pattern.search(text):
            found.append(brand)
    return tuple(found)


def _scan_fake_human(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(phrase for phrase in FAKE_HUMAN_PHRASES if phrase in lowered)


def _scan_yes_man(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(opener for opener in YES_MAN_OPENERS if lowered.startswith(opener))


def _rewrite_brands(text: str, brands: tuple[str, ...]) -> str:
    out = text
    for brand in brands:
        pattern = re.compile(rf"\b{re.escape(brand)}\b", re.IGNORECASE)
        out = pattern.sub(PRODUCT_NAME, out)
    return out


def _rewrite_fake_human(text: str, phrases: tuple[str, ...]) -> str:
    out = text
    for phrase in phrases:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        out = pattern.sub(PRODUCT_NAME, out)
    return out


def _rewrite_yes_man(text: str, openers: tuple[str, ...]) -> str:
    out = text
    for opener in openers:
        if out.lower().startswith(opener):
            out = out[len(opener):].lstrip(" .!,:;-")
            break
    return out


def finalize(
    rendered: RenderedResponse,
    *,
    expose_internal: bool = False,
    max_lines: int | None = None,
) -> tuple[str, FinalizationReport]:
    """Run the finalizer over a rendered response.

    Returns the final user-facing text plus a :class:`FinalizationReport`
    describing what was changed.
    """
    text = rendered.body
    if rendered.suffix:
        text = text.rstrip() + "\n" + rendered.suffix

    stripped_noise = False
    if not expose_internal:
        text, stripped_noise = _strip_route_noise(text)

    brands = _scan_brands(text)
    fake_human = _scan_fake_human(text)
    yes_man = _scan_yes_man(text)

    if brands:
        text = _rewrite_brands(text, brands)
    if fake_human:
        text = _rewrite_fake_human(text, fake_human)
    if yes_man:
        text = _rewrite_yes_man(text, yes_man)

    truncated = False
    if max_lines is not None:
        lines = text.splitlines()
        if len(lines) > max_lines:
            text = "\n".join(lines[:max_lines]).rstrip()
            truncated = True

    report = FinalizationReport(
        stripped_route_noise=stripped_noise,
        flagged_brands=brands,
        flagged_fake_human=fake_human,
        flagged_yes_man=yes_man,
        truncated=truncated,
    )
    return text.rstrip() + "\n", report


def scan_for_brand_leaks(text: str) -> tuple[str, ...]:
    """Public helper used by the naming guard tests."""
    return _scan_brands(text)


__all__ = [
    "BLOCKED_BRANDS",
    "ALLOWED_SURFACE_NAMES",
    "FinalizationReport",
    "finalize",
    "scan_for_brand_leaks",
]
