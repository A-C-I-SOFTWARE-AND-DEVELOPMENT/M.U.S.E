"""Launch-gate proof: the JARVIS Prime per-action gating invariant.

The Python lane's "emergency stop" is enforced at the router boundary:
when an ``OwnerAuth`` instance has pending gated actions, every
subsequent ``JarvisPrime.handle`` call must route to
``RouteTarget.OWNER_DECISION`` regardless of intent text, regardless of
mode, and without running any side effects. This module locks that
invariant down across **every** value of ``OWNER_GATED_ACTIONS``.

What this test does NOT prove:

- A process-level kill-switch env var (``HERMES_DISABLE=1``). That is a
  tracked follow-up — see ``docs/launch/LAUNCH_TEST_GATE.md``.
- Side effects in downstream tools the runtime hands off to. Those
  belong to their respective subsystem tests.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import (
    AUTHORIZATION_PHRASE,
    OWNER_GATED_ACTIONS,
    OwnerAuth,
)
from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.router import RouteTarget
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("JARVIS_OWNER_PHRASE", raising=False)
    return tmp_path


@pytest.fixture()
def no_shell_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard-fail any subprocess invocation reached from JarvisPrime."""

    def _refuse(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            f"subprocess invocation reached from JarvisPrime: {args!r} {kwargs!r}"
        )

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _refuse, raising=True)
    monkeypatch.setattr(os, "system", _refuse, raising=True)


def _build_jp(home: Path, owner_auth: OwnerAuth | None = None) -> JarvisPrime:
    config = JarvisConfig(
        memory=MemoryStore(journal_path=home / "memory.jsonl"),
        owner_auth=owner_auth or OwnerAuth(),
    )
    return JarvisPrime(config=config)


@pytest.mark.parametrize("action", sorted(OWNER_GATED_ACTIONS))
def test_pending_owner_gate_routes_to_owner_decision(
    hermes_home: Path,
    no_shell_out: None,
    action: str,
) -> None:
    """For every gated action, ``handle`` short-circuits to owner_decision."""

    oa = OwnerAuth()
    oa.request(action, risk_class="RC3", rationale=f"test {action}")
    jp = _build_jp(hermes_home, owner_auth=oa)

    turn = jp.handle(
        intent=f"please {action} the thing right now",
        skip_perceive=True,
        skip_recollect=True,
    )

    assert turn.route.target is RouteTarget.OWNER_DECISION, (
        f"action {action!r} should route to OWNER_DECISION, got {turn.route.target}"
    )
    assert turn.route.requires_owner_authorization is True
    assert action in turn.route.pending_actions
    assert turn.route.rationale.startswith("owner-gated"), turn.route.rationale


def test_multiple_pending_gates_are_all_propagated(
    hermes_home: Path,
    no_shell_out: None,
) -> None:
    oa = OwnerAuth()
    oa.request("production_deploy", risk_class="RC3", rationale="release")
    oa.request("package_publish", risk_class="RC3", rationale="release")
    jp = _build_jp(hermes_home, owner_auth=oa)

    turn = jp.handle("ship the release", skip_perceive=True, skip_recollect=True)

    assert turn.route.target is RouteTarget.OWNER_DECISION
    assert set(turn.route.pending_actions) == {"production_deploy", "package_publish"}


def test_handle_with_pending_gate_writes_nothing_outside_hermes_home(
    hermes_home: Path,
    no_shell_out: None,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """No FS writes outside HERMES_HOME during a gated turn."""

    repo_root = Path(__file__).resolve().parent.parent
    sentinel_paths = (
        repo_root / "skills",
        repo_root / "hermes_cli",
        repo_root / "agent",
    )
    sentinel_sizes = {p: _dir_size_or_none(p) for p in sentinel_paths}

    oa = OwnerAuth()
    oa.request("production_deploy", risk_class="RC4", rationale="release")
    jp = _build_jp(hermes_home, owner_auth=oa)
    jp.handle("deploy v1.0.0", skip_perceive=True, skip_recollect=True)

    for p, before in sentinel_sizes.items():
        after = _dir_size_or_none(p)
        assert before == after, (
            f"directory size of {p} changed during a gated handle() call — "
            f"before={before} after={after}"
        )


def test_authorize_clears_pending_and_routes_normally(
    hermes_home: Path,
    no_shell_out: None,
) -> None:
    """The exact phrase clears gates and a subsequent handle routes normally."""

    oa = OwnerAuth()
    oa.request("package_publish", risk_class="RC3", rationale="release")
    jp = _build_jp(hermes_home, owner_auth=oa)

    assert jp.authorize(AUTHORIZATION_PHRASE) == ["package_publish"]
    assert oa.pending_actions() == []

    turn = jp.handle("ship the release", skip_perceive=True, skip_recollect=True)
    assert turn.route.target is not RouteTarget.OWNER_DECISION
    assert turn.route.requires_owner_authorization is False
    assert turn.route.pending_actions == ()


def test_owner_auth_request_rejects_unknown_action() -> None:
    """``OwnerAuth.request`` cannot silently grow the gated-action surface."""

    oa = OwnerAuth()
    with pytest.raises(ValueError, match="OWNER_GATED_ACTIONS"):
        oa.request("not_a_real_gate", risk_class="RC3")


def _dir_size_or_none(path: Path) -> int | None:
    """Sum file sizes under ``path`` excluding ``__pycache__`` (compile artifacts)."""

    if not path.exists():
        return None
    total = 0
    for sub in path.rglob("*"):
        if "__pycache__" in sub.parts:
            continue
        try:
            if sub.is_file():
                total += sub.stat().st_size
        except OSError:
            continue
    return total
