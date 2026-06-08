"""Guards for the ``handlers_autonomy`` extraction seam (grain g-handlers-extract).

The autonomy handler group (``autonomy_get`` / ``autonomy_set`` /
``autonomy_decisions`` and their owner-gate helpers) was physically relocated
out of the ``gateway.cockpit.handlers`` import hub into the sibling module
``gateway.cockpit.handlers_autonomy``. This is a *behaviour-preserving*
move-and-re-import: ``handlers`` re-exports the moved names so every existing
reference keeps resolving unchanged.

These tests pin the seam itself — not behaviour (the full HTTP behaviour is
already covered end-to-end by ``test_cockpit_autonomy.py``, which exercises the
routes through the live server and must keep passing untouched):

* the re-export is *identity* (``handlers.autonomy_set is
  handlers_autonomy.autonomy_set``), so callers reaching the handler via either
  module get the same function object;
* the new module imports cleanly with no import cycle, in either import order;
* the moved helpers live on the new module and ``Request`` / ``JsonResponse``
  are single-sourced (the new module reuses the canonical types rather than
  re-declaring them);
* a light smoke that ``autonomy_get(Request(...))`` still returns the expected
  status/shape after the move.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Re-export identity: the move is invisible to callers
# ---------------------------------------------------------------------------


def test_autonomy_handlers_are_reexported_by_identity() -> None:
    """``handlers.autonomy_* is handlers_autonomy.autonomy_*`` (same objects)."""
    from gateway.cockpit import handlers, handlers_autonomy

    assert handlers.autonomy_get is handlers_autonomy.autonomy_get
    assert handlers.autonomy_set is handlers_autonomy.autonomy_set
    assert handlers.autonomy_decisions is handlers_autonomy.autonomy_decisions


def test_autonomy_handlers_remain_in_handlers_public_surface() -> None:
    """The public surface of ``handlers`` (its ``__all__``) is unchanged."""
    from gateway.cockpit import handlers

    for name in ("autonomy_get", "autonomy_set", "autonomy_decisions"):
        assert name in handlers.__all__, f"{name} dropped from handlers.__all__"
        assert callable(getattr(handlers, name)), f"{name} not callable on handlers"


def test_server_route_table_resolves_to_moved_handlers() -> None:
    """``server``'s route table still calls the (now relocated) handlers.

    The dispatch table holds the live function objects; after the move they are
    the same objects exported by ``handlers_autonomy`` and re-exported by
    ``handlers``. This is the load-bearing guarantee that no route changed.
    """
    from gateway.cockpit import handlers_autonomy, server

    targets = {row[2] for row in server._ROUTES}
    assert handlers_autonomy.autonomy_get in targets
    assert handlers_autonomy.autonomy_set in targets
    assert handlers_autonomy.autonomy_decisions in targets


# ---------------------------------------------------------------------------
# No import cycle — in either order, including a clean subprocess
# ---------------------------------------------------------------------------


def test_handlers_autonomy_imports_without_cycle_either_order() -> None:
    """Importing either module first leaves both fully initialised."""
    handlers = importlib.import_module("gateway.cockpit.handlers")
    handlers_autonomy = importlib.import_module("gateway.cockpit.handlers_autonomy")
    # Request / JsonResponse are single-sourced from handlers (no duplicate type).
    assert handlers_autonomy.Request is handlers.Request
    assert handlers_autonomy.JsonResponse is handlers.JsonResponse


@pytest.mark.parametrize(
    "first",
    ["gateway.cockpit.handlers_autonomy", "gateway.cockpit.handlers"],
)
def test_clean_subprocess_import_no_cycle(first: str) -> None:
    """A fresh interpreter importing either module first must not deadlock/raise.

    Run out-of-process so the result is independent of this session's already
    imported modules — the strongest proof there is no circular-import edge.
    """
    repo_root = Path(__file__).resolve().parents[2]
    code = (
        f"import {first} as m;"
        "import gateway.cockpit.handlers as h;"
        "import gateway.cockpit.handlers_autonomy as ha;"
        "assert h.autonomy_set is ha.autonomy_set;"
        "print('ok')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"import failed:\n{proc.stderr}"
    assert proc.stdout.strip() == "ok"


# ---------------------------------------------------------------------------
# The owner-gate helpers travelled with the group
# ---------------------------------------------------------------------------


def test_owner_gate_helpers_live_on_the_new_module() -> None:
    from gateway.cockpit import handlers_autonomy

    # The privileged-levels set that gates escalation.
    assert handlers_autonomy._PRIVILEGED_AUTONOMY_LEVELS == frozenset(
        {"autonomous", "yolo", "owner_high_autonomy_coding"}
    )
    # The env kill-switch helper.
    assert callable(handlers_autonomy._autonomy_raises_locked)


# ---------------------------------------------------------------------------
# Light behaviour smoke (behaviour itself is fully covered elsewhere)
# ---------------------------------------------------------------------------


def test_autonomy_get_smoke_shape(tmp_path, monkeypatch) -> None:
    """``autonomy_get`` still returns the assisted-floor status shape."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    from gateway.cockpit.handlers import Request
    from gateway.cockpit.handlers_autonomy import autonomy_get

    resp = autonomy_get(Request(method="GET", path="/v1/cockpit/autonomy"))
    assert resp.status == 200
    assert resp.payload["level"] == "assisted"
    assert resp.payload["revocable"] is True
    assert resp.payload["capabilities"]["auto_approved"] == ["safe_read"]


def test_autonomy_set_rejects_unknown_level(tmp_path, monkeypatch) -> None:
    """A behaviour-preserving check that the moved validation path still fires."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from gateway.cockpit.handlers import Request
    from gateway.cockpit.handlers_autonomy import autonomy_set

    resp = autonomy_set(Request(method="POST", path="/x", body={"level": "wishful"}))
    assert resp.status == 400
    assert "wishful" in resp.payload["error"]
