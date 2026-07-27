"""forge_niche tool — mint a thin AXIOM niche specialist at runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error

FORGE_NICHE_SCHEMA: Dict[str, Any] = {
    "name": "forge_niche",
    "description": (
        "Create (or reuse) a thin AXIOM niche specialist YAML for a capability. "
        "Registers into the niche pool for routing; does NOT modify curated AOS "
        "registry.json. Use when no existing niche matches the task well."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "capability": {
                "type": "string",
                "description": "What the niche should specialize in (free text).",
            },
            "domain": {
                "type": "string",
                "description": "Optional domain tag (e.g. security, hazmat-command, qa).",
            },
            "toolsets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional toolset allowlist (default: filesystem, codebase, web).",
            },
            "force": {
                "type": "boolean",
                "description": "Overwrite an existing niche with the same id.",
            },
        },
        "required": ["capability"],
    },
}


def check_forge_niche_requirements() -> Optional[str]:
    return None


def forge_niche_tool(
    capability: Optional[str] = None,
    domain: Optional[str] = None,
    toolsets: Optional[List[str]] = None,
    force: bool = False,
    **_kw: Any,
) -> str:
    try:
        from hermes_cli.jarvis_prime.niches.forge import forge_niche
    except Exception as exc:
        return tool_error(f"forge_niche import failed: {exc}")

    result = forge_niche(
        capability or "",
        domain=domain,
        toolsets=toolsets,
        force=bool(force),
    )
    if not result.ok:
        return tool_error(result.message)
    status = "created" if result.created else "existing"
    spec = result.spec
    return (
        f"forge_niche {status}: id={spec.id if spec else '?'} "
        f"domain={spec.domain if spec else '?'} path={result.path}\n"
        f"{result.message}"
    )


registry.register(
    name="forge_niche",
    toolset="delegation",
    schema=FORGE_NICHE_SCHEMA,
    handler=lambda args, **kw: forge_niche_tool(
        capability=args.get("capability"),
        domain=args.get("domain"),
        toolsets=args.get("toolsets"),
        force=bool(args.get("force") or False),
        **kw,
    ),
    check_fn=check_forge_niche_requirements,
    emoji="⚒️",
)
