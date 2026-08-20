"""Out-of-process probe for registration surfaces with global side effects.

``PluginManager.discover_and_load()`` mutates process-global registries
(tools, hooks, slash commands, gateway platform adapters).  Running it
inside the pytest process would leak that state into every test that runs
afterwards, so the smoke layer runs it in a child interpreter and reads back
a JSON report.

Usage::

    python tests/smoke/_probe.py platforms <output.json>

Exit code is 0 whenever the probe itself ran; whether the *repository* is
healthy is decided by the test reading the report, not by this script.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def probe_platforms() -> dict:
    """Discover plugins and resolve every gateway platform adapter."""
    sys.path.insert(0, str(REPO_ROOT))
    from gateway.platform_registry import platform_registry
    from hermes_cli.plugins import PluginManager

    manager = PluginManager()
    manager.discover_and_load()

    # Names that were registered as deferred loaders during discovery.
    deferred = sorted(platform_registry._deferred)

    # Force every deferred loader to run.  A loader that raises is swallowed
    # and logged by the registry, leaving neither an entry nor a pending
    # loader — so the difference between these two sets is the failure set.
    entries = platform_registry.all_entries()
    resolved = sorted(entry.name for entry in entries)

    plugin_errors = {}
    for key, loaded in getattr(manager, "_plugins", {}).items():
        error = getattr(loaded, "error", None)
        if error:
            plugin_errors[str(key)] = str(error)

    entry_shapes = {}
    for entry in entries:
        entry_shapes[entry.name] = {
            "source": str(getattr(entry, "source", "")),
            "has_factory": callable(getattr(entry, "factory", None)),
            "fields": sorted(
                f for f in dir(entry) if not f.startswith("_")
            ),
        }

    return {
        "deferred_at_discovery": deferred,
        "resolved": resolved,
        "unresolved": sorted(set(deferred) - set(resolved)),
        "plugin_load_errors": plugin_errors,
        "entry_shapes": entry_shapes,
    }


PROBES = {"platforms": probe_platforms}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <probe-name> <output.json>", file=sys.stderr)
        return 2
    name, out_path = argv[1], argv[2]
    probe = PROBES.get(name)
    if probe is None:
        print(f"unknown probe {name!r}; known: {sorted(PROBES)}", file=sys.stderr)
        return 2
    try:
        report = {"ok": True, "result": probe()}
    except BaseException as exc:  # noqa: BLE001
        report = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    Path(out_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
