"""Standalone "Singularity" cockpit studio page — serving + release integration.

``/cockpit/studio.html`` is a self-contained design-canvas (dc-runtime) build of
the full muse Cockpit, served alongside the live modular cockpit. It carries its
own runtime (``studio-support.js``) and embeds the 3D Systems Atlas. Its Releases
view is the unified download hub: every release frontend — Desktop (Tauri),
Android (APK), and full source — is wired to its real rolling channel, with the
"download all" CTA pointing at the live releases index.

These assertions check the *serving contract* and the *release wiring*, not the
design's exact markup (which is owner-authored and free to evolve).

Fixtures mirror ``tests/gateway/test_observatory_static.py`` (hermetic loopback
server).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import observatory_metrics as om

TOKEN = "test-cockpit-token-123"

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "gateway" / "cockpit" / "static"

# The real rolling-release targets the studio's Releases hub must link to —
# one per release frontend, plus the live releases index for "download all".
RELEASE_TARGETS = [
    "/releases/download/android-latest/jarvis-prime-android.apk",
    "/releases/tag/muse-desktop-latest",
    "/archive/refs/heads/main.zip",
    "A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases",
]


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


@pytest.fixture()
def server(home: Path):
    srv = server_mod.serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _get_raw(server, path: str) -> tuple[int, str, bytes]:
    import urllib.request

    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


# ── files exist on disk (so the wheel's ``static/**/*`` glob ships them) ──────


def test_studio_files_present_on_disk() -> None:
    for rel in ("studio.html", "studio-support.js", "atlas/muse-atlas.html"):
        assert (STATIC / rel).is_file(), f"missing static asset: {rel}"


# ── serving ──────────────────────────────────────────────────────────────────


def test_studio_html_served(server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/studio.html")
    assert status == 200
    assert ctype.startswith("text/html")
    text = body.decode("utf-8")
    assert "muse" in text
    # Boots its *page-local* runtime, not the shared ``support.js``.
    assert 'src="./studio-support.js"' in text
    assert "support.js" in text and 'src="./support.js"' not in text
    # The dc-runtime template the runtime mounts.
    assert "<x-dc>" in text


def test_studio_runtime_served_as_javascript(server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/studio-support.js")
    assert status == 200
    assert ctype.startswith("application/javascript")
    assert len(body) > 0


def test_studio_atlas_embed_served(server) -> None:
    # The Studio view iframes ``atlas/muse-atlas.html``; it must resolve.
    status, ctype, body = _get_raw(server, "/cockpit/atlas/muse-atlas.html")
    assert status == 200
    assert ctype.startswith("text/html")
    assert len(body) > 0


# ── release integration: all frontends wired to their real channels ───────────


def test_releases_view_present(server) -> None:
    _, _, body = _get_raw(server, "/cockpit/studio.html")
    text = body.decode("utf-8")
    assert "Releases" in text
    assert "Download muse" in text
    # The three release frontends are all represented.
    for label in ("Desktop cockpit", "Android app", "Full source"):
        assert label in text, f"release frontend missing from hub: {label}"


@pytest.mark.parametrize("target", RELEASE_TARGETS)
def test_releases_link_to_real_channels(server, target: str) -> None:
    _, _, body = _get_raw(server, "/cockpit/studio.html")
    text = body.decode("utf-8")
    assert target in text, f"release hub does not wire real channel: {target}"
