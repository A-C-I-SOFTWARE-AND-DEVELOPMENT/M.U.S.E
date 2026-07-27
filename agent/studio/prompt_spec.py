"""Deterministic one-prompt parser for the first UE5 vertical-slice proof."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from .types import GameProductionSpec, VerticalSliceSpec


_GENRES = (
    "action rpg", "action-rpg", "survival horror", "stealth", "adventure",
    "shooter", "platformer", "rpg", "horror", "fantasy", "sci-fi",
)
_STYLES = (
    "photorealistic", "stylized realism", "painterly", "cel-shaded",
    "low-poly", "dark fantasy", "solarpunk", "cyberpunk",
)


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "", value.title())
    if not value:
        return "MuseGeneratedGame"
    if value[0].isdigit():
        value = f"Game{value}"
    return value[:48]


def _title(prompt: str) -> str:
    quoted = re.search(r"[\"“]([^\"”]{2,60})[\"”]", prompt)
    if quoted:
        return quoted.group(1).strip()
    prefix = re.match(r"\s*([A-Za-z0-9][^:.\n]{2,50})\s*:", prompt)
    if prefix:
        return prefix.group(1).strip()
    meaningful = [
        word.capitalize()
        for word in re.findall(r"[A-Za-z][A-Za-z'-]+", prompt)
        if word.lower() not in {
            "make", "build", "create", "generate", "game", "a", "an", "the",
            "with", "where", "about", "from", "into", "and", "of",
        }
    ]
    return " ".join(meaningful[:3]) or "Untitled Muse Game"


def _first_match(prompt: str, choices: tuple[str, ...], default: str) -> str:
    lowered = prompt.lower()
    return next((choice for choice in choices if choice in lowered), default)


def parse_vertical_slice_prompt(prompt: str) -> VerticalSliceSpec:
    """Convert a single prompt to a stable, validated build specification.

    The parser deliberately uses transparent heuristics instead of an LLM so the
    same prompt always produces byte-for-byte equivalent planning inputs.
    """

    cleaned = " ".join(prompt.split())
    if len(cleaned) < 20:
        raise ValueError(
            "Describe the game world, player fantasy, and objective in at least 20 characters"
        )
    title = _title(cleaned)
    genre = _first_match(cleaned, _GENRES, "third-person action adventure")
    style = _first_match(cleaned, _STYLES, "stylized realism")
    lowered = cleaned.lower()
    setting = cleaned
    for marker in (" set in ", " set on ", " across ", " inside "):
        if marker in lowered:
            setting = cleaned[lowered.index(marker) + len(marker):].rstrip(".")
            break
    setting = setting[:180]
    digest = hashlib.sha256(cleaned.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:4], "big") & 0x7FFFFFFF

    theme_words = [
        word.capitalize()
        for word in re.findall(r"[A-Za-z][A-Za-z'-]+", setting)
        if len(word) > 4
    ]
    anchors = (theme_words + ["Frontier", "Sanctum", "Citadel"])[:3]
    zones = (
        f"{anchors[0]} Approach",
        f"{anchors[1]} Crossing",
        f"{anchors[2]} Heart",
    )
    objective = (
        "Traverse all three zones, defeat their guardians, recover three "
        "relics, and activate the final beacon"
    )
    enemy = "ranged sentinel" if "shooter" in genre else "melee sentinel"

    return VerticalSliceSpec(
        prompt=cleaned,
        title=title,
        project_id=_slug(title),
        genre=genre,
        setting=setting,
        art_direction=f"{style}; cinematic lighting; readable combat silhouettes",
        player_verbs=("move", "look", "jump", "attack", "interact", "save"),
        objective=objective,
        zones=zones,
        enemy_archetype=enemy,
        seed=seed,
    )


def write_vertical_slice_spec(spec: VerticalSliceSpec, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(asdict(spec), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def to_game_production_spec(spec: VerticalSliceSpec) -> GameProductionSpec:
    return GameProductionSpec(
        title=spec.title,
        project_id=spec.project_id,
        engine="unreal",
        engine_version=spec.engine_version,
        platforms=("windows",),
        accessibility_requirements=(
            "subtitles",
            "keyboard and controller remapping",
            "master/music/sfx volume controls",
        ),
        rights_checklist=("generated asset provenance", "LingBot excluded from package"),
        save_schema_version=spec.save_schema_version,
        release_channels=("internal",),
        metadata={"vertical_slice": asdict(spec)},
    )


__all__ = [
    "parse_vertical_slice_prompt",
    "to_game_production_spec",
    "write_vertical_slice_spec",
]
