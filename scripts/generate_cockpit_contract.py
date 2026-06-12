#!/usr/bin/env python3
"""Freeze the cockpit wire contract — EPIC-COCKPIT-SEAM Phase 0.

Walks the cockpit server's route tables (``gateway.cockpit.server._ROUTES``
and ``_STREAM_ROUTES``) **plus** the special-cased routes hand-dispatched in
``Handler._dispatch`` (the streaming chat POST and the static UI shell), and
emits a deterministic, committed inventory of the wire surface:

* ``docs/contracts/cockpit-wire-contract.json`` — machine-readable contract
  (sorted keys, routes sorted by ``(path, method)``, trailing newline), and
* ``docs/contracts/cockpit-wire-contract.md`` — the human route-inventory
  table with the honest route/handler census.

Per route: HTTP method, ``{param}`` path template (reverse-translated from
the compiled regex), module-qualified handler name, ``requires_auth`` (the
4th member of each ``_ROUTES`` tuple), ``owner_gated`` (the handler source —
or a same-module helper it calls, e.g. ``_evaluate_execute_gate`` — references
``AUTHORIZATION_PHRASE``), dispatch ``kind``, and the first docstring line.

Stdlib-only. Read-only against the server modules: importing
``gateway.cockpit.server`` defines the tables; nothing is bound or served.
The committed artifacts are pinned by
``tests/gateway/test_cockpit_contract_freeze.py`` — any route drift fails
that test until this script is re-run and the diff is committed.
"""

from __future__ import annotations

import inspect
import json
import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "docs" / "contracts" / "cockpit-wire-contract.json"
MD_PATH = REPO_ROOT / "docs" / "contracts" / "cockpit-wire-contract.md"

CONTRACT_NAME = "cockpit-wire-contract"
CONTRACT_VERSION = 1

# The owner-gate symbol used by gateway/cockpit/handlers*.py (verified by
# grep): handlers import AUTHORIZATION_PHRASE from
# muse_cli.jarvis_prime.owner_auth and compare the request's
# "authorization" field against it. There is no `require_owner` helper —
# some handlers instead delegate to a same-module helper
# (`_evaluate_execute_gate`) whose source references the phrase, which the
# one-hop check below catches.
_OWNER_GATE_TOKEN = "AUTHORIZATION_PHRASE"

# `(?P<name>[^/]+)` capture (produced by server._compile) → `{name}`.
_CAPTURE_RE = re.compile(r"\(\?P<(\w+)>\[\^/\]\+\)")


def _template_from_pattern(pattern: re.Pattern[str]) -> str:
    """Reverse-translate a compiled route regex back to a `{param}` template."""
    raw = pattern.pattern
    raw = raw.removeprefix("^").removesuffix("$")
    return _CAPTURE_RE.sub(r"{\1}", raw) or "/"


def _qualified_name(fn: Callable[..., Any]) -> str:
    module = getattr(fn, "__module__", "")
    qualname = getattr(fn, "__qualname__", repr(fn))
    return f"{module}.{qualname}"


def _summary(fn: Callable[..., Any]) -> Optional[str]:
    doc = inspect.getdoc(fn)
    if not doc:
        return None
    first = doc.strip().splitlines()[0].strip()
    return first or None


def _source_of(fn: Callable[..., Any]) -> str:
    try:
        return inspect.getsource(fn)
    except (OSError, TypeError):
        return ""


def _owner_gated(fn: Callable[..., Any]) -> bool:
    """True iff the handler enforces the owner authorization phrase.

    Direct: the handler's own source references ``AUTHORIZATION_PHRASE``.
    One hop: the handler calls a function defined in its own module whose
    source references the phrase (e.g. ``_evaluate_execute_gate`` used by
    ``job_run`` and ``coding_execute``).
    """
    if _OWNER_GATE_TOKEN in _source_of(fn):
        return True
    module = inspect.getmodule(fn)
    code = getattr(fn, "__code__", None)
    if module is None or code is None:
        return False
    for name in code.co_names:
        helper = getattr(module, name, None)
        if (
            inspect.isfunction(helper)
            and helper is not fn
            and _OWNER_GATE_TOKEN in _source_of(helper)
        ):
            return True
    return False


def _route_entry(
    *,
    method: str,
    path: str,
    handler: Callable[..., Any],
    requires_auth: bool,
    kind: str,
) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "handler": _qualified_name(handler),
        "requires_auth": bool(requires_auth),
        "owner_gated": _owner_gated(handler),
        "kind": kind,
        "summary": _summary(handler),
    }


def build_contract() -> dict[str, Any]:
    """Build the wire contract from the live route tables (deterministic)."""
    from gateway.cockpit import server
    from gateway.jarvis_local_http import CHAT_PATH

    routes: list[dict[str, Any]] = []

    # 1) Buffered JSON routes — the _ROUTES table. Tuple shape verified
    #    against server.py: (method, compiled-pattern, handler, requires_auth).
    for entry in server._ROUTES:
        if len(entry) != 4:  # fail loudly if the tuple shape ever changes
            raise AssertionError(
                f"_ROUTES tuple shape changed (expected 4 members): {entry!r}"
            )
        method, pattern, handler, requires_auth = entry
        routes.append(
            _route_entry(
                method=method,
                path=_template_from_pattern(pattern),
                handler=handler,
                requires_auth=requires_auth,
                kind="json",
            )
        )

    # The streaming/static handlers live on the request-handler class built by
    # _make_handler. Building the class binds nothing and serves nothing.
    handler_cls = server._make_handler(None, None, threading.Event())

    # Guard: the special cases enumerated below were read out of
    # Handler._dispatch. If _dispatch stops referencing any of these seams,
    # this script is stale and must be updated rather than emit a wrong census.
    dispatch_src = _source_of(handler_cls._dispatch)
    for needle in ("CHAT_PATH", "_serve_static", "_match_stream"):
        if needle not in dispatch_src:
            raise AssertionError(
                f"Handler._dispatch no longer references {needle!r}; update "
                "scripts/generate_cockpit_contract.py to match the new dispatch"
            )

    # 2) Server-Sent Events streams — _STREAM_ROUTES, GET only, bearer-authed
    #    in _dispatch before the named stream method runs.
    for pattern, method_name in server._STREAM_ROUTES:
        routes.append(
            _route_entry(
                method="GET",
                path=_template_from_pattern(pattern),
                handler=getattr(handler_cls, method_name),
                requires_auth=True,
                kind="sse",
            )
        )

    # 3) Special-cased routes hand-dispatched in Handler._dispatch:
    #    the streaming chat POST (bearer-authed, chunked NDJSON) ...
    routes.append(
        _route_entry(
            method="POST",
            path=CHAT_PATH,
            handler=handler_cls._stream_chat,
            requires_auth=True,
            kind="chat-ndjson",
        )
    )
    #    ... and the static cockpit UI shell (GET only, unauthenticated —
    #    plain HTML/CSS/JS; every API call it makes carries the bearer token).
    for static_path in ("/", "/cockpit", "/cockpit/{path}"):
        routes.append(
            _route_entry(
                method="GET",
                path=static_path,
                handler=handler_cls._serve_static,
                requires_auth=False,
                kind="static",
            )
        )

    routes.sort(key=lambda r: (r["path"], r["method"]))
    return {
        "contract": CONTRACT_NAME,
        "version": CONTRACT_VERSION,
        "source": [
            "gateway/cockpit/server.py",
            "gateway/cockpit/handlers.py",
            "gateway/cockpit/handlers_autonomy.py",
        ],
        "route_count": len(routes),
        "handler_count": len({r["handler"] for r in routes}),
        "owner_gated_count": sum(1 for r in routes if r["owner_gated"]),
        "unauthenticated_count": sum(1 for r in routes if not r["requires_auth"]),
        "routes": routes,
    }


def render_json(contract: dict[str, Any]) -> str:
    return json.dumps(contract, indent=2, sort_keys=True) + "\n"


def render_markdown(contract: dict[str, Any]) -> str:
    """Human route-inventory table — the honest route/handler census."""
    lines = [
        "# Cockpit wire contract (frozen)",
        "",
        "Generated by `scripts/generate_cockpit_contract.py` from the live",
        "route tables in `gateway/cockpit/server.py` (`_ROUTES`,",
        "`_STREAM_ROUTES`) plus the special cases hand-dispatched in",
        "`Handler._dispatch` (streaming chat POST, static UI shell).",
        "Pinned by `tests/gateway/test_cockpit_contract_freeze.py` — do not",
        "edit by hand; re-run the generator and commit the diff in the same",
        "PR as any route change.",
        "",
        "## Census (real counts)",
        "",
        f"- **{contract['route_count']} routes** across "
        f"**{contract['handler_count']} distinct handlers**",
        f"- {contract['owner_gated_count']} routes are owner-gated "
        "(handler enforces the exact owner authorization phrase)",
        f"- {contract['unauthenticated_count']} routes do not require the "
        "bearer token (health, pairing bootstrap, static UI shell)",
        "",
        "Auth column: `bearer` = shared/per-device bearer token required;",
        "`open` = no token. Owner column: `owner-phrase` = the handler (or a",
        "helper it calls) compares the request against",
        "`owner_auth.AUTHORIZATION_PHRASE`.",
        "",
        "| Method | Path | Handler | Auth | Owner gate | Kind | Summary |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in contract["routes"]:
        summary = (r["summary"] or "").replace("|", "\\|")
        lines.append(
            "| {method} | `{path}` | `{handler}` | {auth} | {owner} | {kind} "
            "| {summary} |".format(
                method=r["method"],
                path=r["path"],
                handler=r["handler"],
                auth="bearer" if r["requires_auth"] else "open",
                owner="owner-phrase" if r["owner_gated"] else "—",
                kind=r["kind"],
                summary=summary,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    contract = build_contract()
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(render_json(contract), encoding="utf-8")
    MD_PATH.write_text(render_markdown(contract), encoding="utf-8")
    print(
        f"wrote {JSON_PATH.relative_to(REPO_ROOT)} and "
        f"{MD_PATH.relative_to(REPO_ROOT)}: "
        f"{contract['route_count']} routes, "
        f"{contract['handler_count']} distinct handlers, "
        f"{contract['owner_gated_count']} owner-gated, "
        f"{contract['unauthenticated_count']} unauthenticated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
