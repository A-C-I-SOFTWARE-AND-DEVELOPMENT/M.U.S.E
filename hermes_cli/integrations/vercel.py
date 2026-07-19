"""Vercel integration adapter.

Hermes uses Vercel for static and serverless deployments. The adapter
helps the agent:

- detect whether the ``vercel`` CLI is installed,
- build a deployment plan describing the target environment, project
  name, env vars, and the exact ``vercel`` argv that would be invoked,
- gate any preview deployment behind an explicit operator approval,
- gate production deployments behind a *separate, second* approval —
  preview-approval never escalates into production-approval.

The adapter never prints, stores, or transmits the value of an env var
— only its name. Operators set env vars via the Vercel dashboard or
``vercel env add`` themselves; Hermes only ever lists which vars the
deployment expects.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

__all__ = [
    "Detection",
    "EnvVarSpec",
    "VercelPlan",
    "VercelExecutionResult",
    "detect",
    "plan",
    "explain",
    "execute",
]


_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


@dataclass(frozen=True)
class Detection:
    cli_present: bool
    cli_path: Optional[str]
    project_root: Optional[Path]
    has_vercel_json: bool
    has_dot_vercel: bool
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnvVarSpec:
    """A required env var. The *value* is never stored here."""

    name: str
    targets: tuple[str, ...] = ("development", "preview", "production")
    description: str = ""
    secret: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.isidentifier():
            raise ValueError(f"invalid env var name: {self.name!r}")
        bad = set(self.targets) - {"development", "preview", "production"}
        if bad:
            raise ValueError(f"unknown vercel target(s): {sorted(bad)}")


@dataclass(frozen=True)
class VercelPlan:
    project_name: str
    target: str  # "preview" | "production"
    env_vars: list[EnvVarSpec]
    deploy_command: list[str]
    cli_present: bool
    requires_double_approval: bool
    approval_required: bool
    dry_run: bool
    rollback_notes: list[str]
    validation_steps: list[str]
    env_policy: list[str]


@dataclass(frozen=True)
class VercelExecutionResult:
    executed: bool
    deployed: bool
    target: str
    errors: list[str]


def detect(project_root: Optional[Path] = None) -> Detection:
    """Probe for the ``vercel`` CLI and project linkage."""
    cli_path = shutil.which("vercel")
    root = (project_root or Path.cwd()).resolve()
    has_json = (root / "vercel.json").is_file()
    has_dot = (root / ".vercel" / "project.json").is_file()
    notes: list[str] = []
    if cli_path is None:
        notes.append("`vercel` CLI not on PATH — install with `npm i -g vercel`.")
    if not has_dot:
        notes.append(
            "Project not linked — run `vercel link` interactively before "
            "the first deploy. muse will not run `vercel link` for you."
        )
    return Detection(
        cli_present=cli_path is not None,
        cli_path=cli_path,
        project_root=root,
        has_vercel_json=has_json,
        has_dot_vercel=has_dot,
        notes=notes,
    )


def _validate_project_name(name: str) -> str:
    n = (name or "").strip().lower()
    if not _PROJECT_NAME.match(n):
        raise ValueError(
            f"invalid Vercel project name {name!r}: "
            "must be lowercase alphanumerics + dashes, 1-100 chars, leading alphanumeric"
        )
    return n


def plan(
    *,
    project_name: str,
    target: str = "preview",
    env_vars: Optional[Sequence[EnvVarSpec]] = None,
    project_root: Optional[Path] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> VercelPlan:
    """Build a deployment plan for ``project_name`` against ``target``.

    ``target`` must be one of ``"preview"`` or ``"production"``. Both
    require an explicit operator approval; ``"production"`` additionally
    requires *double approval* (the preview must have shipped first OR
    the operator must explicitly confirm bypass).
    """
    name = _validate_project_name(project_name)
    tgt = (target or "preview").strip().lower()
    if tgt not in ("preview", "production"):
        raise ValueError(f"vercel target must be 'preview' or 'production', got {target!r}")

    argv: list[str] = ["vercel", "deploy"]
    if tgt == "production":
        argv.append("--prod")
    argv.extend(["--yes"])  # never interactive prompts; argv carries the intent
    if extra_args:
        argv.extend(extra_args)

    env_list = list(env_vars or [])
    rollback = [
        "Open the Vercel dashboard → Deployments → previous successful deployment → 'Promote to Production'.",
        "Or via CLI: `vercel rollback <deployment-url>` to revert to a known-good deployment.",
        "Never delete a deployment as a rollback — promotion is reversible, deletion is not.",
    ]
    validation = [
        "Wait for `vercel deploy` to print the deployment URL and exit 0.",
        "Open the preview URL in a browser and exercise the golden-path user flow.",
        "Hit the deployed `/api/_health` (or equivalent) and confirm a 200.",
        "If this was a production deploy, monitor error rates in the Vercel dashboard for the first 10 minutes before walking away.",
    ]
    env_policy = [
        "Env var *names* may be committed (e.g. in `.env.example`); values must not.",
        "Add or rotate secrets via `vercel env add` or the dashboard — muse never sends env values to Vercel.",
        "If an env var is missing for the target environment, the deploy will succeed but the app will fail at runtime — confirm presence in the dashboard first.",
        "Treat preview env vars as production-equivalent for any secret that grants real data access.",
    ]

    return VercelPlan(
        project_name=name,
        target=tgt,
        env_vars=env_list,
        deploy_command=argv,
        cli_present=detect(project_root).cli_present,
        requires_double_approval=(tgt == "production"),
        approval_required=True,
        dry_run=True,
        rollback_notes=rollback,
        validation_steps=validation,
        env_policy=env_policy,
    )


def explain(p: VercelPlan) -> str:
    """Render ``p`` as plain-English markdown."""
    lines: list[str] = []
    lines.append(f"### Vercel deploy plan — `{p.project_name}` → `{p.target}`")
    lines.append("")
    risk = "⚠️ PRODUCTION" if p.target == "production" else "preview"
    lines.append(
        f"I want to deploy project `{p.project_name}` to **{risk}** on Vercel."
    )
    lines.append("")
    lines.append(f"**Approval required:** {'yes' if p.approval_required else 'no'}")
    if p.requires_double_approval:
        lines.append(
            "**Double approval required:** yes — production deploys need a "
            "previous successful preview OR an explicit bypass acknowledgement."
        )
    lines.append(f"**`vercel` CLI present:** {'yes' if p.cli_present else 'no'}")
    lines.append("")
    lines.append("**Command I would run:**")
    lines.append("```bash")
    lines.append(" ".join(p.deploy_command))
    lines.append("```")
    lines.append("")
    if p.env_vars:
        lines.append("**Env vars this deployment expects (values managed in Vercel, not here):**")
        for ev in p.env_vars:
            tgts = ", ".join(ev.targets)
            sec = " (secret)" if ev.secret else ""
            desc = f" — {ev.description}" if ev.description else ""
            lines.append(f"- `{ev.name}`{sec} → {tgts}{desc}")
        lines.append("")
    lines.append("**Env-var policy:**")
    for note in p.env_policy:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("**Rollback:**")
    for note in p.rollback_notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("**Validation:**")
    for step in p.validation_steps:
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def execute(
    p: VercelPlan,
    *,
    approve: bool = False,
    approve_production: bool = False,
) -> VercelExecutionResult:
    """Refuses to deploy unless approval flags match the plan's risk.

    This adapter does NOT run ``vercel deploy`` automatically even when
    approved — the operator runs the command from ``p.deploy_command``
    themselves. The function exists to centralize the approval check so
    every caller goes through the same gate.
    """
    errors: list[str] = []
    if not approve:
        errors.append("approve=False — refused to mark deployment approved")
        return VercelExecutionResult(
            executed=False,
            deployed=False,
            target=p.target,
            errors=errors,
        )
    if p.requires_double_approval and not approve_production:
        errors.append(
            "production target requires approve_production=True — refused"
        )
        return VercelExecutionResult(
            executed=False,
            deployed=False,
            target=p.target,
            errors=errors,
        )
    # The actual `vercel deploy` invocation is left to the operator on
    # purpose — see the docstring. We return executed=True to signal
    # that the approval gate has been cleared.
    return VercelExecutionResult(
        executed=True,
        deployed=False,
        target=p.target,
        errors=errors,
    )
