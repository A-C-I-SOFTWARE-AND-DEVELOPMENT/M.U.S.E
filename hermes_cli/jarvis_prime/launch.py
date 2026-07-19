"""``hermes jarvis launch`` — one-command free-first JARVIS launch.

Runs the full launch path end to end:

1. muse runtime availability
2. free-first model bootstrap (writes the model policy)
3. memory path initialization (safe permissions)
4. owner-gate phrase enforcement
5. emergency-stop availability
6. slash-command availability (``/jarvis`` ``/jp`` ``/jarvis-prime``)
7. worker detection (Claude Code, Codex) — detection only
8. install/config sanity (launch-readiness doctor)

It finishes with a launch summary and the exact next commands: how to
start Hermes, invoke JARVIS, run the doctor, and stop JARVIS instantly.

Stdlib-only at import time. Heavy work is delegated to the bootstrap and
doctor modules, which are themselves stdlib-only + injectable for tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Optional


SLASH_INVOCATIONS: tuple[str, ...] = ("/jarvis", "/jp", "/jarvis-prime")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class LaunchStep:
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LaunchSummary:
    ok: bool
    steps: list[LaunchStep] = field(default_factory=list)
    bootstrap: dict[str, Any] = field(default_factory=dict)
    doctor: dict[str, Any] = field(default_factory=dict)
    next_commands: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "steps": [s.to_dict() for s in self.steps],
            "bootstrap": self.bootstrap,
            "doctor": self.doctor,
            "next_commands": self.next_commands,
        }

    def render(self) -> str:
        lines = ["muse — free-first launch", ""]
        for s in self.steps:
            lines.append(f"  {'✓' if s.ok else '✗'} {s.name}: {s.detail}")
        lines.append("")
        lines.append("Next commands:")
        lines.append(f"  Start muse:     {self.next_commands.get('start', 'hermes')}")
        lines.append(f"  Invoke JARVIS:  {self.next_commands.get('invoke', '/jarvis')}")
        lines.append(
            f"  Run doctor:     {self.next_commands.get('doctor', 'hermes doctor --jarvis-launch')}"
        )
        lines.append(
            f"  Stop JARVIS:    {self.next_commands.get('stop', '/jarvis stop')}"
        )
        lines.append("")
        if self.ok:
            lines.append("LAUNCH COMPLETE ✓  muse is ready.")
        else:
            lines.append(
                "LAUNCH BLOCKED ✗  — resolve the failing steps, then re-run `hermes jarvis launch`."
            )
        return "\n".join(lines)


def launch(
    *,
    free_first: bool = True,
    no_pull: bool = False,
    force: bool = False,
    local_only: bool = False,
    dry_run: bool = False,
    which: Optional[Callable[[str], Optional[str]]] = None,
    pull_runner: Optional[Callable[[str], tuple[bool, str]]] = None,
) -> LaunchSummary:
    """Run the full JARVIS launch path and return a structured summary."""
    from hermes_cli.jarvis_prime import launch_doctor as ld
    from hermes_cli.jarvis_prime import model_bootstrap as mb

    steps: list[LaunchStep] = []

    # 1. Runtime availability ------------------------------------------------
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        jp = JarvisPrime()
        jp.handle("launch", skip_perceive=True, skip_recollect=True)
        steps.append(LaunchStep("runtime", True, "muse runtime available"))
    except Exception as exc:
        steps.append(LaunchStep("runtime", False, f"runtime unavailable: {exc}"))

    # 2. Model bootstrap -----------------------------------------------------
    bootstrap_dict: dict[str, Any] = {}
    try:
        kwargs: dict[str, Any] = dict(
            free_first=free_first,
            jarvis=True,
            dry_run=dry_run,
            no_pull=no_pull,
            force=force,
            local_only=local_only,
        )
        if which is not None:
            kwargs["which"] = which
        if pull_runner is not None:
            kwargs["pull_runner"] = pull_runner
        result = mb.bootstrap(**kwargs)
        bootstrap_dict = result.to_dict()
        detail = "model policy " + (
            "written" if result.config_written else "planned (dry-run)"
        )
        if result.warnings:
            detail += f"; {len(result.warnings)} warning(s)"
        steps.append(LaunchStep("model_bootstrap", result.ok, detail))
    except Exception as exc:
        steps.append(LaunchStep("model_bootstrap", False, f"bootstrap failed: {exc}"))

    # 3. Memory path init ----------------------------------------------------
    try:
        base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
        mem_dir = Path(base) / "jarvis_prime"
        mem_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(mem_dir, 0o700)
        except OSError:
            pass
        steps.append(LaunchStep("memory", True, f"memory path ready: {mem_dir}"))
    except Exception as exc:
        steps.append(LaunchStep("memory", False, f"memory path init failed: {exc}"))

    # 4-8. Verification via the launch doctor --------------------------------
    report = ld.run_launch_doctor()
    doctor_dict = report.to_dict()

    def _by(name: str) -> Optional[ld.LaunchCheck]:
        for c in report.checks:
            if c.name == name:
                return c
        return None

    for step_name, check_name in (
        ("owner_gate", "owner_gate"),
        ("emergency_stop", "emergency_stop"),
    ):
        c = _by(check_name)
        steps.append(
            LaunchStep(
                step_name, bool(c and c.status == ld.PASS), c.detail if c else "missing"
            )
        )

    # Slash command availability — the activation skill must exist.
    skill = _repo_root() / "skills" / "jarvis-prime" / "SKILL.md"
    steps.append(
        LaunchStep(
            "slash_commands",
            skill.is_file(),
            f"activation skill present ({', '.join(SLASH_INVOCATIONS)})"
            if skill.is_file()
            else "skills/jarvis-prime/SKILL.md missing",
        )
    )

    # Worker detection (optional — never blocks launch).
    wl = _by("worker_lanes")
    steps.append(LaunchStep("workers", True, wl.detail if wl else "not detected"))

    # Install/config sanity.
    inst = _by("install_script")
    steps.append(
        LaunchStep(
            "install_sanity",
            bool(inst and inst.status == ld.PASS),
            inst.detail if inst else "n/a",
        )
    )

    next_commands = {
        "start": "hermes",
        "invoke": "/jarvis   (aliases: /jp, /jarvis-prime)",
        "doctor": "hermes doctor --jarvis-launch",
        "stop": "/jarvis stop   (or: python -m hermes_cli.jarvis_prime stop)",
    }

    # Launch is OK when every hard step passed AND the doctor's hard checks pass.
    hard_steps_ok = all(
        s.ok
        for s in steps
        if s.name
        in {"runtime", "model_bootstrap", "memory", "owner_gate", "emergency_stop"}
    )
    ok = hard_steps_ok and report.ok

    return LaunchSummary(
        ok=ok,
        steps=steps,
        bootstrap=bootstrap_dict,
        doctor=doctor_dict,
        next_commands=next_commands,
    )


__all__ = ["LaunchStep", "LaunchSummary", "SLASH_INVOCATIONS", "launch"]
