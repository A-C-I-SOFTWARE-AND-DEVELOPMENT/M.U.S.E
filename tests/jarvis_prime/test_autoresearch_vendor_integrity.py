"""Vendor integrity: the autoresearch payload is byte-identical, inert data.

Two invariants:
1. Every vendored file's sha256 matches the committed ``checksums.json``
   manifest — nobody edits upstream files in-repo (the do-not-edit rule in
   ``VENDOR.md``); experiments mutate only workspace copies.
2. Importing the muse-side autoresearch packages never imports torch or any
   vendored module — the engine is GPU/owner-hardware only and must stay out
   of test collection and base-install import paths.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PKG_DIR = (
    Path(__file__).resolve().parents[2]
    / "hermes_cli"
    / "jarvis_prime"
    / "research_fabric"
    / "autoresearch"
)
VENDOR_DIR = PKG_DIR / "vendor"
EXPECTED_FILES = (
    "prepare.py",
    "train.py",
    "program.md",
    "README.md",
    "pyproject.toml",
    ".python-version",
)


def test_checksums_manifest_covers_exactly_the_vendored_files() -> None:
    manifest = json.loads((PKG_DIR / "checksums.json").read_text(encoding="utf-8"))
    assert sorted(manifest) == sorted(EXPECTED_FILES)
    on_disk = sorted(p.name for p in VENDOR_DIR.iterdir() if p.is_file())
    assert on_disk == sorted(EXPECTED_FILES), "unexpected file added to vendor/"


def test_vendored_files_are_byte_identical_to_manifest() -> None:
    manifest = json.loads((PKG_DIR / "checksums.json").read_text(encoding="utf-8"))
    for name, expected_sha in manifest.items():
        actual = hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"vendor/{name} was modified in-repo — vendored files are "
            "byte-identical upstream data (see VENDOR.md); muse adaptations "
            "belong in sibling modules"
        )


def test_vendor_contract_anchors_present() -> None:
    # The three-file contract the integration depends on.
    prepare = (VENDOR_DIR / "prepare.py").read_text(encoding="utf-8")
    train = (VENDOR_DIR / "train.py").read_text(encoding="utf-8")
    program = (VENDOR_DIR / "program.md").read_text(encoding="utf-8")
    assert "def evaluate_bpb(" in prepare
    assert "TIME_BUDGET = 300" in prepare
    assert "H100_BF16_PEAK_FLOPS" in train
    assert 'grep "^val_bpb:" run.log' in program
    # The vendored pyproject must carry the cu128 index uv needs in workspaces.
    assert "pytorch-cu128" in (VENDOR_DIR / "pyproject.toml").read_text(encoding="utf-8")


def test_importing_muse_autoresearch_packages_stays_torch_free() -> None:
    # Check the invariant in a PRISTINE interpreter. The package is lazy
    # (PEP 562) and torch-free, but an in-process check is flaky under xdist:
    # a sibling test that imports torch or a vendor module leaves it in this
    # worker's ``sys.modules``. A fresh subprocess isolates the import so the
    # assertion is about THIS package, not the worker's history.
    import subprocess

    script = (
        "import importlib, sys\n"
        "importlib.import_module("
        "'hermes_cli.jarvis_prime.research_fabric.autoresearch')\n"
        "assert 'torch' not in sys.modules, 'import pulled in torch'\n"
        "bad = [m for m in sys.modules if m.startswith("
        "'hermes_cli.jarvis_prime.research_fabric.autoresearch.vendor')]\n"
        "assert not bad, f'import pulled in vendor modules: {bad}'\n"
        "print('TORCH_FREE_OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "TORCH_FREE_OK" in proc.stdout
