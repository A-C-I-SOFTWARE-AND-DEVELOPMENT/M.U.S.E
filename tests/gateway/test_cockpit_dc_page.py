"""muse Cockpit (`cockpit.dc.html`) — serving, self-containment, packaging.

The cockpit is the imported Claude Design ``muse Cockpit.dc.html`` — a reactive
single page (the "Singularity / Cinematic synthesis" system) rendered by the
vendored ``dc-runtime`` over React. It is un-bundled here (no base64 bundler
wrapper): the design's own ``<x-dc>`` template + ``data-dc-script`` logic + the
inlined dc-runtime, with React vendored locally so it boots offline like the
Observatory.

Covers:

* the page and its vendored React halves are served by the cockpit server with
  the right content types;
* the page is fully self-contained — no script/link/import/fetch in the page
  references a remote (CDN) URL, so the cockpit works offline and never leaks
  requests off-box;
* React is loaded *before* the dc-runtime (the runtime skips its own loader when
  ``window.React`` already exists), and the references resolve to files that are
  actually served;
* the wheel ships the static tree (``static/**/*`` package-data glob).

Fixtures mirror ``tests/gateway/test_observatory_static.py`` (hermetic loopback
server).
"""

from __future__ import annotations

import re
import tomllib
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import gateway.cockpit.server as server_mod
from gateway.cockpit import observatory_metrics as om

TOKEN = "test-cockpit-token-123"

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "gateway" / "cockpit" / "static"

PAGE = STATIC / "cockpit.dc.html"
NEW_SOURCES = [
    PAGE,
    STATIC / "vendor" / "react.production.min.js",
    STATIC / "vendor" / "react-dom.production.min.js",
    STATIC / "vendor" / "dc-runtime.js",
    # The 3D Atlas, vendored under /cockpit/atlas/ (synced from docs/3d-model/,
    # sharing the cockpit's three.js) — must also stay offline.
    STATIC / "atlas" / "index.html",
    STATIC / "atlas" / "app.js",
    STATIC / "atlas" / "architecture_data.js",
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
    host, port = server.server_address
    req = urllib.request.Request(f"http://{host}:{port}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", ""), exc.read()


# ── serving ──────────────────────────────────────────────────────────────────


def test_cockpit_dc_html_served(server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/cockpit.dc.html")
    assert status == 200
    assert ctype.startswith("text/html")
    text = body.decode("utf-8")
    # The design's reactive document: an <x-dc> template + its data-dc-script.
    assert "<x-dc>" in text
    assert "data-dc-script" in text
    # React is vendored locally, not pulled from a CDN.
    assert 'src="vendor/react.production.min.js"' in text


@pytest.mark.parametrize(
    "path",
    [
        "/cockpit/vendor/react.production.min.js",
        "/cockpit/vendor/react-dom.production.min.js",
    ],
)
def test_vendored_react_served_with_js_content_type(server, path: str) -> None:
    status, ctype, body = _get_raw(server, path)
    assert status == 200
    assert ctype.startswith("application/javascript")
    assert len(body) > 0


def test_react_loads_before_dc_runtime(server) -> None:
    """The dc-runtime early-returns from its own React loader when
    ``window.React`` is already set, so the vendored React <script> tags must
    appear *before* the runtime script — otherwise the runtime would fall back
    to its (now-neutralised) loader.

    The runtime is loaded as an EXTERNAL ``vendor/dc-runtime.js`` (not inlined):
    inlining puts the runtime's own ``/<x-dc…>/`` regex literal into the page
    HTML, which its live-edit re-fetch (``parseDcText`` over ``location.href``)
    then matches instead of the real template — corrupting the render."""
    _, _, body = _get_raw(server, "/cockpit/cockpit.dc.html")
    text = body.decode("utf-8")
    react_at = text.find('src="vendor/react.production.min.js"')
    runtime_at = text.find('src="vendor/dc-runtime.js"')
    assert react_at != -1 and runtime_at != -1
    assert react_at < runtime_at
    # The runtime must NOT be inlined (would self-match the x-dc regex literal).
    assert "// GENERATED from dc-runtime" not in text


# ── self-containment: no remote executable/script/link references ───────────

# Executable/reference contexts that must never point at a remote URL.
# NOTE: the <link> rule exempts rel="canonical" (and other non-fetched discovery
# metadata) — a canonical href is an SEO hint the browser never fetches or
# executes, so it is not a self-containment violation. Loaded sub-resources
# (rel="stylesheet"/"preload"/"modulepreload"/"icon"/"manifest") are still caught
# because their tags don't carry rel="canonical".
_REMOTE_PATTERNS = [
    re.compile(r"<script[^>]+src\s*=\s*[\"']https?://", re.IGNORECASE),
    re.compile(r"<link(?![^>]*rel\s*=\s*[\"']canonical[\"'])[^>]+href\s*=\s*[\"']https?://", re.IGNORECASE),
    re.compile(r"\bfrom\s*[\"']https?://"),
    re.compile(r"\bimport\s*\(\s*[\"']https?://"),
    re.compile(r"\bimport\s+[\"']https?://"),
    re.compile(r"\bimportScripts\s*\(\s*[\"']https?://"),
    re.compile(r"\bnew\s+Worker\s*\(\s*[\"']https?://"),
    re.compile(r"\bfetch\s*\(\s*[\"']https?://"),
]


@pytest.mark.parametrize("source", NEW_SOURCES, ids=lambda p: p.name)
def test_no_remote_references_in_new_static_sources(source: Path) -> None:
    assert source.is_file(), f"missing static source: {source}"
    text = source.read_text(encoding="utf-8", errors="replace")
    for pattern in _REMOTE_PATTERNS:
        match = pattern.search(text)
        assert match is None, (
            f"{source.name} references a remote URL in an executable context: "
            f"{match.group(0)!r}"
        )


def test_page_vendor_references_resolve_locally(server) -> None:
    """Every ``vendor/<file>`` the page loads must be a file the server serves."""
    _, _, body = _get_raw(server, "/cockpit/cockpit.dc.html")
    text = body.decode("utf-8")
    refs = set(re.findall(r'src="(vendor/[^"]+)"', text))
    assert refs  # the page does vendor something (React)
    for rel in refs:
        status, _, payload = _get_raw(server, f"/cockpit/{rel}")
        assert status == 200 and payload, f"vendored asset 404s: {rel}"


# ── default promotion: /cockpit/ serves the Singularity design ───────────────


def test_cockpit_is_the_default_at_root(server) -> None:
    # /cockpit/ (and the bare "/" root) now serve the Singularity cockpit, while
    # the prior modular shell stays reachable at its explicit /cockpit/index.html.
    for root in ("/cockpit/", "/"):
        status, ctype, body = _get_raw(server, root)
        assert status == 200 and ctype.startswith("text/html")
        text = body.decode("utf-8")
        assert "<x-dc>" in text and 'src="vendor/dc-runtime.js"' in text, root


def test_root_relative_assets_resolve_when_singularity_is_at_slash(server) -> None:
    """muse omni opens http://host:8765/ — page refs must work without /cockpit/."""
    for path in (
        "/vendor/dc-runtime.js",
        "/vendor/react.production.min.js",
        "/vendor/react-dom.production.min.js",
        "/atlas/index.html",
        "/manifest.webmanifest",
        "/studio.html",
        "/observatory.html",
        "/legacy.html",
    ):
        status, _, body = _get_raw(server, path)
        assert status == 200 and body, f"root asset 404s: {path}"
    # Unknown root path must still 404 as JSON (not silently become the SPA).
    status, ctype, body = _get_raw(server, "/no-such-root-asset.js")
    assert status == 404
    assert b"unknown route" in body


def test_unknown_cockpit_route_falls_back_to_the_cockpit(server) -> None:
    # A client-side route (no file suffix) falls back to the cockpit document,
    # not a 404 — the design is its own single hash-routed page.
    status, ctype, body = _get_raw(server, "/cockpit/jobs")
    assert status == 200 and ctype.startswith("text/html")
    assert "<x-dc>" in body.decode("utf-8")


# ── 3D Atlas: vendored under /cockpit/atlas/, wired, three.js shared ─────────


def test_atlas_served_and_wired(server) -> None:
    # The cockpit points window.__resources.atlas at the served atlas, and the
    # atlas entry document is actually served.
    _, _, page = _get_raw(server, "/cockpit/cockpit.dc.html")
    assert 'atlas: "atlas/index.html"' in page.decode("utf-8")
    status, ctype, body = _get_raw(server, "/cockpit/atlas/index.html")
    assert status == 200 and ctype.startswith("text/html")
    assert b"3D" in body and b"Atlas" in body


def test_atlas_shares_the_cockpit_vendored_three(server) -> None:
    # The atlas reuses the cockpit's three.js (no 712K duplication): its app.js
    # imports the shared sibling vendor build, which the server serves.
    _, _, appjs = _get_raw(server, "/cockpit/atlas/app.js")
    assert b'from "../vendor/three.module.min.js"' in appjs
    assert not (STATIC / "atlas" / "vendor").exists()
    status, _, three = _get_raw(server, "/cockpit/vendor/three.module.min.js")
    assert status == 200 and three


# ── packaging: the wheel ships the static tree ───────────────────────────────


def test_pyproject_packages_cockpit_static_tree() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "gateway.cockpit" in package_data
    assert "static/**/*" in package_data["gateway.cockpit"]
