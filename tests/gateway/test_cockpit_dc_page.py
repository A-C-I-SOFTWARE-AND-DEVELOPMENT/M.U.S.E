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
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


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
    appear *before* the inlined runtime — otherwise the runtime would fall back
    to its (now-neutralised) loader."""
    _, _, body = _get_raw(server, "/cockpit/cockpit.dc.html")
    text = body.decode("utf-8")
    react_at = text.find('src="vendor/react.production.min.js"')
    runtime_at = text.find("// GENERATED from dc-runtime")
    assert react_at != -1 and runtime_at != -1
    assert react_at < runtime_at


# ── self-containment: no remote executable/script/link references ───────────

# Executable/reference contexts that must never point at a remote URL.
_REMOTE_PATTERNS = [
    re.compile(r"<script[^>]+src\s*=\s*[\"']https?://", re.IGNORECASE),
    re.compile(r"<link[^>]+href\s*=\s*[\"']https?://", re.IGNORECASE),
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


# ── packaging: the wheel ships the static tree ───────────────────────────────


def test_pyproject_packages_cockpit_static_tree() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "gateway.cockpit" in package_data
    assert "static/**/*" in package_data["gateway.cockpit"]
