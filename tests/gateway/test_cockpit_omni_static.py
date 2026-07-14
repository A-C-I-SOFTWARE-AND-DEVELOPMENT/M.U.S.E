"""Regression tests for the Atlas Omni root swap on the cockpit gateway.

``muse omni`` serves the new Atlas Omni UI (``apps/desktop/ui/dist``, resolved
via ``MUSE_OMNI_DIST_DIR``) at the site root when a build exists, while the
classic Singularity shell stays reachable at ``/cockpit/`` and its
root-relative asset dirs keep working. Without a build, the root serves
Singularity exactly as before. These tests pin that contract.

Hermetic: starts the real stdlib server on a random loopback port with a tmp
HERMES_HOME and a known token, then drives it with ``urllib``. Same pattern as
tests/gateway/test_cockpit_nexus_static.py.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-omni"
ATLAS_MARKER = "ATLAS-OMNI-TEST-BUILD"
SINGULARITY_MARKER = "muse — your AI operating partner"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def omni_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake Vite build the server should adopt as the site root."""
    dist = tmp_path / "omni-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        f"<!doctype html><html><body>{ATLAS_MARKER}</body></html>",
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log('atlas')", encoding="utf-8")
    (dist / "registerSW.js").write_text("/* sw */", encoding="utf-8")
    (dist / "space").mkdir()
    (dist / "space" / "starmap.jpg").write_bytes(b"\xff\xd8\xff\xdbjpegish")
    (dist / "secret.py").write_text("nope", encoding="utf-8")  # disallowed type
    monkeypatch.setenv("MUSE_OMNI_DIST_DIR", str(dist))
    return dist


@pytest.fixture()
def no_omni_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Authoritative override pointing at an empty dir — the swap is off even
    if a real apps/desktop/ui build exists on this machine."""
    empty = tmp_path / "no-dist"
    empty.mkdir()
    monkeypatch.setenv("MUSE_OMNI_DIST_DIR", str(empty))


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get_raw(server, path: str):
    req = urllib.request.Request(_url(server, path), method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def test_root_serves_singularity_without_build(no_omni_dist, server) -> None:
    status, ctype, body = _get_raw(server, "/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert SINGULARITY_MARKER in body.decode("utf-8", "replace")


def test_root_serves_atlas_build_when_present(omni_dist, server) -> None:
    status, ctype, body = _get_raw(server, "/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert ATLAS_MARKER in body.decode("utf-8", "replace")


def test_atlas_assets_served_from_build(omni_dist, server) -> None:
    status, ctype, body = _get_raw(server, "/assets/app.js")
    assert status == 200
    assert ctype.startswith("application/javascript")
    assert b"atlas" in body

    status, _, body = _get_raw(server, "/registerSW.js")
    assert status == 200
    assert b"sw" in body

    # Real-photography plates ship as JPEG — the suffix allowlist must serve
    # them (regression: .jpg was missing and the NASA layer 404'd).
    status, ctype, body = _get_raw(server, "/space/starmap.jpg")
    assert status == 200
    assert ctype.startswith("image/jpeg")
    assert body.startswith(b"\xff\xd8")


def test_singularity_stays_at_cockpit_prefix(omni_dist, server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/")
    assert status == 200
    assert ctype.startswith("text/html")
    text = body.decode("utf-8", "replace")
    assert SINGULARITY_MARKER in text
    assert ATLAS_MARKER not in text


def test_legacy_alias_stays_singularity(omni_dist, server) -> None:
    status, _, body = _get_raw(server, "/legacy.html")
    assert status == 200
    assert SINGULARITY_MARKER in body.decode("utf-8", "replace")


def test_disallowed_suffix_in_build_is_not_served(omni_dist, server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get_raw(server, "/secret.py")
    assert exc.value.code == 404


def test_unknown_bare_route_is_not_spa_masked(omni_dist, server) -> None:
    # The Atlas UI routes client-side via the URL hash; an unknown bare path
    # must stay an honest 404, not silently alias the SPA document.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get_raw(server, "/definitely-not-a-route")
    assert exc.value.code == 404


def test_missing_asset_404s_instead_of_spa_fallback(omni_dist, server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get_raw(server, "/assets/missing.js")
    assert exc.value.code == 404
