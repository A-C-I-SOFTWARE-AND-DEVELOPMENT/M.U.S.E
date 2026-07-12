"""Bounded, authenticated route registration for cockpit plugins."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from gateway.cockpit.handlers import JsonResponse, Request


Handler = Callable[[Request], JsonResponse]

_PLUGIN_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class RegisteredRoute:
    """A plugin-owned cockpit route whose static path text is literal."""

    plugin_id: str
    method: str
    path: str
    pattern: re.Pattern[str]
    handler: Handler
    requires_auth: bool


_routes: list[RegisteredRoute] = []
_lock = threading.RLock()


def _normalise_plugin_id(plugin_id: str) -> str:
    if not isinstance(plugin_id, str):
        raise ValueError("plugin id must be a string")
    clean = plugin_id.strip().lower()
    if not _PLUGIN_ID.fullmatch(clean):
        raise ValueError(f"invalid plugin id {plugin_id!r}")
    return clean


def _compile(path: str) -> re.Pattern[str]:
    """Compile a path template without interpreting static text as regex."""
    if "{" not in path and "}" not in path:
        return re.compile(f"^{re.escape(path)}$")

    pattern_parts: list[str] = []
    cursor = 0
    parameter_names: set[str] = set()
    for found in _PLACEHOLDER.finditer(path):
        static = path[cursor:found.start()]
        if "{" in static or "}" in static:
            raise ValueError(f"invalid path template {path!r}")
        name = found.group(1)
        if name in parameter_names:
            raise ValueError(f"invalid path template {path!r}: duplicate placeholder {name!r}")
        parameter_names.add(name)
        pattern_parts.extend((re.escape(static), f"(?P<{name}>[^/]+)"))
        cursor = found.end()

    static = path[cursor:]
    if "{" in static or "}" in static:
        raise ValueError(f"invalid path template {path!r}")
    pattern_parts.append(re.escape(static))
    return re.compile(f"^{''.join(pattern_parts)}$")


def register_route(
    plugin_id: str,
    method: str,
    path: str,
    handler: Handler,
    *,
    requires_auth: bool = True,
) -> None:
    """Register one authenticated route inside its owning plugin namespace."""
    clean_plugin_id = _normalise_plugin_id(plugin_id)
    if not isinstance(method, str):
        raise ValueError("method must be a string")
    if not isinstance(path, str):
        raise ValueError("path template must be a string")
    if not callable(handler):
        raise ValueError("handler must be callable")
    if not requires_auth:
        raise ValueError("cockpit plugin routes must require authentication")

    clean_method = method.strip().upper()
    clean_path = path.rstrip("/") or "/"
    prefix = f"/v1/plugins/{clean_plugin_id}/"
    if not clean_path.startswith(prefix):
        raise ValueError(f"route must stay inside plugin prefix {prefix}")
    if clean_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"unsupported method {clean_method!r}")
    if "?" in clean_path or "#" in clean_path:
        raise ValueError(f"invalid path template {path!r}")
    if any(segment in {".", ".."} for segment in clean_path.split("/")):
        raise ValueError(f"invalid path template {path!r}")

    pattern = _compile(clean_path)
    with _lock:
        if any(route.method == clean_method and route.path == clean_path for route in _routes):
            raise ValueError(f"route already registered: {clean_method} {clean_path}")
        _routes.append(
            RegisteredRoute(
                clean_plugin_id,
                clean_method,
                clean_path,
                pattern,
                handler,
                True,
            )
        )


def match(
    method: str, path: str
) -> Optional[tuple[Handler, bool, dict[str, str]]]:
    """Return the first registered plugin route matching ``method`` and ``path``."""
    clean_path = path.rstrip("/") or "/"
    clean_method = method.upper()
    with _lock:
        routes = tuple(_routes)
    for route in routes:
        if route.method != clean_method:
            continue
        found = route.pattern.match(clean_path)
        if found:
            return route.handler, route.requires_auth, found.groupdict()
    return None


def clear_routes_for_tests() -> None:
    """Clear registered routes for hermetic test setup."""
    with _lock:
        _routes.clear()
