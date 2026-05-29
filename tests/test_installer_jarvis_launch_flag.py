"""Tests for the installer --jarvis-launch / -JarvisLaunch flag.

These are static checks against the shipped installers (no install is
actually run): the flag must be parsed, wired into the post-install
flow, and the bash installer must remain syntactically valid.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"


def test_install_sh_parses_jarvis_launch_flag() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "--jarvis-launch)" in text
    assert "JARVIS_LAUNCH=true" in text
    assert "JARVIS_LAUNCH=false" in text  # safe default


def test_install_sh_runs_bootstrap_and_doctor() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "models bootstrap --free-first --jarvis" in text
    assert "doctor --jarvis-launch" in text


def test_install_sh_jarvis_launch_is_opt_in_and_called_in_main() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    # The launch routine guards on the flag and main() invokes it.
    assert 'run_jarvis_launch()' in text
    assert '[ "$JARVIS_LAUNCH" = true ] || return 0' in text
    assert "\n    run_jarvis_launch\n" in text


def test_install_sh_unattended_uses_no_pull() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    # Unattended installs must not pull multi-GB models implicitly.
    assert "models bootstrap --free-first --jarvis --no-pull" in text


def test_install_sh_prints_recovery_commands() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "Recovery commands:" in text


def test_install_sh_help_documents_flag() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "--jarvis-launch After install" in text


def test_install_sh_is_valid_bash() -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    result = subprocess.run([bash, "-n", str(INSTALL_SH)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_install_ps1_has_jarvis_launch_parity() -> None:
    if not INSTALL_PS1.is_file():
        pytest.skip("install.ps1 not present")
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "[switch]$JarvisLaunch" in text
    assert "function Invoke-JarvisLaunch" in text
    assert "models bootstrap --free-first --jarvis --no-pull" in text
    assert "doctor --jarvis-launch" in text
    # Wired into Main.
    assert "Invoke-JarvisLaunch" in text
