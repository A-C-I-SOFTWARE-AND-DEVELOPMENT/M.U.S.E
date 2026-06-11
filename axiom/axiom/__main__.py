"""The `python -m axiom` CLI (Phase 7.2).

Five verbs, one law:
  axiom verify <unit.json>      — the gate: attest or be rejected
  axiom run <hash> --args JSON  — execute with postconditions enforced
  axiom audit                   — recompute the full chain
  axiom forge <spec.json>       — hard-gated tournament over variants
  axiom mind observe|recall     — the memory plane

All output is JSON on stdout; exit code 0 means verified truth,
1 means a (machine-readable) refusal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.canonical import Unit
from .core.contracts import PostconditionViolation
from .core.ledger import Ledger
from .core.registry import Registry, UnresolvedReferenceError
from .core.verifier import Attestation, Verifier
from .forge.engine import ForgeEngine
from .memory.mind import Mind


def _host(data_dir: str):
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    registry = Registry(str(d / "registry.db"))
    ledger = Ledger(str(d / "ledger.db"))
    verifier = Verifier(registry, ledger)
    return registry, ledger, verifier, d


def _emit(obj, code: int = 0) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))
    return code


def cmd_verify(args) -> int:
    _r, _l, verifier, _d = _host(args.data_dir)
    form = json.loads(Path(args.unit).read_text())
    outcome = verifier.verify(Unit.from_form(form))
    if isinstance(outcome, Attestation):
        return _emit({"ok": True, "unit_hash": outcome.unit_hash,
                      "checks": list(outcome.checks),
                      "warnings": list(outcome.warnings)})
    return _emit({"ok": False, "errors": [dict(e) for e in outcome.errors]}, 1)


def cmd_run(args) -> int:
    _r, _l, verifier, _d = _host(args.data_dir)
    call_args = json.loads(args.args)
    caps = frozenset(args.capabilities.split(",")) if args.capabilities else frozenset()
    try:
        result = verifier.run(args.unit_hash, call_args, granted=caps)
        return _emit({"ok": True, "result": result})
    except UnresolvedReferenceError as e:
        return _emit({"ok": False, "error": "unresolved",
                      "unit_hash": e.unit_hash}, 1)
    except PostconditionViolation as e:
        return _emit({"ok": False, "error": "postcondition",
                      "clause": e.clause}, 1)
    except PermissionError as e:
        return _emit({"ok": False, "error": "capability", "detail": str(e)}, 1)


def cmd_audit(args) -> int:
    _r, ledger, _v, _d = _host(args.data_dir)
    valid = ledger.verify_chain()
    return _emit({"chain_valid": valid, "events": ledger.count()},
                 0 if valid else 1)


def cmd_forge(args) -> int:
    _r, _l, verifier, d = _host(args.data_dir)
    spec = json.loads(Path(args.spec).read_text())
    engine = ForgeEngine(verifier, ratings_path=str(d / "ratings.db"),
                         data_dir=str(d))
    units = {cid: Unit.from_form(form) for cid, form in spec["units"].items()}
    report = engine.run_spec_tournament(units, probes=spec.get("probes", []))
    return _emit(report)


def cmd_mind(args) -> int:
    _r, ledger, _v, d = _host(args.data_dir)
    mind = Mind(d, ledger)
    if args.mind_cmd == "observe":
        mid = mind.observe(args.content, source_grade=args.source_grade)
        return _emit({"ok": True, "memory_id": mid})
    hits = mind.recall(args.query, k=args.k)
    return _emit(hits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="axiom",
        description="AXIOM — intelligence proposes; the verifier disposes.",
    )
    parser.add_argument("--data-dir", default="data",
                        help="store directory (default: ./data)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("verify", help="verify + attest a unit JSON file")
    p.add_argument("unit")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("run", help="run an attested unit by hash")
    p.add_argument("unit_hash")
    p.add_argument("--args", default="{}", help="JSON dict of arguments")
    p.add_argument("--capabilities", default="",
                   help="comma-separated granted effects")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("audit", help="recompute the full hash chain")
    p.set_defaults(fn=cmd_audit)

    p = sub.add_parser("forge", help="run a tournament from a spec JSON")
    p.add_argument("spec")
    p.set_defaults(fn=cmd_forge)

    p = sub.add_parser("mind", help="the memory plane")
    mind_sub = p.add_subparsers(dest="mind_cmd", required=True)
    po = mind_sub.add_parser("observe")
    po.add_argument("content")
    po.add_argument("--source-grade", default="")
    pr = mind_sub.add_parser("recall")
    pr.add_argument("query")
    pr.add_argument("-k", type=int, default=5)
    p.set_defaults(fn=cmd_mind)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
