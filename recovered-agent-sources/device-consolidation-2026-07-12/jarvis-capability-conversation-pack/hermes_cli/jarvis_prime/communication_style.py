"""Jarvis Prime communication style.

A style preset is a small bag of knobs that the response shapes layer on
top of the chosen mode and surface. The conversation engine asks for a
preset given a mode + surface + depth, and then formats the actual answer
using those knobs. The presets are the source of truth for "how long",
"how many lines", "use bullets vs prose", and so on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from hermes_cli.jarvis_prime.modes import Mode


class Depth(str, Enum):
    """How much room the response should take."""

    BRIEF = "brief"
    NORMAL = "normal"
    DEEP = "deep"


class StyleSurface(str, Enum):
    """Conversation-level surfaces used by the style picker.

    The capability layer has its own ``Surface`` enum tuned for routing.
    This one is tuned for *display* — how the rendered text should look.
    """

    MOBILE = "mobile"
    TERMUX = "termux"
    SLACK = "slack"
    APP = "app"
    VOICE = "voice"
    FOCUSED = "focused"


@dataclass(frozen=True)
class StylePreset:
    """Knobs the response renderer reads to format a final answer."""

    name: str
    max_lines: int
    use_bullets: bool
    use_headers: bool
    allow_code_blocks: bool
    allow_diffs: bool
    target_sentences: int
    conversational: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


# Base presets keyed by depth — surface/mode overlays apply on top.
_DEPTH_BASE: dict[Depth, StylePreset] = {
    Depth.BRIEF: StylePreset(
        name="brief",
        max_lines=6,
        use_bullets=False,
        use_headers=False,
        allow_code_blocks=False,
        allow_diffs=False,
        target_sentences=2,
        conversational=True,
    ),
    Depth.NORMAL: StylePreset(
        name="normal",
        max_lines=18,
        use_bullets=True,
        use_headers=False,
        allow_code_blocks=True,
        allow_diffs=False,
        target_sentences=5,
        conversational=True,
    ),
    Depth.DEEP: StylePreset(
        name="deep",
        max_lines=120,
        use_bullets=True,
        use_headers=True,
        allow_code_blocks=True,
        allow_diffs=True,
        target_sentences=20,
        conversational=False,
    ),
}


_MOBILE_LIKE: frozenset[StyleSurface] = frozenset(
    {StyleSurface.MOBILE, StyleSurface.TERMUX, StyleSurface.VOICE}
)


def style_for_surface(surface: StyleSurface, depth: Depth = Depth.NORMAL) -> StylePreset:
    """Pick a preset given a surface and depth.

    Mobile-like surfaces always clamp to brief defaults, ignoring deeper
    depth requests. Focused and app surfaces respect the caller's depth.
    """
    if surface in _MOBILE_LIKE:
        base = _DEPTH_BASE[Depth.BRIEF]
        return StylePreset(
            name=f"{surface.value}-brief",
            max_lines=min(base.max_lines, 8) if surface != StyleSurface.VOICE else 4,
            use_bullets=False,
            use_headers=False,
            allow_code_blocks=False,
            allow_diffs=False,
            target_sentences=2 if surface != StyleSurface.VOICE else 1,
            conversational=True,
            notes=(
                f"Mobile-like surface ({surface.value}); long output deferred to focused mode.",
            ),
        )

    if surface == StyleSurface.SLACK:
        base = _DEPTH_BASE[depth]
        return StylePreset(
            name=f"slack-{depth.value}",
            max_lines=min(base.max_lines, 24),
            use_bullets=base.use_bullets,
            use_headers=False,
            allow_code_blocks=base.allow_code_blocks,
            allow_diffs=False,
            target_sentences=base.target_sentences,
            conversational=base.conversational,
            notes=("Slack surface; avoid raw diffs and oversized blocks.",),
        )

    return _DEPTH_BASE[depth]


def style_for_mode(mode: Mode, surface: StyleSurface, depth: Depth = Depth.NORMAL) -> StylePreset:
    """Pick a preset for a mode + surface + depth.

    Builder mode upgrades to structured presentation on focused/app surfaces.
    Companion mode pulls toward conversational prose. Mobile voice mode is
    always brief.
    """
    if mode == Mode.MOBILE_VOICE:
        return style_for_surface(StyleSurface.VOICE, Depth.BRIEF)

    base = style_for_surface(surface, depth)

    if mode == Mode.BUILDER and surface in {StyleSurface.FOCUSED, StyleSurface.APP} and depth == Depth.DEEP:
        return StylePreset(
            name="builder-deep",
            max_lines=200,
            use_bullets=True,
            use_headers=True,
            allow_code_blocks=True,
            allow_diffs=True,
            target_sentences=30,
            conversational=False,
            notes=("Builder mode on focused surface; structured packet expected.",),
        )

    if mode == Mode.COMPANION:
        return StylePreset(
            name=f"companion-{base.name}",
            max_lines=base.max_lines,
            use_bullets=False,
            use_headers=False,
            allow_code_blocks=False,
            allow_diffs=False,
            target_sentences=max(base.target_sentences, 3),
            conversational=True,
            notes=base.notes + ("Companion voice; prose over bullets.",),
        )

    if mode == Mode.CRITIC and depth != Depth.DEEP:
        return StylePreset(
            name=f"critic-{base.name}",
            max_lines=base.max_lines,
            use_bullets=True,
            use_headers=False,
            allow_code_blocks=base.allow_code_blocks,
            allow_diffs=False,
            target_sentences=base.target_sentences,
            conversational=base.conversational,
            notes=base.notes + ("Critic voice; lead with strongest objection.",),
        )

    return base


__all__ = [
    "Depth",
    "StyleSurface",
    "StylePreset",
    "style_for_surface",
    "style_for_mode",
]
