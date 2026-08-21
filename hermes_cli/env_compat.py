"""Compatibility shim for environment variables inherited from the fork.

The downstream fork this repo consolidates used a ``MUSE_`` prefix for its
configuration. Everything ported in is renamed to ``HERMES_`` on the way, but
users who already have a populated ``.env`` or shell profile would silently
lose those settings — a renamed flag that nothing reads is a feature switched
off with no error, which is the worst possible failure mode for a config knob.

This module is that safety net. It is deliberately installed **before** any
tranche needs it: the shim has to run at process start, and wiring a
process-start hook is a core edit. T6 was the only tranche permitted to make
those, so the hook goes in now, while it is a two-line change, rather than
forcing a core edit in T11 when the first legacy name actually arrives.

## Contract for later tranches

Every tranche that ports material carrying a ``MUSE_*`` name adds its rows to
``LEGACY_ENV_ALIASES`` **in the same commit** that lands the rename. The
guard in ``tests/test_no_fork_branding.py`` allowlists this file precisely so
the table is free to spell the legacy names; nowhere else in the tree may.

Rules learned the hard way, recorded so they are not re-derived:

* Never regex-rename ``MUSE_`` to ``HERMES_`` across the tree. These names
  appear in Markdown prose, JSON fixtures and shell heredocs where a blind
  rewrite corrupts the file.
* Check for collisions first. If ``MUSE_X`` renames onto a ``HERMES_X`` that
  upstream already defines with different semantics, scope the new name
  instead (``HERMES_PRIME_X`` for prime-scoped flags).
* Register each legacy name in ``_DEPRECATED_ENV_VARS`` in
  ``hermes_cli/doctor.py`` too, so ``hermes doctor`` tells users to migrate
  rather than leaving them to discover it.

The shim is scheduled for removal in 0.21.
"""

from __future__ import annotations

import os
from typing import Dict, List

__all__ = ["LEGACY_ENV_ALIASES", "apply_legacy_env_aliases", "legacy_vars_in_use"]


#: Maps a legacy fork environment variable onto its current name.
#:
#: Empty by design: no ported material carries a legacy name yet. Tranches
#: T11-T18 populate it as they land features. See the module docstring.
LEGACY_ENV_ALIASES: Dict[str, str] = {}


def legacy_vars_in_use(environ: "os._Environ[str] | Dict[str, str] | None" = None) -> List[str]:
    """Legacy names that are set in ``environ`` — for ``hermes doctor``.

    Reports regardless of whether the modern name is also set, because a user
    who has both wants to know the legacy one is now ignored.
    """
    env = os.environ if environ is None else environ
    return sorted(legacy for legacy in LEGACY_ENV_ALIASES if legacy in env)


def apply_legacy_env_aliases(
    environ: "os._Environ[str] | Dict[str, str] | None" = None,
    *,
    warn: bool = True,
) -> List[str]:
    """Copy any set legacy variable onto its modern name.

    The modern name always wins: if both are set, the legacy value is ignored
    rather than silently overriding an explicit modern setting.

    Returns the legacy names that were actually carried across, so callers can
    report them. Emits at most one warning per process covering all of them —
    a per-variable warning on a machine with a dozen legacy names is noise
    people learn to scroll past.

    Safe to call more than once; the second call is a no-op because the modern
    names are set by then.
    """
    env = os.environ if environ is None else environ
    carried: List[str] = []

    for legacy, modern in LEGACY_ENV_ALIASES.items():
        value = env.get(legacy)
        if value is None or env.get(modern) is not None:
            continue
        env[modern] = value
        carried.append(legacy)

    if carried and warn:
        pairs = ", ".join(f"{name} -> {LEGACY_ENV_ALIASES[name]}" for name in sorted(carried))
        # Deliberately stderr and not the logging module: this runs before
        # logging is configured, and a dropped deprecation notice defeats the
        # entire point of the shim.
        import sys

        print(
            f"warning: {len(carried)} deprecated environment variable(s) in use "
            f"and honoured for now ({pairs}). Support is removed in 0.21; "
            f"run 'hermes doctor' for details.",
            file=sys.stderr,
        )

    return carried
