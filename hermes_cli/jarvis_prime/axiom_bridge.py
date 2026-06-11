"""Bridge between the Hermes runtime and the vendored AXIOM kernel.

The bridge owns a stdlib-only, hash-chained event ledger at
``$HERMES_HOME/axiom/chain.jsonl`` — every gate summary, written
decision, and UE5 action is appended as a sha256-linked record, so
``audit()`` can answer "does history verify?" with ``chain_valid``.

It deliberately does **not** use ``axiom.core.ledger.Ledger`` for the
runtime chain: that ledger hard-imports blake3/pynacl, which have no
wheels on some target platforms (Termux/aarch64). The record format
here is a structural subset of axiom's (kind/payload/prev/ts/hash) so
events can be mirrored into a full axiom ledger later without rewrites.

Soft by construction: every write path swallows its own errors, and
``MUSE_AXIOM_GATES=0`` makes the bridge inert (no reads of the chain,
no writes, ``chain_valid: None``) for hermetic CI.

CLI:
    python -m hermes_cli.jarvis_prime.axiom_bridge status
    python -m hermes_cli.jarvis_prime.axiom_bridge audit      # exit 1 iff chain invalid
    python -m hermes_cli.jarvis_prime.axiom_bridge tail [-n N]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MUSE_AXIOM_GATES_ENV = "MUSE_AXIOM_GATES"
GENESIS_PREV = "0" * 64
_CHAIN_DIR = "axiom"
_CHAIN_FILE = "chain.jsonl"

# Blast-radius constants — keep in parity with
# axiom/axiom/orchestrator/gates.py (W_*, *_THRESHOLD, GATE_PROFILES).
# Duplicated rather than imported so the bridge never depends on the
# vendored tree being importable at runtime.
_W_LOC = 0.3
_W_FILES = 0.2
_W_EFFECTS = 0.4
_W_DEFAULT_BEHAVIOR = 0.65
_LOC_NORM = 20.0
_MED_THRESHOLD = 0.3
_HIGH_THRESHOLD = 0.65

# Profiles expressed in the hermes gate vocabulary (jarvis_prime/gates.py).
GATE_PROFILES: dict[str, tuple[str, ...]] = {
    "LOW": ("build", "test"),
    "MED": ("planning", "build", "review", "test", "security", "rollback"),
    "HIGH": (
        "planning",
        "build",
        "review",
        "test",
        "security",
        "release",
        "owner_approval",
        "rollback",
    ),
}


def _hermes_home() -> Path:
    """Return the active Hermes home directory (lazy, env-aware)."""
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _record_hash(record: Mapping[str, Any]) -> str:
    body = {k: record[k] for k in ("kind", "payload", "prev", "seq", "ts", "v")}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _axiom_importable() -> bool:
    """True when the vendored axiom kernel imports (deps present)."""
    try:
        importlib.import_module("axiom.core.ledger")
        return True
    except Exception:
        pass
    # The vendored layout is <repo>/axiom/axiom/; retry with the outer
    # directory on sys.path.
    try:
        vendored = Path(__file__).resolve().parents[2] / "axiom"
        if (vendored / "axiom" / "core" / "ledger.py").exists():
            if str(vendored) not in sys.path:
                sys.path.append(str(vendored))
            importlib.import_module("axiom.core.ledger")
            return True
    except Exception:
        pass
    return False


def _dep_present(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


class AxiomBridge:
    """Runtime-facing facade: event chain, audit, risk classification."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = Path(home) if home is not None else _hermes_home()

    # ------------------------------------------------------------- properties
    @property
    def home(self) -> Path:
        return self._home

    @property
    def chain_path(self) -> Path:
        return self._home / _CHAIN_DIR / _CHAIN_FILE

    @property
    def inert(self) -> bool:
        """True when MUSE_AXIOM_GATES disables the bridge (re-read each call)."""
        flag = os.environ.get(MUSE_AXIOM_GATES_ENV, "").strip().lower()
        return flag in ("0", "false", "off", "no")

    def chain_exists(self) -> bool:
        try:
            return self.chain_path.is_file()
        except Exception:
            return False

    # ---------------------------------------------------------------- writing
    def record_event(self, kind: str, payload: Mapping[str, Any]) -> Optional[str]:
        """Append one record to the chain; returns its hash.

        Returns None (and writes nothing) when inert or on any error —
        the bridge never raises into the host.
        """
        if self.inert:
            return None
        try:
            records = self._read_records()
            prev = records[-1]["hash"] if records else GENESIS_PREV
            record: dict[str, Any] = {
                "v": 1,
                "seq": len(records),
                "ts": time.time(),
                "kind": str(kind),
                "payload": json.loads(_canonical(dict(payload))),
                "prev": prev,
            }
            record["hash"] = _record_hash(record)
            self.chain_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.chain_path, "a", encoding="utf-8") as fh:
                fh.write(_canonical(record) + "\n")
            return record["hash"]
        except Exception:
            return None

    # ---------------------------------------------------------------- reading
    def _read_records(self) -> list[dict]:
        if not self.chain_exists():
            return []
        records: list[dict] = []
        with open(self.chain_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def tail(self, n: int = 10) -> list[dict]:
        """Last *n* chain records (oldest first); [] when inert or empty."""
        if self.inert:
            return []
        try:
            return self._read_records()[-max(0, int(n)):]
        except Exception:
            return []

    def status(self) -> dict:
        """Introspection: kernel availability, degradation, chain shape."""
        available = _axiom_importable()
        deps = {
            "z3": _dep_present("z3"),
            "blake3": _dep_present("blake3"),
            "pynacl": _dep_present("nacl"),
        }
        events = 0
        if not self.inert:
            try:
                events = len(self._read_records())
            except Exception:
                events = 0
        return {
            "available": available,
            "degraded": available and not deps["z3"],
            "inert": self.inert,
            "home": str(self._home),
            "chain_path": str(self.chain_path),
            "chain_exists": self.chain_exists(),
            "chain_events": events,
            "deps": deps,
        }

    def audit(self) -> dict:
        """Verify the whole chain: every hash recomputes, every prev links.

        ``chain_valid`` is None when inert or no chain exists yet,
        True/False otherwise. ``first_bad_seq`` pinpoints the break.
        """
        base = {
            "chain_path": str(self.chain_path),
            "inert": self.inert,
            "events": 0,
            "tip": None,
            "first_bad_seq": None,
        }
        if self.inert or not self.chain_exists():
            return {**base, "chain_valid": None}
        try:
            records = self._read_records()
        except Exception as exc:
            return {**base, "chain_valid": False, "error": f"unreadable chain: {exc}"}
        prev = GENESIS_PREV
        for i, record in enumerate(records):
            try:
                ok = (
                    record.get("prev") == prev
                    and record.get("seq") == i
                    and record.get("hash") == _record_hash(record)
                )
            except Exception:
                ok = False
            if not ok:
                return {
                    **base,
                    "chain_valid": False,
                    "events": len(records),
                    "first_bad_seq": i,
                }
            prev = record["hash"]
        return {
            **base,
            "chain_valid": True,
            "events": len(records),
            "tip": prev if records else None,
        }

    # ----------------------------------------------------------- risk banding
    def classify_change(
        self,
        *,
        description: str = "",
        loc: int = 0,
        files: int = 1,
        effects: Sequence[str] = (),
        changes_default_behavior: bool = False,
    ) -> dict:
        """Blast-radius classification → risk band + exact gate profile.

        Effects and default-behavior changes dominate; HIGH always
        includes owner_approval. Pure function — works even when inert.
        """
        loc_term = min(1.0, max(0, int(loc)) / _LOC_NORM) * _W_LOC
        files_term = min(1.0, (max(1, int(files)) - 1) / 5.0) * _W_FILES
        effects_term = min(1.0, len(tuple(effects)) / 2.0) * _W_EFFECTS
        default_term = _W_DEFAULT_BEHAVIOR if changes_default_behavior else 0.0
        score = loc_term + files_term + effects_term + default_term

        if score >= _HIGH_THRESHOLD:
            risk = "HIGH"
        elif score >= _MED_THRESHOLD:
            risk = "MED"
        else:
            risk = "LOW"

        reasons: list[str] = []
        if changes_default_behavior:
            reasons.append("changes default behavior")
        if effects:
            reasons.append(f"effect surface: {', '.join(sorted(set(effects)))}")
        if loc:
            reasons.append(f"{int(loc)} lines across {max(1, int(files))} file(s)")
        if description:
            reasons.append(description)

        return {
            "risk": risk,
            "score": round(score, 4),
            "gates": list(GATE_PROFILES[risk]),
            "reasons": reasons,
        }


# ------------------------------------------------------------------ singleton
_BRIDGE: Optional[AxiomBridge] = None


def get_bridge() -> AxiomBridge:
    """Process-wide bridge, rebuilt whenever HERMES_HOME resolves elsewhere."""
    global _BRIDGE
    home = _hermes_home()
    if _BRIDGE is None or _BRIDGE.home != home:
        _BRIDGE = AxiomBridge(home)
    return _BRIDGE


def reset_bridge() -> None:
    """Drop the singleton (test helper)."""
    global _BRIDGE
    _BRIDGE = None


# ------------------------------------------------------------------------ CLI
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime.axiom_bridge",
        description="Inspect the AXIOM bridge event chain.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="bridge availability + chain shape")
    sub.add_parser("audit", help="verify the chain; exit 1 iff invalid")
    tail_p = sub.add_parser("tail", help="print the last N chain records")
    tail_p.add_argument("-n", "--count", type=int, default=10)

    args = parser.parse_args(argv)
    bridge = get_bridge()
    if args.command == "status":
        print(json.dumps(bridge.status(), indent=2))
        return 0
    if args.command == "audit":
        report = bridge.audit()
        print(json.dumps(report, indent=2))
        return 1 if report.get("chain_valid") is False else 0
    if args.command == "tail":
        print(json.dumps(bridge.tail(args.count), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
