"""Registration surfaces must build without error.

Three registries decide what the running system can actually do, and none
of them had a test that simply asked "does everything you advertise
register?":

* **gateway platform adapters** — 20-odd messaging platforms registered as
  deferred loaders at plugin discovery and imported lazily on first lookup.
  A loader that raises is *swallowed and logged* by
  ``PlatformRegistry._resolve``, so a broken adapter silently disappears
  from the gateway instead of failing loudly.
* **bundled plugins** — ``PluginManager`` records a per-plugin ``error``
  string and keeps going.  A plugin calling a ``PluginContext`` method that
  does not exist loads to nothing, and its own unit tests still pass
  because they hand ``register()`` a ``Mock`` context.
* **HTTP routes** — the FastAPI app and routers behind ``muse dashboard``.

Plugin discovery mutates process-global registries, so it runs in a child
interpreter (:mod:`tests.smoke._probe`) and this module asserts over the
JSON report.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest

from tests.smoke._discovery import (
    REPO_ROOT,
    ZERO_TEST_PACKAGES,
    discover_modules,
    first_party_top_level,
)

_PROBE = Path(__file__).with_name("_probe.py")

# A plugin that is switched off in config did not fail; it was not asked to
# run.  Every other error string is a defect until proven otherwise.
_NOT_A_DEFECT = re.compile(
    r"not enabled in config|disabled by config|requires opt-in",
    re.IGNORECASE,
)
_MISSING_OPTIONAL_DEP = re.compile(
    r"No module named ['\"]([^'\"]+)['\"]",
)


@lru_cache(maxsize=1)
def _platform_report() -> dict:
    """Run the out-of-process plugin/platform probe once per session."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "platforms.json"
        completed = subprocess.run(
            [sys.executable, str(_PROBE), "platforms", str(out)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if not out.is_file():
            raise RuntimeError(
                f"platform probe produced no report (exit {completed.returncode})\n"
                f"stdout:\n{completed.stdout[-2000:]}\n"
                f"stderr:\n{completed.stderr[-2000:]}"
            )
        return json.loads(out.read_text(encoding="utf-8"))


def _probe_result() -> dict:
    report = _platform_report()
    if not report.get("ok"):
        raise RuntimeError(
            "gateway platform / plugin discovery probe crashed:\n"
            f"{report.get('error')}\n{report.get('traceback', '')[-2000:]}"
        )
    return report["result"]


# Runs at collection so the platform list can be parametrised.  A failure
# here must not abort collection — it is reported by ``test_platform_probe_ran``.
try:
    _RESULT = _probe_result()
except Exception as exc:  # noqa: BLE001 - surfaced by test_platform_probe_ran
    _RESULT = {}
    _PROBE_ERROR: Exception | None = exc
else:
    _PROBE_ERROR = None

_DEFERRED = tuple(_RESULT.get("deferred_at_discovery", ()))
_PLUGIN_ERRORS = tuple(sorted(_RESULT.get("plugin_load_errors", {}).items()))


# ── gateway platform adapters ──────────────────────────────────────────────


def test_platform_probe_ran() -> None:
    assert _PROBE_ERROR is None, f"platform probe failed: {_PROBE_ERROR}"


def test_gateway_registers_a_realistic_platform_count() -> None:
    """Guard against a vacuously-green suite.

    23 adapters resolved on 2026-08-17.  A floor of 10 tolerates removing
    platforms but not a discovery collapse that would make the
    per-platform assertions below cover nothing.
    """
    resolved = _RESULT.get("resolved", [])
    assert len(resolved) >= 10, (
        f"only {len(resolved)} gateway platform adapters resolved: {resolved}. "
        f"Plugin discovery is probably broken."
    )


@pytest.mark.parametrize("platform", _DEFERRED, ids=list(_DEFERRED) or None)
def test_deferred_platform_adapter_resolves(platform: str) -> None:
    """A platform advertised at discovery must survive being imported.

    ``PlatformRegistry._resolve`` catches and logs loader exceptions, so a
    platform that fails here vanishes from ``muse gateway`` with nothing but
    a warning in the log.
    """
    unresolved = set(_RESULT.get("unresolved", ()))
    assert platform not in unresolved, (
        f"gateway platform {platform!r} was registered as a deferred loader "
        f"but its loader raised while importing; PlatformRegistry swallowed "
        f"the exception, so the platform is silently missing at runtime."
    )


@pytest.mark.parametrize("platform", _DEFERRED, ids=list(_DEFERRED) or None)
def test_platform_entry_exposes_its_adapter_contract(platform: str) -> None:
    """Every resolved entry must carry the fields the gateway dispatches on."""
    shapes = _RESULT.get("entry_shapes", {})
    if platform not in shapes:
        pytest.skip(f"platform {platform!r} did not resolve; see the resolve test")
    fields = set(shapes[platform]["fields"])
    required = {"name", "label", "adapter_factory", "source"}
    missing = sorted(required - fields)
    assert not missing, (
        f"gateway platform entry {platform!r} is missing {missing}; the "
        f"gateway looks these up by attribute when starting the platform."
    )


# ── bundled plugins ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "plugin_key,error",
    _PLUGIN_ERRORS,
    ids=[key for key, _ in _PLUGIN_ERRORS] or None,
)
def test_bundled_plugin_load_error_is_not_a_defect(
    plugin_key: str, error: str
) -> None:
    """A plugin that failed to load must have failed for a benign reason.

    Opt-in plugins that are switched off in config, and plugins whose
    optional third-party SDK is not installed, are configuration facts and
    are skipped with that reason.  Anything else — most importantly a
    ``PluginContext`` method that does not exist — is a real defect: the
    plugin registers nothing at runtime while its own unit tests keep
    passing against a mock context.
    """
    if _NOT_A_DEFECT.search(error):
        pytest.skip(f"plugin {plugin_key!r} is opt-in and not enabled: {error}")
    dep = _MISSING_OPTIONAL_DEP.search(error)
    if dep and dep.group(1).split(".")[0] not in first_party_top_level():
        pytest.skip(
            f"plugin {plugin_key!r} needs optional dependency "
            f"{dep.group(1)!r}, which is not installed"
        )
    pytest.fail(f"plugin {plugin_key!r} failed to load: {error}")


# ── HTTP route registration ────────────────────────────────────────────────


_ROUTER_DECL = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(FastAPI|APIRouter)\(",
    re.MULTILINE,
)


@lru_cache(maxsize=1)
def _http_surfaces() -> tuple[tuple[str, str], ...]:
    """Discover ``(module, attribute)`` pairs holding a FastAPI app/router.

    Found by scanning source rather than by importing everything, so adding
    a router module tomorrow is covered without editing this file.
    """
    found: list[tuple[str, str]] = []
    for package in ZERO_TEST_PACKAGES:
        for module_name in discover_modules(package):
            rel = Path(*module_name.split("."))
            for candidate in (
                REPO_ROOT / rel.with_suffix(".py"),
                REPO_ROOT / rel / "__init__.py",
            ):
                if not candidate.is_file():
                    continue
                text = candidate.read_text(encoding="utf-8", errors="replace")
                for match in _ROUTER_DECL.finditer(text):
                    found.append((module_name, match.group(1)))
                break
    return tuple(sorted(set(found)))


_HTTP_SURFACES = _http_surfaces()
_HTTP_IDS = [f"{m}:{a}" for m, a in _HTTP_SURFACES]


def test_http_surface_discovery_is_not_empty() -> None:
    """16 FastAPI/APIRouter declarations were found on 2026-08-17."""
    assert len(_HTTP_SURFACES) >= 8, (
        f"only {len(_HTTP_SURFACES)} FastAPI/APIRouter declarations were "
        f"discovered: {_HTTP_SURFACES}"
    )


@pytest.mark.parametrize("module_name,attr", _HTTP_SURFACES, ids=_HTTP_IDS or None)
def test_http_routes_register(module_name: str, attr: str) -> None:
    """Every declared route must register with a callable endpoint.

    Also asserts no ``(path, method)`` pair is registered twice on one app
    or router: FastAPI silently keeps the first match, so a duplicate means
    a handler that can never be reached.
    """
    pytest.importorskip("fastapi", reason="fastapi is not installed")
    import importlib

    module = importlib.import_module(module_name)
    surface = getattr(module, attr, None)
    assert surface is not None, (
        f"{module_name} declares {attr} at module scope but it is not an "
        f"attribute of the imported module."
    )
    routes = list(getattr(surface, "routes", []))
    assert routes, f"{module_name}:{attr} registered no routes at all"

    seen: dict[tuple[str, str], str] = {}
    for route in routes:
        path = getattr(route, "path", None)
        assert isinstance(path, str) and path.startswith("/"), (
            f"{module_name}:{attr} has a route with a non-path value: {path!r}"
        )
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None:
            assert callable(endpoint), (
                f"{module_name}:{attr} route {path} has a non-callable "
                f"endpoint: {endpoint!r}"
            )
        for method in sorted(getattr(route, "methods", None) or {"WEBSOCKET"}):
            key = (path, method)
            name = getattr(route, "name", "?")
            assert key not in seen, (
                f"{module_name}:{attr} registers {method} {path} twice "
                f"({seen[key]} and {name}); the second handler is unreachable."
            )
            seen[key] = name
