"""Owner-approved action-executor registry — the out-of-band execution seam.

The plugin write tools (Vercel / Supabase) are **propose-only**: they emit a
:class:`hermes_cli.decision_engine.DecisionVerdict` and never mutate, because a
tool cannot enforce an owner gate on a value the model controls. This module is
where an *out-of-band* owner approval (the cockpit decide handler after device
auth, or an owner-run CLI) actually performs the approved mutation.

The model never reaches this code: nothing here is a registered tool. Executors
register themselves by ``action_type`` (e.g. ``"vercel.set_env"``) on plugin
load. The approval path calls :func:`apply_owner_approved` with the exact owner
authorization phrase and the action params; on a match it dispatches to the
registered executor.

Wiring this into the cockpit is a one-liner the cockpit lane owns: on an
approved write proposal, call ``apply_owner_approved(verdict.action_type,
params, owner_phrase=<the owner's phrase>)``. Keeping the dispatch here (rather
than in the churning cockpit handler) means the executors are unit-testable in
isolation and every approval surface enforces the same gate.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

__all__ = [
    "Executor",
    "UnknownAction",
    "NotAuthorized",
    "register",
    "unregister",
    "registered",
    "has",
    "dispatch",
    "apply_owner_approved",
]

# An executor takes the action params and returns a ``{"success": bool, ...}``
# result dict (the same envelope the plugins use). It must not raise across its
# surface for expected failures (missing token, API error) — return success
# False instead.
Executor = Callable[[Dict[str, Any]], Dict[str, Any]]

_REGISTRY: dict[str, Executor] = {}


class UnknownAction(KeyError):
    """No executor is registered for the requested ``action_type``."""


class NotAuthorized(PermissionError):
    """The exact owner authorization phrase was not supplied."""


def register(action_type: str, fn: Executor, *, overwrite: bool = False) -> None:
    """Register ``fn`` as the executor for ``action_type``.

    Idempotent by default: re-registering the same ``action_type`` is a no-op
    unless ``overwrite=True``, so importing a plugin twice never clobbers a
    live executor.
    """
    if not action_type or not isinstance(action_type, str):
        raise ValueError("action_type must be a non-empty string")
    if not callable(fn):
        raise ValueError("executor must be callable")
    if action_type in _REGISTRY and not overwrite:
        return
    _REGISTRY[action_type] = fn


def unregister(action_type: str) -> bool:
    """Remove an executor. Returns False if it was not registered."""
    return _REGISTRY.pop(action_type, None) is not None


def registered() -> list[str]:
    """Sorted list of registered ``action_type`` values."""
    return sorted(_REGISTRY)


def has(action_type: str) -> bool:
    return action_type in _REGISTRY


def dispatch(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Run the executor for ``action_type`` (no authorization check).

    Internal/already-authorized callers only. Most callers want
    :func:`apply_owner_approved`.
    """
    try:
        fn = _REGISTRY[action_type]
    except KeyError as exc:
        raise UnknownAction(action_type) from exc
    return fn(dict(params or {}))


def apply_owner_approved(
    action_type: str, params: Dict[str, Any], *, owner_phrase: str
) -> Dict[str, Any]:
    """Execute an owner-approved action. Out-of-band callers only.

    Verifies the exact owner authorization phrase before dispatching. This is
    defence in depth: the cockpit already authenticates the owner's device
    before reaching here, and the CLI path is owner-run by construction. The
    model cannot invoke this (it is not a tool), so the phrase check guards the
    seam rather than being the sole gate.

    Raises :class:`NotAuthorized` on a phrase mismatch and
    :class:`UnknownAction` when no executor is registered.
    """
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if (owner_phrase or "").strip() != AUTHORIZATION_PHRASE:
        raise NotAuthorized("exact owner authorization phrase required")
    return dispatch(action_type, params)
