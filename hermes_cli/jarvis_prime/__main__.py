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
- ``proposals {list|approve|reject}`` — owner review surface for
  JARVIS Prime self-update proposals. ``approve`` requires the exact
  phrase ``Yes, with authorization.`` Status updates only — execution
  of the proposed change belongs to a future lane.
- ``handoff --intent ... --packet ...`` — render the structured
  handoff template for an intent + work-packet pair. Does not execute
  owner-gated actions surfaced in the rendered handoff.
- ``models <task> [--local] [--license MIT] [--all-providers]`` —
  recommend the best open-weight models for a task (coding, bug_fix,
  reasoning, …) from the cross-referenced OSS model brain catalog,
  resolved against the providers installed on this host. ``models tasks``
  lists the known task categories. Recommendation only — selecting a
  model for live inference stays with the existing /model machinery.
- ``avatar [--locale en-US] [--json]`` — print the canonical JARVIS
  Prime avatar (brand glyph, palette, tagline) and the locale-aware
  voice + local voice-stack embodiment shared with the Android cockpit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.awareness import perceive
from hermes_cli.jarvis_prime.gates import GATES, run_gate_summary
from hermes_cli.jarvis_prime.modes import (
    ClassifierContext,
    Mode,
    ModeClassifier,
)
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE
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


def _proposals_store_path() -> Path:
    """Return the JSONL path the CLI uses to persist proposals."""

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "proposals.jsonl"


def _proposal_id(prop: dict[str, Any]) -> str:
    """Deterministic 10-char id derived from the proposal dict."""

    raw = (
        f"{prop.get('kind', '')}|"
        f"{prop.get('target_path', '')}|"
        f"{prop.get('created_at', '')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _load_proposals(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(
                f"error: invalid JSON on line {line_no} of {path}: {exc.msg}",
                file=sys.stderr,
            )
            raise SystemExit(2)
    return items


def _save_proposals(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, default=str))
            fh.write("\n")
    os.replace(tmp, path)


def _resolve_owner_phrase(args: argparse.Namespace) -> Optional[str]:
    phrase = getattr(args, "phrase", None)
    if phrase is None:
        phrase = os.environ.get("JARVIS_OWNER_PHRASE")
    return phrase


def _cmd_proposals_list(args: argparse.Namespace) -> int:
    items = _load_proposals(_proposals_store_path())
    if args.json:
        decorated = [{"id": _proposal_id(p), **p} for p in items]
        _print_json(decorated)
        return 0
    if not items:
        print("no pending proposals")
        return 0
    for p in items:
        pid = _proposal_id(p)
        kind = p.get("kind", "?")
        target = p.get("target_path", "?")
        status = p.get("status", "?")
        risk = p.get("risk_class", "?")
        print(f"{pid}  {status:<10}  {risk}  {kind} @ {target}")
    return 0


def _cmd_proposals_approve(args: argparse.Namespace) -> int:
    phrase = _resolve_owner_phrase(args)
    if phrase is None:
        print(
            "error: owner authorization phrase required for approve "
            "(pass --phrase or set JARVIS_OWNER_PHRASE)",
            file=sys.stderr,
        )
        return 1
    if phrase.strip() != AUTHORIZATION_PHRASE:
        print(
            "error: phrase does not match owner authorization phrase",
            file=sys.stderr,
        )
        return 1
    return _set_proposal_status(args.proposal_id, "approved", note="approved via CLI")


def _cmd_proposals_reject(args: argparse.Namespace) -> int:
    return _set_proposal_status(args.proposal_id, "rejected", note="rejected via CLI")


def _set_proposal_status(proposal_id: str, new_status: str, note: str) -> int:
    path = _proposals_store_path()
    items = _load_proposals(path)
    matched = False
    for p in items:
        if _proposal_id(p) == proposal_id:
            p["status"] = new_status
            p["resolved_at"] = datetime.now(timezone.utc).isoformat()
            p["owner_decision_note"] = note
            matched = True
            break
    if not matched:
        print(
            f"unknown proposal: {proposal_id!r} "
            f"(run `python -m hermes_cli.jarvis_prime proposals list` to see ids)",
            file=sys.stderr,
        )
        return 1
    _save_proposals(path, items)
    print(f"{proposal_id}: {new_status}")
    return 0


def _cmd_handoff(args: argparse.Namespace) -> int:
    packet_path = Path(args.packet)
    if not packet_path.is_file():
        print(f"error: packet file not found: {args.packet}", file=sys.stderr)
        return 2
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.packet}: {exc.msg}", file=sys.stderr)
        return 2
    jp = JarvisPrime()
    turn = jp.handle(args.intent, packet=packet, skip_perceive=args.skip_perceive)
    print(jp.render_handoff(turn))
    return 0


def _cmd_avatar(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.avatar import default_avatar

    avatar = default_avatar()
    if args.json:
        payload = avatar.voice_for(args.locale).to_dict() if args.locale else avatar.to_dict()
        _print_json(payload)
        return 0

    p = avatar.palette
    voice = avatar.voice_for(args.locale)
    lv = avatar.local_voice
    print(f"{avatar.name} — {avatar.tagline}")
    print(f"Glyph: {avatar.glyph}")
    print(f"Palette: gold {p.gold} · cyan {p.cyan} · ink {p.ink} · signal {p.signal}")
    print(
        f"Voice [{voice.locale} · {voice.language_name}]: \"{voice.greeting}\" "
        f"(tts: {voice.tts_voice}; listening: \"{voice.listening_prompt}\")"
    )
    print(
        f"Local voice stack: STT {lv.stt_engine}:{lv.stt_model} ({lv.stt_compute}) · "
        f"TTS {lv.tts_engine} · offline_first={lv.offline_first} · wake \"{lv.wake_phrase}\""
    )
    if not args.locale:
        print("Locales: " + ", ".join(avatar.locales()))
    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    from hermes_cli import oss_model_brain as ob
    from hermes_cli.jarvis_prime import model_brain as mb

    task = (args.task or "").strip()
    if not task or task == "tasks":
        catalog = ob.load_oss_catalog()
        if args.json:
            _print_json(
                {
                    "updated_at": catalog.updated_at,
                    "source": catalog.source,
                    "tasks": catalog.tasks(),
                }
            )
        else:
            print(
                f"OSS model brain — known tasks "
                f"(catalog {catalog.updated_at or '?'}, {catalog.source}):"
            )
            for t in catalog.tasks():
                print(f"  - {t}")
        return 0

    license_allow: Optional[list[str]] = None
    if args.license:
        license_allow = [
            tok.strip()
            for chunk in args.license
            for tok in chunk.split(",")
            if tok.strip()
        ]
    only_installed = not args.all_providers

    if args.json:
        models = mb.recommend_models(
            task,
            local_only=args.local,
            license_allow=license_allow,
            only_installed=only_installed,
        )
        available = ob.installed_provider_names() if only_installed else None
        results = []
        for m in models[: args.limit]:
            entry = m.to_dict()
            ref = m.resolve_provider(available)
            entry["resolved_provider"] = ref.to_dict() if ref else None
            results.append(entry)
        _print_json({"task": task, "results": results})
        return 0

    print(
        mb.render_recommendation(
            task,
            local_only=args.local,
            license_allow=license_allow,
            only_installed=only_installed,
            limit=args.limit,
        )
    )
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
    p_proposals = sub.add_parser(
        "proposals",
        help="List, approve, or reject JARVIS Prime self-update proposals",
        description=(
            "Owner review surface for JARVIS Prime's self-update proposals. "
            "The runtime stores proposals at "
            "${HERMES_HOME:-~/.hermes}/jarvis_prime/proposals.jsonl. "
            "'approve' requires the exact phrase 'Yes, with authorization.' "
            "via --phrase or the JARVIS_OWNER_PHRASE env var. "
            "approve/reject only update proposal status — they do NOT "
            "execute the proposed change. Execution belongs to a future lane."
        ),
    )
    p_proposals_sub = p_proposals.add_subparsers(
        dest="proposals_command", required=True
    )

    p_proposals_list = p_proposals_sub.add_parser(
        "list", help="List proposals from the JSONL store"
    )
    p_proposals_list.add_argument("--json", action="store_true")
    p_proposals_list.set_defaults(func=_cmd_proposals_list)

    p_proposals_approve = p_proposals_sub.add_parser(
        "approve",
        help="Approve a proposal (requires owner authorization phrase)",
    )
    p_proposals_approve.add_argument("proposal_id")
    p_proposals_approve.add_argument(
        "--phrase",
        help="Owner authorization phrase. Must be exactly 'Yes, with authorization.'",
    )
    p_proposals_approve.set_defaults(func=_cmd_proposals_approve)

    p_proposals_reject = p_proposals_sub.add_parser(
        "reject", help="Reject a proposal"
    )
    p_proposals_reject.add_argument("proposal_id")
    p_proposals_reject.set_defaults(func=_cmd_proposals_reject)

    p_handoff = sub.add_parser(
        "handoff",
        help="Render the structured handoff for an intent + work-packet",
        description=(
            "Convenience wrapper for `handle --handoff`. Reads --packet, runs "
            "the full perceive→classify→decide turn, and prints "
            "render_handoff(turn). Owner-gated actions in the rendered "
            "handoff remain data — handoff does NOT execute them."
        ),
    )
    p_handoff.add_argument("--intent", required=True)
    p_handoff.add_argument("--packet", required=True)
    p_handoff.add_argument(
        "--skip-perceive",
        action="store_true",
        help="Skip the awareness snapshot (faster, less context)",
    )
    p_handoff.set_defaults(func=_cmd_handoff)

    p_avatar = sub.add_parser(
        "avatar",
        help="Print the JARVIS Prime avatar + locale-aware voice embodiment",
        description=(
            "Print the canonical JARVIS Prime avatar (brand glyph, palette, "
            "tagline) and the locale-aware voice + local voice-stack "
            "embodiment shared with the Android cockpit "
            "(docs/jarvis-prime/avatar.json)."
        ),
    )
    p_avatar.add_argument(
        "--locale", help="Resolve the voice profile for a locale (e.g. en-US, fr, ja-JP)"
    )
    p_avatar.add_argument("--json", action="store_true")
    p_avatar.set_defaults(func=_cmd_avatar)

    p_models = sub.add_parser(
        "models",
        help="Recommend best open-weight models for a task (OSS model brain)",
        description=(
            "Recommend open-weight models for a task from the cross-referenced "
            "OSS model brain catalog (docs/ai-intelligence/oss-model-catalog.yaml), "
            "resolved against the providers installed on this host. "
            "Recommendation only — it does not switch the live inference model."
        ),
    )
    p_models.add_argument(
        "task",
        nargs="?",
        help="Task category (coding, agentic_coding, bug_fix, code_edit, "
        "reasoning, math, local_coding, local_reasoning). Use 'tasks' to list.",
    )
    p_models.add_argument(
        "--local", action="store_true", help="Only models with a local variant"
    )
    p_models.add_argument(
        "--license",
        action="append",
        metavar="SPDX",
        help="Filter by license (e.g. MIT, Apache-2.0). Repeatable or comma-separated.",
    )
    p_models.add_argument(
        "--all-providers",
        action="store_true",
        help="Don't restrict to installed providers (show every reachable option)",
    )
    p_models.add_argument("--limit", type=int, default=5)
    p_models.add_argument("--json", action="store_true")
    p_models.set_defaults(func=_cmd_models)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
