"""CLI for ``python -m hermes_cli.jarvis_prime``.

Subcommands:

- ``perceive [--dry-run]`` — print a populated AwarenessSnapshot.
- ``classify "<intent>"`` — print the ModeClassification.
- ``gate <name> --packet <path>`` — run one gate against a JSON packet.
- ``handle "<intent>"`` — full perceive→classify→decide on stdin/args.
- ``tick`` — one proactive tick (uses ~/.hermes/config.yaml if present).
- ``stop [--reason X]`` — emergency stop: clear pending gates, disable tick.
- ``forget --key K`` — remove all records with that key from memory.
- ``remember --key K --value V [--durable]`` — capture a memory record.
- ``recollect QUERY [--limit N]`` — print top relevant memories.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.awareness import perceive
from hermes_cli.jarvis_prime.gates import GATES, run_gate_summary
from hermes_cli.jarvis_prime.modes import (
    ClassifierContext,
    Mode,
    ModeClassifier,
)
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime
from hermes_cli.jarvis_prime.tick import run_once as tick_once


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _cmd_perceive(args: argparse.Namespace) -> int:
    snap = perceive(timeout=args.timeout)
    if args.dry_run or args.json:
        _print_json(snap.to_dict())
    else:
        print(snap.summary())
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    classifier = ModeClassifier()
    explicit = None
    if args.mode:
        try:
            explicit = Mode(args.mode)
        except ValueError:
            print(f"Unknown mode: {args.mode!r}", file=sys.stderr)
            return 2
    context = ClassifierContext(
        surface=args.surface,
        is_voice_input=args.voice,
        repo_root=args.repo_root,
        risk_class=args.risk_class,
        explicit_mode=explicit,
    )
    result = classifier.classify(args.intent, context=context)
    _print_json(result.to_dict())
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    packet: dict[str, Any] = {}
    if args.packet:
        path = Path(args.packet)
        packet = json.loads(path.read_text(encoding="utf-8"))

    if args.name == "all":
        summary = run_gate_summary(packet)
        if args.json:
            _print_json(summary.to_dict())
        else:
            print(summary.render())
        return 0 if summary.overall.value == "pass" else 1

    for gate in GATES:
        if gate.name == args.name:
            result = gate.evaluate(packet)
            if args.json:
                _print_json(result.to_dict())
            else:
                print(f"{result.name}: {result.outcome.value} — {result.reason}")
                for f in result.findings:
                    print(f"  - {f}")
            return 0 if result.outcome.value == "pass" else 1

    print(f"Unknown gate: {args.name!r}. Known: {[g.name for g in GATES]+['all']}", file=sys.stderr)
    return 2


def _cmd_handle(args: argparse.Namespace) -> int:
    jp = JarvisPrime()
    explicit = None
    if args.mode:
        try:
            explicit = Mode(args.mode)
        except ValueError:
            print(f"Unknown mode: {args.mode!r}", file=sys.stderr)
            return 2
    context = ClassifierContext(
        surface=args.surface,
        is_voice_input=args.voice,
        repo_root=args.repo_root,
        risk_class=args.risk_class,
        explicit_mode=explicit,
    )
    packet: Optional[dict[str, Any]] = None
    if args.packet:
        packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))

    turn = jp.handle(args.intent, context=context, packet=packet, skip_perceive=args.skip_perceive)
    if args.handoff:
        print(jp.render_handoff(turn))
    elif args.json:
        _print_json(turn.to_dict())
    else:
        print(f"Mode: {turn.classification.mode.value} (confidence {turn.classification.confidence:.2f})")
        print(f"Reason: {turn.classification.reason}")
        print(f"Route: {turn.route.target.value} — {turn.route.rationale}")
        if turn.route.delegate_to:
            print(f"Delegate to: {turn.route.delegate_to}")
        if turn.route.pending_actions:
            print(f"Owner gates pending: {', '.join(turn.route.pending_actions)}")
        if turn.gate_summary:
            print("\n" + turn.gate_summary.render())
    return 0


def _cmd_stop(args: argparse.Namespace) -> int:
    jp = JarvisPrime()
    result = jp.stop(reason=args.reason)
    _print_json(result)
    return 0


def _cmd_forget(args: argparse.Namespace) -> int:
    jp = JarvisPrime()
    removed = jp.config.memory.forget(args.key)
    _print_json({"key": args.key, "removed": removed})
    return 0


def _cmd_remember(args: argparse.Namespace) -> int:
    jp = JarvisPrime()
    durability = "durable" if args.durable else "session"
    record = jp.config.memory.remember(
        key=args.key,
        value=args.value,
        durability=durability,
        source="user",
    )
    if record is None:
        _print_json({"stored": False, "reason": "rejected (secret-like or low confidence)"})
        return 1
    _print_json({"stored": True, "record": record.to_dict()})
    return 0


def _cmd_recollect(args: argparse.Namespace) -> int:
    jp = JarvisPrime()
    hits = jp.config.memory.recollect(args.query, limit=args.limit)
    _print_json([r.to_dict() for r in hits])
    return 0


def _cmd_tick(args: argparse.Namespace) -> int:
    notes = tick_once(
        notify_via=args.notify_via,
        briefing_window=args.briefing_window,
        enabled=args.enabled or args.force,
    )
    if args.json:
        _print_json([{
            "kind": n.kind,
            "title": n.title,
            "body": n.body,
            "severity": n.severity,
        } for n in notes])
    else:
        if not notes:
            print("tick: no material change since last run")
        for n in notes:
            print(f"[{n.severity}] {n.kind}: {n.title}\n  {n.body}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime",
        description="JARVIS Prime — Jeremiah Echerd's local-first AI operating partner",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_perceive = sub.add_parser("perceive", help="Print an AwarenessSnapshot")
    p_perceive.add_argument("--dry-run", action="store_true", help="Print full JSON")
    p_perceive.add_argument("--json", action="store_true")
    p_perceive.add_argument("--timeout", type=float, default=2.0)
    p_perceive.set_defaults(func=_cmd_perceive)

    p_classify = sub.add_parser("classify", help="Classify intent → mode")
    p_classify.add_argument("intent")
    p_classify.add_argument("--surface")
    p_classify.add_argument("--voice", action="store_true")
    p_classify.add_argument("--repo-root")
    p_classify.add_argument("--risk-class")
    p_classify.add_argument("--mode", help="Pin to explicit mode")
    p_classify.set_defaults(func=_cmd_classify)

    p_gate = sub.add_parser("gate", help="Run a verification gate")
    p_gate.add_argument("name", help="Gate name or 'all'")
    p_gate.add_argument("--packet", help="Path to JSON work-packet")
    p_gate.add_argument("--json", action="store_true")
    p_gate.set_defaults(func=_cmd_gate)

    p_handle = sub.add_parser("handle", help="Full perceive → classify → decide")
    p_handle.add_argument("intent")
    p_handle.add_argument("--surface")
    p_handle.add_argument("--voice", action="store_true")
    p_handle.add_argument("--repo-root")
    p_handle.add_argument("--risk-class")
    p_handle.add_argument("--mode")
    p_handle.add_argument("--packet")
    p_handle.add_argument("--skip-perceive", action="store_true")
    p_handle.add_argument("--handoff", action="store_true")
    p_handle.add_argument("--json", action="store_true")
    p_handle.set_defaults(func=_cmd_handle)

    p_tick = sub.add_parser("tick", help="Run one proactive tick")
    p_tick.add_argument("--notify-via", default="none")
    p_tick.add_argument("--briefing-window", default="08:00 America/Toronto")
    p_tick.add_argument("--enabled", action="store_true")
    p_tick.add_argument("--force", action="store_true", help="Run even if disabled")
    p_tick.add_argument("--json", action="store_true")
    p_tick.set_defaults(func=_cmd_tick)

    p_stop = sub.add_parser("stop", help="Emergency stop: clear pending owner gates and disable tick")
    p_stop.add_argument("--reason", default="owner_requested")
    p_stop.set_defaults(func=_cmd_stop)

    p_forget = sub.add_parser("forget", help="Remove all records with a given key from memory")
    p_forget.add_argument("--key", required=True)
    p_forget.set_defaults(func=_cmd_forget)

    p_remember = sub.add_parser("remember", help="Capture a memory record")
    p_remember.add_argument("--key", required=True)
    p_remember.add_argument("--value", required=True)
    p_remember.add_argument("--durable", action="store_true", help="Promote to long-term memory")
    p_remember.set_defaults(func=_cmd_remember)

    p_recollect = sub.add_parser("recollect", help="Print top relevant memories for a query")
    p_recollect.add_argument("query")
    p_recollect.add_argument("--limit", type=int, default=5)
    p_recollect.set_defaults(func=_cmd_recollect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
