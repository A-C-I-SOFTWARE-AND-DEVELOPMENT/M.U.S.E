"""Orchestrator Trio preset — GLM-5.2 planner, LongCat-2.0 executor, Grok 4.5 critic.

Maps the "Orchestrator-Worker" harness pattern onto muse's existing five
primitives (Job, Worker profile, Model routing, Validation gate, Decision
ledger) instead of inventing new machinery:

- Each role is a named hermes **profile** (an isolated ``HERMES_HOME``), so
  every role keeps its own model, memory, skills, and ``SOUL.md``. Profiles
  accumulate experience across jobs — that persistence is what lets each
  role improve over time rather than starting cold on every run.
- **Planning** routes to the ``orchestrator`` profile via
  ``kanban.orchestrator_profile`` — GLM-5.2 is the only role that holds the
  heavy global context, and it decomposes goals into atomic tickets.
- **Execution** fans out to the ``executor`` profile via
  ``kanban.default_assignee`` and roster-description matching — LongCat-2.0
  sees only the files a ticket needs, never the whole repo.
- **Review** routes to the ``critic`` profile by description matching,
  preserving the builder ≠ reviewer separation muse already enforces
  (a builder never self-merges).

All three models route through OpenRouter, so one ``OPENROUTER_API_KEY``
serves the whole trio.

Installed interactively via ``hermes setup trio`` (or offered at the end of
the full setup wizard). Headless installs call :func:`install_trio` directly::

    python -c "from hermes_cli.orchestrator_trio import install_trio; install_trio()"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrioRole:
    """One role of the orchestrator trio, realized as a hermes profile."""

    profile: str
    provider: str
    model: str        # provider model slug written to <profile>/config.yaml
    catalog_ref: str  # provider/id handle in config/model-catalog.yaml
    title: str
    description: str  # roster description the kanban decomposer routes by


TRIO_ROLES: tuple[TrioRole, ...] = (
    TrioRole(
        profile="orchestrator",
        provider="openrouter",
        model="z-ai/glm-5.2",
        catalog_ref="openrouter/glm-5.2",
        title="Global orchestrator & planner (GLM-5.2)",
        description=(
            "Global planner and architect. Holds whole-repo context "
            "(1M tokens), decomposes goals into atomic dependency-mapped "
            "tasks, and guards module boundaries and architectural "
            "constraints across long jobs. Route planning, decomposition, "
            "and architecture questions here."
        ),
    ),
    TrioRole(
        profile="executor",
        provider="openrouter",
        model="meituan/longcat-2.0",
        catalog_ref="openrouter/longcat-2.0",
        title="Tactical executor & tool caller (LongCat-2.0)",
        description=(
            "Tactical builder. Implements one bounded ticket at a time: "
            "writes code, runs commands, edits files, and self-corrects "
            "when a tool call fails. Route implementation, coding, "
            "file-edit, and tool-execution tasks here."
        ),
    ),
    TrioRole(
        profile="critic",
        provider="openrouter",
        model="x-ai/grok-4.5",
        catalog_ref="openrouter/grok-4.5",
        title="Independent reviewer & critic (Grok 4.5)",
        description=(
            "Independent reviewer. Checks diffs against API contracts and "
            "architecture, hunts regressions and technical debt, and "
            "approves or rejects with a concrete critique. Route review, "
            "verification, and QA tasks here; never assign it its own "
            "build tasks."
        ),
    ),
)

# Kanban routing the preset wires up: planning goes to the orchestrator,
# unmatched work lands on the executor.
_KANBAN_WIRING = {
    "orchestrator_profile": "orchestrator",
    "default_assignee": "executor",
}


def _write_profile_model(profile_dir: Path, provider: str, model: str) -> None:
    """Set the ``model`` block in ``<profile_dir>/config.yaml``, preserving
    every other key the profile's config may already carry."""
    import yaml

    path = profile_dir / "config.yaml"
    data: dict = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            logger.warning("Unreadable %s — rewriting model block only", path)
            data = {}

    model_cfg = data.get("model")
    if isinstance(model_cfg, str) and model_cfg.strip():
        model_cfg = {"default": model_cfg.strip()}
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    model_cfg["provider"] = provider
    model_cfg["default"] = model
    data["model"] = model_cfg

    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def trio_status() -> dict:
    """Report which trio roles are installed and what model each is pinned to.

    Returns ``{profile: {"installed": bool, "model": str|None}}``.
    """
    from hermes_cli import profiles as profiles_mod

    status: dict = {}
    for role in TRIO_ROLES:
        profile_dir = profiles_mod.get_profile_dir(role.profile)
        model = None
        if profile_dir.is_dir():
            model, _provider = profiles_mod._read_config_model(profile_dir)
        status[role.profile] = {
            "installed": profile_dir.is_dir(),
            "model": model,
        }
    return status


def install_trio(*, force: bool = False) -> dict:
    """Install (or repair) the orchestrator-trio profiles and kanban routing.

    Idempotent and conservative by default: existing profiles are kept, a
    profile's model is only written when it has none, descriptions are only
    written when empty, and kanban routing keys are only set when unset —
    the preset never silently overwrites a choice the user already made.
    Pass ``force=True`` to re-pin models/descriptions/routing to the preset
    values.

    Returns a summary dict::

        {
          "created": [profile, ...],     # profiles created by this call
          "existing": [profile, ...],    # profiles that already existed
          "models_set": [profile, ...],  # profiles whose model was (re)written
          "kanban": {key: value, ...},   # routing keys this call set
        }
    """
    from hermes_cli import profiles as profiles_mod
    from hermes_cli.config import load_config, save_config

    summary: dict = {"created": [], "existing": [], "models_set": [], "kanban": {}}

    for role in TRIO_ROLES:
        profile_dir = profiles_mod.get_profile_dir(role.profile)
        if profile_dir.is_dir():
            summary["existing"].append(role.profile)
        else:
            profiles_mod.create_profile(
                role.profile, no_alias=True, description=role.description
            )
            summary["created"].append(role.profile)

        current_model, _ = profiles_mod._read_config_model(profile_dir)
        if force or not current_model:
            _write_profile_model(profile_dir, role.provider, role.model)
            summary["models_set"].append(role.profile)

        meta = profiles_mod.read_profile_meta(profile_dir)
        if force or not meta.get("description"):
            try:
                profiles_mod.write_profile_meta(
                    profile_dir, description=role.description, description_auto=False
                )
            except Exception:
                logger.debug(
                    "Could not write profile.yaml for %s", role.profile, exc_info=True
                )

    config = load_config()
    kanban = config.setdefault("kanban", {})
    if not isinstance(kanban, dict):
        kanban = {}
        config["kanban"] = kanban
    changed = False
    for key, value in _KANBAN_WIRING.items():
        if force or not kanban.get(key):
            if kanban.get(key) != value:
                kanban[key] = value
                changed = True
            summary["kanban"][key] = value
    if changed:
        save_config(config)

    return summary


def setup_trio(config: dict, *, quick: bool = False) -> None:
    """Setup-wizard section: offer and install the orchestrator trio.

    Opt-in (defaults to No) so the full wizard flow stays unchanged for
    users who just press Enter. ``config`` is re-synced in place after an
    install so the wizard's final ``save_config(config)`` doesn't clobber
    the kanban routing this section writes (same contract as
    ``setup_model_provider``, #4172).
    """
    from hermes_cli.cli_output import (
        print_header,
        print_info,
        print_success,
        prompt_yes_no,
    )

    print_header("Orchestrator Trio (optional)")
    print_info("A ready-made planner/executor/critic team for /orchestrate and kanban:")
    for role in TRIO_ROLES:
        print_info(f"   {role.profile:<13s} {role.title}")
    print_info("Each role is its own hermes profile with its own memory, skills,")
    print_info("and SOUL.md, so every role keeps improving across jobs.")
    print_info("All three models route via OpenRouter — one OPENROUTER_API_KEY.")
    print()

    if not prompt_yes_no("Install the orchestrator trio now?", False):
        print_info("Skipped — install later with 'hermes setup trio'.")
        return

    summary = install_trio()

    # Re-sync the wizard's config dict from disk (install_trio saved kanban
    # routing through its own load/save cycle).
    from hermes_cli.config import load_config

    refreshed = load_config()
    config.clear()
    config.update(refreshed)

    for name in summary["created"]:
        print_success(f"Created profile '{name}'")
    for name in summary["existing"]:
        print_info(f"Profile '{name}' already existed — kept as-is")
    if summary["kanban"]:
        wired = ", ".join(f"{k}={v}" for k, v in summary["kanban"].items())
        print_success(f"Kanban routing wired: {wired}")
    print()
    print_info("Try it:  /orchestrate <goal>   (planning runs on the orchestrator,")
    print_info("         work fans out to the executor, review routes to the critic)")
    print_info("Inspect: hermes profile list   ·   Re-pin models: install_trio(force=True)")
