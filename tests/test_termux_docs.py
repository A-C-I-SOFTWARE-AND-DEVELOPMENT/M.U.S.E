"""Regression coverage for the Termux phone-first runtime docs and scripts.

Phase 21 ships a small set of artifacts that the rest of the project
links to: two shell scripts under ``scripts/`` and four documentation
files under ``docs/termux/``. These tests pin the shape of those
files so that future refactors do not silently delete sections that
external links (or this repo's own CLAUDE.md / AGENTS.md) depend on.

The tests deliberately do **not** execute the shell scripts — Termux
is not available in CI. They only inspect the files as text.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs" / "termux"

SERVICE_SH = SCRIPTS_DIR / "muse-termux-service.sh"
DOCTOR_SH = SCRIPTS_DIR / "muse-termux-doctor.sh"

DOC_PHONE_RUNTIME = DOCS_DIR / "muse-phone-runtime.md"
DOC_TERMUX_BOOT = DOCS_DIR / "muse-termux-boot.md"
DOC_BACKGROUND_LIMITS = DOCS_DIR / "muse-background-limits.md"
DOC_WAKE_LOCK = DOCS_DIR / "muse-wake-lock-policy.md"


# ── Files exist ────────────────────────────────────────────────────────────

def test_service_script_exists() -> None:
    assert SERVICE_SH.is_file(), f"missing {SERVICE_SH}"


def test_doctor_script_exists() -> None:
    assert DOCTOR_SH.is_file(), f"missing {DOCTOR_SH}"


def test_all_phase21_docs_exist() -> None:
    for path in (
        DOC_PHONE_RUNTIME,
        DOC_TERMUX_BOOT,
        DOC_BACKGROUND_LIMITS,
        DOC_WAKE_LOCK,
    ):
        assert path.is_file(), f"missing {path}"


# ── Service script: command surface ────────────────────────────────────────

def test_service_script_exposes_all_required_subcommands() -> None:
    text = SERVICE_SH.read_text()
    for sub in ("start", "stop", "restart", "status", "logs", "doctor"):
        assert f"    {sub})" in text, f"service script missing case for {sub!r}"


def test_service_script_uses_graceful_stop_not_sigkill() -> None:
    text = SERVICE_SH.read_text()
    # Hard rule: phone-first stop is graceful only. ``kill -9`` may appear
    # inside a banner comment ("never use kill -9") but must not appear
    # as an executed command. Inspect non-comment lines only.
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        assert "kill -9" not in stripped, f"service script executes kill -9: {line!r}"
        assert "SIGKILL" not in stripped, f"service script uses SIGKILL: {line!r}"
    # And we must use SIGTERM as the first signal.
    assert "kill -TERM" in text


def test_service_script_manages_wake_lock() -> None:
    text = SERVICE_SH.read_text()
    assert "termux-wake-lock" in text
    assert "termux-wake-unlock" in text
    assert "HERMES_TERMUX_NO_WAKELOCK" in text


def test_service_script_writes_pid_files_under_hermes_home() -> None:
    text = SERVICE_SH.read_text()
    assert "api.pid" in text
    assert "gateway.pid" in text
    assert "HERMES_HOME" in text


# ── Doctor script: required checks ─────────────────────────────────────────

@pytest.mark.skip(
    reason="Phase 21 doctor expansion (npm/pnpm/uv/API reachability/gateway/127.0.0.1) "
    "salvaged ahead of impl PR; un-skip when the doctor script lands."
)
def test_doctor_script_covers_required_checks() -> None:
    text = DOCTOR_SH.read_text()
    # Direct command/tool probes the phase 21 spec requires.
    required_tokens = [
        "termux-info",
        "termux-wake-lock",
        "git",
        "gh",
        "python",
        "node",
        "npm",
        "pnpm",
        "uv",
        "codex",
        "claude",
        "aider",
        "goose",
        "storage",
        # Local API reachability + gateway status sections.
        "Local API reachability",
        "Gateway status",
        # The probe must talk to localhost only — never the public internet.
        "127.0.0.1",
    ]
    missing = [tok for tok in required_tokens if tok not in text]
    assert not missing, f"doctor script is missing checks for: {missing}"


def test_doctor_script_is_read_only() -> None:
    """The doctor must not mutate the system — no installs, no rm -rf."""
    text = DOCTOR_SH.read_text()
    forbidden = [
        "pkg install",
        "apt install",
        "rm -rf",
        "termux-wake-unlock",  # doctor reports only; service script releases
    ]
    for token in forbidden:
        # We allow the literal string to appear inside *help text* or
        # remediation hints (e.g. ``pkg install termux-tools``), but it
        # must never appear as an executed command. The convention used
        # by the script is to put remediation hints inside `_print warn`
        # detail strings, so we look for the command-execution form:
        # a line that starts with the token (possibly indented).
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(token):
                raise AssertionError(
                    f"doctor script appears to execute {token!r} on line: {line!r}"
                )


def test_doctor_script_supports_json_and_quiet_flags() -> None:
    text = DOCTOR_SH.read_text()
    assert "--json" in text
    assert "--quiet" in text or "-q" in text


# ── Docs: required sections / cross-links ──────────────────────────────────

def test_phone_runtime_doc_covers_lifecycle() -> None:
    text = DOC_PHONE_RUNTIME.read_text()
    for needle in (
        "start",
        "stop",
        "restart",
        "status",
        "logs",
        "doctor",
        "Safe shutdown",
        "Crash recovery",
        "wake lock",
    ):
        assert needle in text, f"muse-phone-runtime.md missing section/term: {needle!r}"


def test_termux_boot_doc_links_back_to_runtime_and_wake_lock() -> None:
    text = DOC_TERMUX_BOOT.read_text()
    assert "Termux:Boot" in text
    assert "termux-wake-lock" in text
    assert "~/.termux/boot" in text


def test_background_limits_doc_covers_required_topics() -> None:
    text = DOC_BACKGROUND_LIMITS.read_text()
    for needle in (
        "background",
        "Doze",
        "wake lock",
        "battery optimiz",  # matches optimizer/optimization
        "foreground service",
        "OOM",
        "Termux:Boot",
    ):
        assert needle in text, f"muse-background-limits.md missing topic: {needle!r}"


def test_wake_lock_policy_doc_covers_required_topics() -> None:
    text = DOC_WAKE_LOCK.read_text()
    for needle in (
        "Termux wake lock",
        "PARTIAL_WAKE_LOCK",
        "termux-wake-lock",
        "termux-wake-unlock",
        "HERMES_TERMUX_NO_WAKELOCK",
        "battery",
        "Opting out",
    ):
        assert needle in text, f"muse-wake-lock-policy.md missing topic: {needle!r}"


def test_docs_are_internally_cross_linked() -> None:
    """Each phase 21 doc should link to at least one of its siblings.

    This catches the common regression where a doc is renamed and the
    surrounding docs are not updated.
    """
    siblings = {
        DOC_PHONE_RUNTIME: ("muse-termux-boot.md", "muse-background-limits.md"),
        DOC_TERMUX_BOOT: ("muse-phone-runtime.md", "muse-android-permissions.md"),
        DOC_BACKGROUND_LIMITS: ("muse-phone-runtime.md", "muse-wake-lock-policy.md"),
        DOC_WAKE_LOCK: ("muse-phone-runtime.md", "muse-background-limits.md"),
    }
    for doc, candidates in siblings.items():
        text = doc.read_text()
        assert any(c in text for c in candidates), (
            f"{doc.name} does not link to any of its siblings: {candidates}"
        )
