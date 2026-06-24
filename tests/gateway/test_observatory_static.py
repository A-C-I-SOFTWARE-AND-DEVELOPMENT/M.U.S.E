"""Neural Observatory static page — serving, self-containment, packaging.

Covers the flagship ``/cockpit/observatory.html`` 3D page and its assets:

* every new static file (page, module, stylesheet, vendored three.js build)
  is served by the cockpit server with the right content type;
* the page is fully self-contained — no script/link tag, ES-module import,
  or fetch in any of the new sources references a remote (CDN) URL, so the
  Observatory works offline and never leaks requests off-box (the vendored
  three.js provenance *comment* may name its source domain — comments are
  not executable references);
* ``index.html`` still serves and carries the one nav link to the page;
* the wheel actually ships the static tree (``gateway.cockpit`` package-data
  glob in ``pyproject.toml`` — previously index.html was omitted entirely).

Fixtures mirror ``tests/gateway/test_cockpit_observatory.py`` (hermetic
loopback server).
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

NEW_SOURCES = [
    STATIC / "observatory.html",
    STATIC / "observatory.js",
    STATIC / "observatory.css",
    STATIC / "vendor" / "three.module.min.js",
    STATIC / "vendor" / "three.core.min.js",
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


def test_observatory_html_served(server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/observatory.html")
    assert status == 200
    assert ctype.startswith("text/html")
    text = body.decode("utf-8")
    assert "Neural Observatory" in text
    # The page boots its renderer as a local ES module, nothing else.
    assert 'type="module"' in text
    assert 'src="observatory.js"' in text


@pytest.mark.parametrize(
    "path",
    [
        "/cockpit/observatory.js",
        "/cockpit/vendor/three.module.min.js",
        "/cockpit/vendor/three.core.min.js",
    ],
)
def test_javascript_assets_served_with_js_content_type(server, path: str) -> None:
    status, ctype, body = _get_raw(server, path)
    assert status == 200
    assert ctype.startswith("application/javascript")
    assert len(body) > 0


def test_observatory_css_served(server) -> None:
    status, ctype, body = _get_raw(server, "/cockpit/observatory.css")
    assert status == 200
    assert ctype.startswith("text/css")
    assert b"--void" in body or b"#stage" in body


def test_observatory_js_imports_vendored_three(server) -> None:
    _, _, body = _get_raw(server, "/cockpit/observatory.js")
    assert b'from "./vendor/three.module.min.js"' in body


def test_cockpit_default_is_singularity_design(server) -> None:
    # The default cockpit document is now the imported "Singularity" Claude
    # Design (cockpit.dc.html): /cockpit/ serves it directly.
    status, ctype, body = _get_raw(server, "/cockpit/")
    assert status == 200
    assert ctype.startswith("text/html")
    text = body.decode("utf-8")
    assert "<x-dc>" in text and 'src="vendor/dc-runtime.js"' in text
    assert "muse" in text


def test_classic_shell_and_observatory_still_reachable(server) -> None:
    # The prior modular shell stays reachable at its explicit path, still
    # carrying the SPA nav entry the router resolves to the observatory view
    # (js/views/observatory.js embeds /cockpit/observatory.html in an iframe).
    _, _, classic = _get_raw(server, "/cockpit/index.html")
    assert 'data-nav="observatory"' in classic.decode("utf-8")
    # And the flagship 3D page itself is served regardless of the default.
    status, ctype, _ = _get_raw(server, "/cockpit/observatory.html")
    assert status == 200 and ctype.startswith("text/html")


# ── self-containment: no remote executable/script/link references ───────────

# Executable/reference contexts that must never point at a remote URL:
#   * HTML: <script src=...>, <link href=...>, ES-module import in inline JS
#   * JS:   static import ... from "http...", dynamic import("http..."),
#           importScripts("http..."), new Worker("http..."), fetch("http...")
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


def test_vendored_three_module_resolves_locally() -> None:
    # The split three.js build re-exports from a relative sibling; both halves
    # must be vendored or the module graph 404s at runtime.
    module = (STATIC / "vendor" / "three.module.min.js").read_text(
        encoding="utf-8", errors="replace"
    )
    relative_imports = set(re.findall(r"from\s*\"(\./[^\"]+)\"", module))
    assert relative_imports <= {"./three.core.min.js"}
    assert (STATIC / "vendor" / "three.core.min.js").is_file()


# ── packaging: the wheel ships the static tree ───────────────────────────────


def test_pyproject_packages_cockpit_static_tree() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = data["tool"]["setuptools"]["package-data"]
    assert "gateway.cockpit" in package_data
    assert "static/**/*" in package_data["gateway.cockpit"]
