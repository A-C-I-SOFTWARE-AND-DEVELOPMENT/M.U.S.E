"""Guards for the opt-in GPU helper scripts.

These never install anything in CI — they only check that the scripts parse,
expose a usage banner, and that `--dry-run` / `--print` describe the right plan
without touching the system.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTALL = _REPO_ROOT / "scripts" / "install-cuda.sh"
_MUSE_GPU = _REPO_ROOT / "scripts" / "muse-gpu.sh"
_DOC = _REPO_ROOT / "docs" / "gpu" / "using-nvidia-tools-anywhere.md"
_DOCKERFILE = _REPO_ROOT / "Dockerfile.cuda"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=30,
    )


# --- presence / shape -------------------------------------------------------


@pytest.mark.parametrize("path", [_INSTALL, _MUSE_GPU, _DOC, _DOCKERFILE])
def test_artifact_exists(path):
    assert path.exists(), f"missing {path}"


@pytest.mark.parametrize("script", [_INSTALL, _MUSE_GPU])
def test_scripts_are_executable(script):
    assert os.access(script, os.X_OK), f"{script.name} should be chmod +x"


@pytest.mark.parametrize("script", [_INSTALL, _MUSE_GPU])
def test_scripts_have_valid_bash_syntax(script):
    # `bash -n` parses without executing.
    res = _run("-n", str(script))
    assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("script", [_INSTALL, _MUSE_GPU])
def test_help_exits_zero_with_usage(script):
    res = _run(str(script), "--help")
    assert res.returncode == 0, res.stderr
    assert "Usage:" in res.stdout


# --- install-cuda.sh --dry-run plans (no system changes) --------------------


def test_install_dry_run_apt_plan():
    res = _run(str(_INSTALL), "--dry-run", "--mode", "apt")
    assert res.returncode == 0, res.stderr
    assert "nvidia-cuda-toolkit" in res.stdout
    assert "apt-get" in res.stdout
    assert "no changes made" in res.stdout.lower()


def test_install_dry_run_nvidia_repo_plan():
    res = _run(str(_INSTALL), "--dry-run", "--mode", "nvidia-repo", "--cuda-version", "12-6")
    assert res.returncode == 0, res.stderr
    assert "cuda-keyring" in res.stdout
    assert "cuda-toolkit-12-6" in res.stdout


def test_install_dry_run_pip_plan():
    res = _run(str(_INSTALL), "--dry-run", "--mode", "pip")
    assert res.returncode == 0, res.stderr
    assert "nvidia-cuda-nvcc-cu12" in res.stdout


def test_install_rejects_unknown_mode():
    res = _run(str(_INSTALL), "--mode", "bogus")
    assert res.returncode != 0
    assert "invalid --mode" in res.stderr


# --- muse-gpu.sh --print emits a GPU-passthrough docker command -------------


def test_muse_gpu_print_run_command():
    res = _run(str(_MUSE_GPU), "--print", "run", "echo", "hi")
    assert res.returncode == 0, res.stderr
    assert "docker run --rm --gpus all" in res.stdout
    assert "echo hi" in res.stdout


def test_muse_gpu_print_build_command():
    res = _run(str(_MUSE_GPU), "--print", "build")
    assert res.returncode == 0, res.stderr
    assert "docker build" in res.stdout
    assert "Dockerfile.cuda" in res.stdout


# --- doc consistency --------------------------------------------------------


def test_doc_references_each_helper():
    text = _DOC.read_text(encoding="utf-8")
    for token in (
        "scripts/install-cuda.sh",
        "scripts/muse-gpu.sh",
        "Dockerfile.cuda",
    ):
        assert token in text, f"{token} missing from {_DOC.name}"
