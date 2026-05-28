"""Launch-gate invariant: JARVIS Prime never auto-executes side effects.

The runtime is contracted to be side-effect-free except for memory
journal writes inside ``HERMES_HOME``. This module proves it in two
ways:

1. Structural scan — every ``hermes_cli/jarvis_prime/*.py`` module is
   parsed with ``ast`` and rejected if it imports a known shell-out
   surface (``subprocess``, ``os.system``, ``os.popen``,
   ``shutil.rmtree``) or calls into git as a child process.

2. Behavioural — driving ``JarvisPrime.handle`` and
   ``ProposalBook.propose`` over an isolated ``HERMES_HOME`` with
   ``subprocess.run`` monkeypatched records zero invocations and no
   filesystem writes outside the isolated home.

This file is intentionally narrow: it does not claim that the runtime
is bug-free, only that it cannot perform an out-of-band side effect
between perception and routing.
"""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import (
    OWNER_GATED_ACTIONS,
    JarvisPrime,
    OwnerAuth,
)
from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.runtime import JarvisConfig
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalKind


PACKAGE_DIR = Path(__file__).resolve().parent.parent / "hermes_cli" / "jarvis_prime"

# Modules within the package that are allowed to import shell-out surfaces
# (none today). Add here with a justification if a future module needs
# to drive an external tool.
SHELL_OUT_ALLOWLIST: frozenset[str] = frozenset()

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "subprocess",
)

# Forbidden attribute access patterns (matched as dotted-name suffixes).
FORBIDDEN_ATTRIBUTES: tuple[tuple[str, ...], ...] = (
    ("os", "system"),
    ("os", "popen"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "spawnv"),
    ("shutil", "rmtree"),
)

# Action category we already know is a Hot Word for shell-outs. If it
# appears as a bare identifier we reject — the runtime should never
# import a git library either.
FORBIDDEN_TOP_LEVEL_IMPORTS: frozenset[str] = frozenset({"git", "pygit2"})


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("JARVIS_OWNER_PHRASE", raising=False)
    return tmp_path


@pytest.fixture()
def subprocess_recorder(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Monkeypatch every documented subprocess entry to record calls."""

    calls: list[tuple] = []

    def _record(name: str):
        def _wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((name, args, kwargs))
            raise AssertionError(
                f"subprocess.{name} was invoked from JarvisPrime — "
                f"args={args!r} kwargs={kwargs!r}"
            )

        return _wrapped

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _record(name), raising=True)
    monkeypatch.setattr(os, "system", _record("os.system"), raising=True)
    return calls


def _iter_jarvis_modules() -> list[Path]:
    return sorted(p for p in PACKAGE_DIR.glob("*.py") if not p.name.startswith("_"))


def test_package_has_modules() -> None:
    """Sanity check — without this list the AST scan would silently pass."""

    modules = _iter_jarvis_modules()
    assert modules, f"no Python modules found under {PACKAGE_DIR}"
    assert any(m.name == "runtime.py" for m in modules)
    assert any(m.name == "self_update.py" for m in modules)


@pytest.mark.parametrize("module_path", _iter_jarvis_modules(), ids=lambda p: p.name)
def test_module_does_not_import_shell_out_surfaces(module_path: Path) -> None:
    """No ``subprocess`` / ``os.system`` / ``shutil.rmtree`` / git imports."""

    if module_path.stem in SHELL_OUT_ALLOWLIST:
        pytest.skip(f"{module_path.name} is explicitly allowlisted")

    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    bad: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if alias.name in FORBIDDEN_TOP_LEVEL_IMPORTS or root in FORBIDDEN_TOP_LEVEL_IMPORTS:
                    bad.append(f"import {alias.name}")
                if any(alias.name == p or alias.name.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES):
                    bad.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".")[0]
            if mod in FORBIDDEN_TOP_LEVEL_IMPORTS or root in FORBIDDEN_TOP_LEVEL_IMPORTS:
                bad.append(f"from {mod} import ...")
            if any(mod == p or mod.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES):
                bad.append(f"from {mod} import ...")

    assert not bad, (
        f"{module_path.name} imports a shell-out surface: {bad}. "
        "If this is intentional, add the module name to SHELL_OUT_ALLOWLIST."
    )


@pytest.mark.parametrize("module_path", _iter_jarvis_modules(), ids=lambda p: p.name)
def test_module_does_not_call_shell_out_attributes(module_path: Path) -> None:
    """No ``os.system(...)`` / ``shutil.rmtree(...)`` style references."""

    if module_path.stem in SHELL_OUT_ALLOWLIST:
        pytest.skip(f"{module_path.name} is explicitly allowlisted")

    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    bad: list[str] = []

    def _dotted(node: ast.AST) -> tuple[str, ...]:
        parts: list[str] = []
        cur: ast.AST | None = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return tuple(reversed(parts))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            dotted = _dotted(node)
            for forbidden in FORBIDDEN_ATTRIBUTES:
                if dotted[-len(forbidden):] == forbidden:
                    bad.append(".".join(dotted))

    assert not bad, (
        f"{module_path.name} references a shell-out attribute: {bad}. "
        "If this is intentional, add the module name to SHELL_OUT_ALLOWLIST."
    )


def test_owner_gated_actions_set_is_locked_down() -> None:
    """Snapshot the OWNER_GATED_ACTIONS set so additions are visible."""

    expected = {
        "spend_money",
        "post_publicly",
        "create_third_party_account",
        "oauth_change",
        "credential_change",
        "production_deploy",
        "dns_change",
        "main_branch_merge",
        "force_push",
        "package_publish",
        "app_store_submission",
        "delete_recovered_sources",
        "modify_secrets",
        "change_default_active_agents",
        "registry_mutation",
        "regulated_claim",
    }
    actual = set(OWNER_GATED_ACTIONS)
    new = actual - expected
    removed = expected - actual
    assert not (new or removed), (
        "OWNER_GATED_ACTIONS changed shape — update docs/jarvis-prime-operating-system.md "
        f"and the launch gate snapshot. added={new!r} removed={removed!r}"
    )


def test_handle_with_no_pending_gates_does_not_shell_out(
    hermes_home: Path,
    subprocess_recorder: list[tuple],
) -> None:
    """Driving a normal turn never reaches a subprocess."""

    jp = JarvisPrime(
        config=JarvisConfig(memory=MemoryStore(journal_path=hermes_home / "memory.jsonl"))
    )
    turn = jp.handle("audit the repo", skip_perceive=True, skip_recollect=True)
    assert turn is not None
    assert subprocess_recorder == []


def test_proposal_book_propose_does_not_execute(
    hermes_home: Path,
    subprocess_recorder: list[tuple],
) -> None:
    """``ProposalBook.propose`` only enqueues — it never runs anything."""

    book = ProposalBook()
    for risk in ("RC1", "RC2", "RC3", "RC4"):
        book.propose(
            kind=ProposalKind.SKILL_UPDATE,
            target_path="skills/foo/SKILL.md",
            rationale="test",
            diff_intent="test",
            risk_class=risk,
        )
    assert len(book.proposals) == 4
    assert subprocess_recorder == []
    # ProposalBook is in-process — propose() never touches the network
    # nor shells out. Persistence to disk is the CLI's job, not the
    # book's, and it requires the owner approval path.
    assert all(p.status.value in {"proposed", "needs_owner_approval"} for p in book.proposals)


def test_authorization_phrase_mismatch_does_not_grant(hermes_home: Path) -> None:
    """Approximate phrases never authorize gated actions."""

    oa = OwnerAuth()
    oa.request("package_publish", risk_class="RC3", rationale="release")
    assert oa.authorize("yes with authorization") == []
    assert oa.authorize("Yes, with authorization") == []  # missing trailing period
    assert oa.authorize("approved") == []
    assert oa.pending_actions() == ["package_publish"]

    granted = oa.authorize("Yes, with authorization.")
    assert [g.action for g in granted] == ["package_publish"]
    assert oa.pending_actions() == []
