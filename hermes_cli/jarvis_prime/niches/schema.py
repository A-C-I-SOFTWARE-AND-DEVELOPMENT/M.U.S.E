"""NicheSpec schema — thin specialist definition (not a full SKILL.md)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence
import re

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*){1,4}$")


@dataclass(frozen=True)
class NicheSpec:
    """One niche AXIOM specialist."""

    id: str
    domain: str
    keywords: tuple[str, ...]
    system: str
    toolsets: tuple[str, ...] = ("filesystem", "codebase")
    scout_queries: tuple[str, ...] = ()
    model_lane: str = "muse-local"
    max_iterations: int = 25
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["keywords"] = list(self.keywords)
        d["toolsets"] = list(self.toolsets)
        d["scout_queries"] = list(self.scout_queries)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NicheSpec":
        validate_niche_dict(data)
        return cls(
            id=str(data["id"]).strip(),
            domain=str(data["domain"]).strip(),
            keywords=tuple(str(k).strip() for k in data.get("keywords") or () if str(k).strip()),
            system=str(data["system"]).strip(),
            toolsets=tuple(
                str(t).strip() for t in (data.get("toolsets") or ("filesystem", "codebase"))
                if str(t).strip()
            ),
            scout_queries=tuple(
                str(q).strip() for q in (data.get("scout_queries") or ()) if str(q).strip()
            ),
            model_lane=str(data.get("model_lane") or "muse-local").strip(),
            max_iterations=int(data.get("max_iterations") or 25),
            description=str(data.get("description") or "").strip(),
        )

    def on_task_suffix(self) -> str:
        return (
            "\n\nRules: Stay on your niche. Prefer Scout packets already on the "
            "blackboard (SCOUT/*) over re-searching. Only search again on a clear "
            "Scout miss. End with a short verification note."
        )


def validate_niche_dict(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("niche must be a mapping")
    nid = str(data.get("id") or "").strip()
    if not nid or not _ID_RE.match(nid):
        raise ValueError(
            f"invalid niche id {nid!r} — expect dotted slug like domain.slice.focus"
        )
    if not str(data.get("domain") or "").strip():
        raise ValueError("niche.domain required")
    if not str(data.get("system") or "").strip():
        raise ValueError("niche.system required")
    kws = data.get("keywords") or []
    if not isinstance(kws, (list, tuple)) or len(kws) < 1:
        raise ValueError("niche.keywords must be a non-empty list")
    iters = int(data.get("max_iterations") or 25)
    if iters < 1 or iters > 200:
        raise ValueError("max_iterations out of range")


def slugify_capability(capability: str) -> str:
    """Turn free text into a dotted niche id fragment."""
    words = re.findall(r"[a-z0-9]+", capability.lower())
    words = [w for w in words if len(w) >= 2][:6]
    if len(words) < 2:
        words = (words + ["general", "helper"])[:2]
    return ".".join(words[:4])
