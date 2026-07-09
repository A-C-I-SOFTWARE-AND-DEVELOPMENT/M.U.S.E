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

Beyond the core trio, the preset ships an **extended roster** of three more
seats — ``researcher``, ``operator``, ``scribe`` — for teams that want the
full bench. Every model routes through OpenRouter, so one
``OPENROUTER_API_KEY`` serves the whole roster.

Installed interactively via ``hermes setup trio`` (or offered at the end of
the full setup wizard). Headless installs call :func:`install_trio` directly::

    python -c "from hermes_cli.orchestrator_trio import install_trio; install_trio(extended=True)"
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

# Extended bench: three more seats for teams that want the full roster.
# Same conservative install semantics as the trio. Models are existing
# catalog entries (openrouter/kimi-k2, openrouter/deepseek-v4,
# openrouter/minimax-m2) — candidate-tagged, confirm availability before spend.
EXTENDED_ROLES: tuple[TrioRole, ...] = (
    TrioRole(
        profile="researcher",
        provider="openrouter",
        model="moonshotai/kimi-k2",
        catalog_ref="openrouter/kimi-k2",
        title="Long-context researcher (Kimi K2)",
        description=(
            "Long-context researcher. Gathers sources, reads docs and "
            "codebases, compares options, and summarizes evidence with "
            "citations before decisions are made. Route research, "
            "investigation, comparison, and documentation-reading tasks "
            "here. Not a builder — no file edits."
        ),
    ),
    TrioRole(
        profile="operator",
        provider="openrouter",
        model="deepseek/deepseek-v4",
        catalog_ref="openrouter/deepseek-v4",
        title="Operations & infrastructure seat (DeepSeek-V4)",
        description=(
            "Operations seat. Handles environment setup, dependency and "
            "CI upkeep, release preparation, and long maintenance chores. "
            "Irreversible actions (deploy, publish, spend) stay behind the "
            "owner gates. Route ops, environment, CI, and maintenance "
            "tasks here."
        ),
    ),
    TrioRole(
        profile="scribe",
        provider="openrouter",
        model="minimax/minimax-m2",
        catalog_ref="openrouter/minimax-m2",
        title="Documentation & knowledge curator (MiniMax-M2)",
        description=(
            "Documentation and knowledge curator. Writes docs, changelogs, "
            "and job summaries; keeps roster descriptions and the memory "
            "tree fresh. Route documentation, summarization, and "
            "knowledge-curation tasks here."
        ),
    ),
)

# The full bench: core trio + extended seats.
FULL_ROSTER: tuple[TrioRole, ...] = TRIO_ROLES + EXTENDED_ROLES

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
    """Report which roster seats are installed and what model each is pinned to.

    Covers the full roster (trio + extended seats). Returns
    ``{profile: {"installed": bool, "model": str|None}}``.
    """
    from hermes_cli import profiles as profiles_mod

    status: dict = {}
    for role in FULL_ROSTER:
        profile_dir = profiles_mod.get_profile_dir(role.profile)
        model = None
        if profile_dir.is_dir():
            model, _provider = profiles_mod._read_config_model(profile_dir)
        status[role.profile] = {
            "installed": profile_dir.is_dir(),
            "model": model,
        }
    return status


def export_seat_distributions(
    dest_dir: Path | str, *, extended: bool = True, version: str = "1.0.0"
) -> dict:
    """Stage each installed seat profile as a single-profile distribution.

    Local staging ONLY: writes ``<dest_dir>/<seat>/`` directories, each a
    ready-to-share profile distribution (``distribution.yaml`` manifest plus
    the profile payload). Credentials never ship — ``auth.json`` / ``.env`` /
    ``memories`` / ``sessions`` and every other user-owned path are stripped
    by the same ``USER_OWNED_EXCLUDE`` machinery ``hermes profile install``
    protects on update. No git init, no push, no network: publishing a staged
    distribution anywhere (repo creation, push, package publish) is a
    separate, owner-gated step.

    One distribution == one profile (the profile-distribution contract), so
    each seat stages independently under its own directory. Every manifest
    requires ``OPENROUTER_API_KEY`` — the one key that serves the whole
    roster — which installers surface via the generated ``.env.EXAMPLE``.

    Seats whose profile isn't installed are skipped, never fabricated.
    Returns::

        {"exported": [seat, ...], "skipped": [seat, ...], "dest": str}
    """
    from hermes_cli import profiles as profiles_mod
    from hermes_cli.profile_distribution import (
        DistributionManifest,
        EnvRequirement,
        _copy_dist_payload,
    )

    dest = Path(dest_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    roster = FULL_ROSTER if extended else TRIO_ROLES
    exported: list[str] = []
    skipped: list[str] = []
    for role in roster:
        profile_dir = profiles_mod.get_profile_dir(role.profile)
        if not profile_dir.is_dir():
            skipped.append(role.profile)
            continue
        manifest = DistributionManifest(
            name=role.profile,
            version=version,
            description=role.description,
            env_requires=[
                EnvRequirement(
                    name="OPENROUTER_API_KEY",
                    description="OpenRouter API key — routes every roster seat's model",
                )
            ],
        )
        # Reuse the distribution copy machinery: it skips every
        # USER_OWNED_EXCLUDE path (auth.json, .env, memories/, sessions/, …)
        # at every depth, emits .env.EXAMPLE from env_requires, and writes
        # the manifest into the staged tree last.
        _copy_dist_payload(
            profile_dir, dest / role.profile, manifest, preserve_config=False
        )
        # Second scrub pass: gateway/channel credentials that live under
        # names USER_OWNED_EXCLUDE doesn't cover (Slack bot tokens,
        # WhatsApp/Signal session keys, misc *.session / *tokens* files).
        # A staged distribution must never carry a live credential.
        _scrub_staged_credentials(dest / role.profile)
        exported.append(role.profile)

    return {"exported": exported, "skipped": skipped, "dest": str(dest)}


# Channel/gateway credential artifacts stripped from staged distributions
# in addition to profile_distribution.USER_OWNED_EXCLUDE. Directory names
# match whole path components; file patterns are glob-matched at any depth.
_EXPORT_CREDENTIAL_DIRS = frozenset({"whatsapp", "signal", "cookies"})
_EXPORT_CREDENTIAL_GLOBS = ("*.session", "*tokens*.json", "*_token.json", "*.cookies")


def _scrub_staged_credentials(staged_root: Path) -> None:
    """Remove channel credentials from a staged distribution tree."""
    import shutil

    if not staged_root.is_dir():
        return
    for path in sorted(staged_root.rglob("*"), reverse=True):
        try:
            if path.is_dir() and path.name in _EXPORT_CREDENTIAL_DIRS:
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file() and any(
                path.match(g) for g in _EXPORT_CREDENTIAL_GLOBS
            ):
                path.unlink(missing_ok=True)
        except OSError:
            logger.warning("could not scrub %s from staged export", path)


def install_trio(*, force: bool = False, extended: bool = False) -> dict:
    """Install (or repair) the orchestrator-roster profiles and kanban routing.

    Installs the core trio by default; pass ``extended=True`` to install the
    full six-seat roster (trio + researcher/operator/scribe).

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

    roster = FULL_ROSTER if extended else TRIO_ROLES
    for role in roster:
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
    )
    from hermes_cli.setup import prompt_choice

    print_header("Orchestrator Seats (optional)")
    print_info("A ready-made agent team for /orchestrate and kanban. Core trio:")
    for role in TRIO_ROLES:
        print_info(f"   {role.profile:<13s} {role.title}")
    print_info("Extended bench (full roster):")
    for role in EXTENDED_ROLES:
        print_info(f"   {role.profile:<13s} {role.title}")
    print_info("Each seat is its own hermes profile with its own memory, skills,")
    print_info("and SOUL.md, so every seat keeps improving across jobs.")
    print_info("All models route via OpenRouter — one OPENROUTER_API_KEY.")
    print()

    choice = prompt_choice(
        "Install the orchestrator seats?",
        [
            "Skip for now",
            "Core trio — orchestrator / executor / critic",
            "Full roster — trio + researcher / operator / scribe",
        ],
        0,
    )
    if choice == 0:
        print_info("Skipped — install later with 'hermes setup trio'.")
        return

    summary = install_trio(extended=(choice == 2))

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
