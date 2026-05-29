"""JARVIS Prime ← OSS model brain bridge.

Thin, lazy adapter so the ``jarvis_prime`` package stays stdlib-only at
import time (it loads in Termux / slim CI). The heavy lifting — YAML
parsing, the catalog, provider discovery — lives in
``hermes_cli.oss_model_brain`` and is imported only when a recommendation
is actually requested.

Public API:

* ``recommend_models(task, ...)`` — ordered ``OssModel`` list for a task,
  by default filtered to providers installed on this host.
* ``render_recommendation(task, ...)`` — a compact human-readable block
  JARVIS Prime can print in Builder/Operator mode or the CLI.
* ``KNOWN_TASKS`` — the task categories the catalog routes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:  # avoid importing the heavy module at type-check / import time
    from hermes_cli.oss_model_brain import OssModel


KNOWN_TASKS = (
    "coding",
    "agentic_coding",
    "bug_fix",
    "code_edit",
    "reasoning",
    "math",
    "local_coding",
    "local_reasoning",
)


def recommend_models(
    task: str,
    *,
    local_only: bool = False,
    license_allow: Optional[Iterable[str]] = None,
    only_installed: bool = True,
) -> list["OssModel"]:
    """Return OSS models for ``task``, best first.

    When ``only_installed`` is True we filter to providers actually
    installed on this host — but only if the provider registry is
    importable. If it isn't (stripped-down install), we don't filter, so
    the recommendation still works as pure guidance.
    """
    from hermes_cli import oss_model_brain as ob

    catalog = ob.load_oss_catalog()
    available = ob.installed_provider_names() if only_installed else None
    return catalog.recommend(
        task,
        local_only=local_only,
        license_allow=license_allow,
        available_providers=available,
    )


def render_recommendation(
    task: str,
    *,
    local_only: bool = False,
    license_allow: Optional[Iterable[str]] = None,
    only_installed: bool = True,
    limit: int = 5,
) -> str:
    """Render a compact, human-readable recommendation block."""
    from hermes_cli import oss_model_brain as ob

    catalog = ob.load_oss_catalog()
    available = ob.installed_provider_names() if only_installed else None
    models = catalog.recommend(
        task,
        local_only=local_only,
        license_allow=license_allow,
        available_providers=available,
    )

    flags = []
    if local_only:
        flags.append("local-only")
    if license_allow:
        flags.append("license=" + ",".join(sorted(license_allow)))
    if only_installed and available is not None:
        flags.append("installed-providers-only")
    flag_str = f" [{'; '.join(flags)}]" if flags else ""

    header = (
        f"JARVIS Prime — OSS model brain · task: {task}{flag_str} "
        f"(catalog {catalog.updated_at or '?'}, {catalog.source})"
    )
    if not models:
        return (
            header + "\n  (no catalog match — try `models tasks` for known categories, "
            "or drop --installed / filters)"
        )

    lines = [header, ""]
    used_sources: list[str] = []
    for i, m in enumerate(models[:limit], 1):
        ref = m.resolve_provider(available)
        via = f"{ref.provider}:{ref.model}" if ref else "(no installed provider)"
        fallbacks = [
            p.provider for p in m.providers if not ref or p.provider != ref.provider
        ]
        fb = f"   (fallbacks: {', '.join(fallbacks)})" if fallbacks else ""
        ctx = f"{m.context_window // 1000}K ctx" if m.context_window else "ctx ?"
        bench = " · ".join(f"{k}={v:g}" for k, v in m.benchmarks)
        lines.append(f"  {i}. {m.id}  [{m.tier} · {m.license} · {ctx}]")
        lines.append(f"     via {via}{fb}")
        if bench:
            lines.append(f"     {bench}")
        if m.why:
            lines.append(f"     {m.why}")
        for s in m.sources:
            if s not in used_sources:
                used_sources.append(s)
        lines.append("")

    if used_sources:
        lines.append("Sources (validated " + (catalog.updated_at or "recently") + "):")
        for s in used_sources:
            lines.append(f"  - {s}")
    return "\n".join(lines).rstrip()
