"""Vendor integrity for the clean-room LLM-JEPA harness.

Two invariants, mirroring the autoresearch vendor-integrity test:
1. Every file under ``vendor/`` matches the committed ``checksums.json`` and no
   stray file is added — the do-not-edit rule in ``VENDOR.md`` (changes go
   through review + a manifest bump; the loop mutates only workspace copies).
2. Importing the muse-side llm_jepa package never imports torch or a vendored
   module — the engine is owner-hardware only and must stay out of the base
   import path.
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
    / "llm_jepa"
)
VENDOR_DIR = PKG_DIR / "vendor"
EXPECTED_FILES = (
    "train.py",
    "program.md",
    "README.md",
    "pyproject.toml",
    ".python-version",
)


def test_checksums_manifest_covers_exactly_the_vendored_files():
    manifest = json.loads((PKG_DIR / "checksums.json").read_text(encoding="utf-8"))
    assert sorted(manifest) == sorted(EXPECTED_FILES)
    on_disk = sorted(p.name for p in VENDOR_DIR.iterdir() if p.is_file())
    assert on_disk == sorted(EXPECTED_FILES), "unexpected file added to vendor/"


def test_vendored_files_match_manifest():
    manifest = json.loads((PKG_DIR / "checksums.json").read_text(encoding="utf-8"))
    for name, expected_sha in manifest.items():
        actual = hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"vendor/{name} changed in-repo — bump checksums.json via review "
            "(see VENDOR.md); the loop mutates only workspace copies"
        )


def test_vendor_contract_anchors_present():
    train = (VENDOR_DIR / "train.py").read_text(encoding="utf-8")
    program = (VENDOR_DIR / "program.md").read_text(encoding="utf-8")
    assert "jepa_accuracy:" in train
    assert "[PRED]" in train  # the tied-weights predictor token
    assert "cosine" in train.lower()
    assert "baseline_accuracy:" in program
    assert "pytorch-cu128" in (VENDOR_DIR / "pyproject.toml").read_text(encoding="utf-8")


def test_importing_llm_jepa_stays_torch_free():
    import subprocess

    script = (
        "import importlib, sys\n"
        "importlib.import_module("
        "'hermes_cli.jarvis_prime.research_fabric.llm_jepa')\n"
        "m = importlib.import_module("
        "'hermes_cli.jarvis_prime.research_fabric.llm_jepa')\n"
        "m.build_views  # trigger lazy attr\n"
        "assert 'torch' not in sys.modules, 'import pulled in torch'\n"
        "bad = [x for x in sys.modules if x.startswith("
        "'hermes_cli.jarvis_prime.research_fabric.llm_jepa.vendor')]\n"
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
