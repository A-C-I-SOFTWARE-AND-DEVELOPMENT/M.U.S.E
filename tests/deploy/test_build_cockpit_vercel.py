"""Vercel cockpit assemble layout — Singularity at root, musehq under /chat/."""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "deploy" / "build_cockpit_vercel.sh"
COCKPIT_DC = REPO_ROOT / "gateway" / "cockpit" / "static" / "cockpit.dc.html"


def test_assemble_script_documents_singularity_at_root() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "cockpit.dc.html" in text
    assert 'cp "$SRC/cockpit.dc.html" "$OUT/index.html"' in text
    assert "$OUT/chat/" in text or '"$OUT/chat/"' in text
    assert "MUSEHQ_BASE=/chat/" in text
    # Must not dump musehq dist onto site root anymore.
    assert 'cp -R "$APP/dist/." "$OUT/"' not in text
    assert 'cp -R "$APP/dist/." "$OUT/chat/"' in text


def test_vercel_json_does_not_spa_rewrite_entire_site() -> None:
    """Catch-all rewrites would swallow static cockpit assets at /."""
    vercel = (REPO_ROOT / "vercel.json").read_text(encoding="utf-8")
    # Scoped to /chat/ only — not /((?!api/).*)
    assert "/chat/" in vercel
    assert 'destination": "/chat/index.html"' in vercel or '"/chat/index.html"' in vercel
    assert "/((?!api/).*)" not in vercel


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm required for assemble smoke")
def test_assemble_layout_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the assemble script against a stub musehq build (no real Solid compile)."""
    out = tmp_path / "cockpit-dist"
    # Stub npm so we don't wait on a full Solid build in unit tests.
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    npm = stub_bin / "npm"
    musehq_dist = REPO_ROOT / "web" / "musehq" / "dist"
    musehq_dist.mkdir(parents=True, exist_ok=True)
    (musehq_dist / "index.html").write_text(
        "<!doctype html><title>musehq stub</title>\n", encoding="utf-8"
    )
    (musehq_dist / "assets").mkdir(exist_ok=True)
    (musehq_dist / "assets" / "app.js").write_text("// stub\n", encoding="utf-8")

    npm.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            # no-op stub: dist already prepared by the test
            exit 0
            """
        ),
        encoding="utf-8",
    )
    npm.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_bin}:{os.environ.get('PATH', '')}")

    result = subprocess.run(
        ["bash", str(SCRIPT), str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    index = (out / "index.html").read_text(encoding="utf-8")
    expected_marker = COCKPIT_DC.read_text(encoding="utf-8")[:200]
    assert index.startswith(expected_marker[:80]) or "<x-dc>" in index
    assert "Local Admin" in index or "local-admin" in index
    assert (out / "legacy.html").is_file()
    assert (out / "chat" / "index.html").is_file()
    assert "musehq stub" in (out / "chat" / "index.html").read_text(encoding="utf-8")
    assert (out / "vendor" / "dc-runtime.js").is_file()
    assert (out / "atlas").is_dir()
