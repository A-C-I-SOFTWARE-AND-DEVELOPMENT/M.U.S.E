"""Runtime forge — mint a niche specialist when the pool has a gap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence
import re

from hermes_cli.jarvis_prime.niches.schema import NicheSpec, slugify_capability
from hermes_cli.jarvis_prime.niches.loader import (
    load_niche,
    update_runtime_registry,
    write_niche,
    niches_dir,
)

MAX_NICHES_ON_DISK = 500


@dataclass
class ForgeResult:
    ok: bool
    spec: Optional[NicheSpec] = None
    path: str = ""
    message: str = ""
    created: bool = False


def _count_niches() -> int:
    return len(list(niches_dir().glob("*.yaml")))


def forge_niche(
    capability: str,
    *,
    domain: Optional[str] = None,
    toolsets: Optional[Sequence[str]] = None,
    model_lane: str = "muse-local",
    force: bool = False,
) -> ForgeResult:
    """Create (or return existing) niche YAML for ``capability``.

    Does NOT write into curated AOS registry.json — only niches/runtime_registry.json.
    """
    capability = (capability or "").strip()
    if not capability:
        return ForgeResult(ok=False, message="capability required")

    # Prefer existing exact/near match
    slug = slugify_capability(capability)
    if domain:
        niche_id = f"{re.sub(r'[^a-z0-9]+', '-', domain.lower()).strip('-')}.{slug}"
    else:
        # first token as domain if capability looks like "security: foo"
        if ":" in capability:
            left, right = capability.split(":", 1)
            niche_id = f"{slugify_capability(left).replace('.', '-')}.{slugify_capability(right)}"
        else:
            parts = slug.split(".")
            niche_id = f"{parts[0]}.{'.'.join(parts[1:])}" if len(parts) > 1 else f"general.{slug}"

    # normalize id to schema (max 5 segments)
    segs = [s for s in niche_id.split(".") if s][:5]
    niche_id = ".".join(segs)
    if len(segs) < 2:
        niche_id = f"general.{segs[0] if segs else 'helper'}"

    existing = load_niche(niche_id)
    if existing and not force:
        return ForgeResult(
            ok=True,
            spec=existing,
            path=str(niches_dir() / f"{existing.id}.yaml"),
            message=f"niche already exists: {existing.id}",
            created=False,
        )

    if _count_niches() >= MAX_NICHES_ON_DISK and not existing:
        return ForgeResult(
            ok=False,
            message=f"niche cap reached ({MAX_NICHES_ON_DISK})",
        )

    dom = domain or niche_id.split(".", 1)[0]
    kws = tuple(
        dict.fromkeys(
            re.findall(r"[a-z0-9]{3,}", capability.lower())[:12]
            + list(dom.split("-"))
        )
    )
    if not kws:
        kws = (dom, "specialist")

    tools = tuple(toolsets) if toolsets else ("filesystem", "codebase", "web")
    system = (
        f"You are the AXIOM niche specialist `{niche_id}` for domain `{dom}`. "
        f"Capability focus: {capability.strip()}. "
        "Be precise, cite evidence from Scout packets when present, and stay in scope."
    )
    scout_queries = (
        f"{capability} best practices",
        f"repo: {capability}",
        f"docs: {capability}",
    )

    spec = NicheSpec(
        id=niche_id,
        domain=dom,
        keywords=kws,
        system=system,
        toolsets=tools,
        scout_queries=scout_queries,
        model_lane=model_lane,
        max_iterations=25,
        description=capability[:200],
    )
    path = write_niche(spec)
    update_runtime_registry(spec, forged=True)

    # Invalidate agent pool so the next route() sees the niche
    try:
        from hermes_cli.jarvis_prime.agent_pool import invalidate_pool

        invalidate_pool()
    except Exception:
        pass

    return ForgeResult(
        ok=True,
        spec=spec,
        path=str(path),
        message=f"forged niche {spec.id}",
        created=True,
    )
