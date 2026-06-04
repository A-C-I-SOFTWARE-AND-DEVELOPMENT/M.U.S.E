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
- ``registry-update [--check] [--no-refresh] [--json]`` — REG-1: diff the
  live published model catalog against the in-repo registry
  (``config/model-catalog.yaml``) and queue owner-gated proposals for any
  drift. Proposal-only — it never edits the YAML or contacts an endpoint.
- ``calendar [--file ...] [--days N] [--json]`` — CAL-1: list the upcoming
  agenda from a local ICS file (default ``~/.hermes/calendar.ics``).
  Local-first; no Google/CalDAV network sync (an owner-gated follow-up).
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
- ``presence [--mission ... --target-app ... --real-action] [signals]``
  — compute the living-companion presence state and, with ``--mission``,
  a task animation plan. Policy/state only: no camera, microphone,
  overlay, or device control is performed; real device actions stay
  behind Android permissions and owner gates.
- ``packet "<request>" [--branch-prefix jarvis] [--json]`` — turn a
  plain-English request into a bounded coding work packet (intent,
  branch, risk class, allowed files, acceptance + verification plan,
  builder/reviewer split, owner gates). Describes scope only — it does
  not execute anything.
- ``memory-tree [--add NS::TITLE::TEXT ...] [--search Q | --outline]``
  — build an in-memory Memory Tree of source-backed notes and search it
  or print its outline. Stateless per invocation; no durable recall.
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

    print(
        f"Unknown gate: {args.name!r}. Known: {[g.name for g in GATES] + ['all']}",
        file=sys.stderr,
    )
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

    turn = jp.handle(
        args.intent, context=context, packet=packet, skip_perceive=args.skip_perceive
    )
    if args.handoff:
        print(jp.render_handoff(turn))
    elif args.json:
        _print_json(turn.to_dict())
    else:
        print(
            f"Mode: {turn.classification.mode.value} (confidence {turn.classification.confidence:.2f})"
        )
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
        _print_json({
            "stored": False,
            "reason": "rejected (secret-like or low confidence)",
        })
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
        _print_json([
            {
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
            }
            for n in notes
        ])
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


def _cmd_registry_update(args: argparse.Namespace) -> int:
    """REG-1: diff the live model catalog vs the repo registry, propose deltas.

    Proposal-only and owner-gated: with ``--check`` it just prints the delta;
    otherwise it appends the proposals to the same JSONL store that
    ``proposals {list|approve|reject}`` reads. It never edits the YAML or
    contacts a model endpoint — approval + execution stay separate, owner-gated
    steps.
    """
    from .registry_updater import (
        diff_provider_models,
        load_local_catalog,
        propose_registry_updates,
        render_deltas,
    )
    from .self_update import ProposalBook

    try:
        from hermes_cli.model_catalog import get_catalog

        remote = get_catalog(force_refresh=not getattr(args, "no_refresh", False))
    except Exception as exc:  # fail-open: offline ⇒ nothing to do
        print(f"REG-1: live catalog unavailable ({exc}); nothing to do")
        return 0
    if not remote:
        print("REG-1: live catalog unavailable; nothing to do")
        return 0

    deltas = diff_provider_models(load_local_catalog(), remote)

    if getattr(args, "json", False):
        _print_json([
            {
                "provider": d.provider,
                "added_ids": list(d.added_ids),
                "removed_ids": list(d.removed_ids),
                "risk_class": d.risk_class,
            }
            for d in deltas
        ])
    else:
        print(render_deltas(deltas))

    if not deltas or getattr(args, "check", False):
        return 0

    book = ProposalBook()
    proposals = propose_registry_updates(deltas, book)
    path = _proposals_store_path()
    existing = _load_proposals(path)
    existing_ids = {_proposal_id(p) for p in existing}
    added = 0
    for prop in proposals:
        as_dict = prop.to_dict()
        if _proposal_id(as_dict) in existing_ids:
            continue  # idempotent — don't double-queue an unchanged delta
        existing.append(as_dict)
        added += 1
    _save_proposals(path, existing)
    print(
        f"\nqueued {added} proposal(s) for owner review "
        f"(run `python -m hermes_cli.jarvis_prime proposals list`). "
        "Approve with the owner authorization phrase before any change is applied."
    )
    return 0


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


def _cmd_calendar(args: argparse.Namespace) -> int:
    """CAL-1: print upcoming events from a local ICS file (no network).

    Reads ``--file`` or, by default, ``${HERMES_HOME:-~/.hermes}/calendar.ics``.
    Local-first by design: there is no Google/CalDAV sync here — that is an
    owner-gated follow-up (OAuth + outbound network).
    """
    from datetime import datetime, timedelta, timezone

    from agent.calendar import parse_ics_file, render_agenda, upcoming

    if args.file:
        path = Path(args.file)
    else:
        base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
        path = Path(base) / "calendar.ics"

    if not path.is_file():
        print(f"calendar: no ICS file at {path} (pass --file or drop one there)")
        return 0

    events = parse_ics_file(path)
    now = datetime.now(timezone.utc)
    window = upcoming(events, now=now, within=timedelta(days=args.days))

    if getattr(args, "json", False):
        _print_json([
            {
                "summary": e.summary,
                "start": e.start_dt().isoformat(),
                "location": e.location,
                "all_day": e.all_day,
                "recurring": bool(e.rrule),
                "uid": e.uid,
            }
            for e in window
        ])
        return 0

    print(render_agenda(window, title=f"Upcoming (next {args.days}d)"))
    return 0


# --- learning dataset queue ------------------------------------------------


def _learning_store():
    # Profile-aware default path (honors HERMES_HOME / active profile).
    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

    return DatasetStore.load()


def _cmd_learning_list(args: argparse.Namespace) -> int:
    store = _learning_store()
    items = store.entries()
    if getattr(args, "json", False):
        _print_json([c.audit_card() for c in items])
        return 0
    if not items:
        print("no learning candidates")
        return 0
    for c in items:
        labels = ",".join(c.labels) or "-"
        print(
            f"{c.id}  {c.status.value:<9}  {c.trace_type.value:<26}  "
            f"labels={labels}  src={c.provenance.source_kind}"
        )
    return 0


def _cmd_learning_approve(args: argparse.Namespace) -> int:
    phrase = _resolve_owner_phrase(args)
    if phrase is None or phrase.strip() != AUTHORIZATION_PHRASE:
        print(
            "error: owner authorization phrase required for approve "
            "(pass --phrase or set JARVIS_OWNER_PHRASE; must be exactly "
            f"{AUTHORIZATION_PHRASE!r})",
            file=sys.stderr,
        )
        return 1
    store = _learning_store()
    if store.get(args.candidate_id) is None:
        print(f"unknown candidate: {args.candidate_id!r}", file=sys.stderr)
        return 1
    store.approve(args.candidate_id, note="approved via CLI")
    print(f"{args.candidate_id}: approved")
    return 0


def _cmd_learning_reject(args: argparse.Namespace) -> int:
    store = _learning_store()
    if store.get(args.candidate_id) is None:
        print(f"unknown candidate: {args.candidate_id!r}", file=sys.stderr)
        return 1
    store.reject(args.candidate_id, note="rejected via CLI")
    print(f"{args.candidate_id}: rejected")
    return 0


def _cmd_learning_export(args: argparse.Namespace) -> int:
    store = _learning_store()
    out = Path(args.out)
    fmt = args.format
    if fmt == "jsonl":
        n = store.export_jsonl(out)
    elif fmt == "preference":
        n = store.export_preference_pairs(out)
    elif fmt == "eval":
        n = store.export_eval_cases(out)
    elif fmt == "skill":
        n = store.export_skill_candidates(out)
    else:  # pragma: no cover - argparse choices guard this
        print(f"unknown format: {fmt}", file=sys.stderr)
        return 2
    print(f"exported {n} record(s) ({fmt}) -> {out}")
    return 0


def _cmd_learning_ingest_trajectory(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.learning_dataset import QualityGates
    from hermes_cli.jarvis_prime.learning_ingest import from_trajectory_file

    # The operator asserts which verification gates the *completed* traces in
    # this file have cleared. We never auto-mint a "passed" example: without
    # these flags, completed coding traces lack their required gates and are
    # skipped (failed traces still import as labeled negatives).
    quality = QualityGates(
        tests_passed=args.tests_passed,
        reviewer_passed=args.reviewer_passed,
        rollback_available=args.rollback_available,
        citations_verified=args.citations_verified,
    )
    store = _learning_store()
    created = from_trajectory_file(Path(args.path), store, quality=quality)
    print(f"ingested {len(created)} candidate(s) from {args.path}")
    skipped_for_gates = False
    for note in store.load_diagnostics:
        print(f"  skipped: {note}", file=sys.stderr)
        if "quality gates not met" in note:
            skipped_for_gates = True
    if skipped_for_gates and not (
        args.tests_passed or args.reviewer_passed or args.rollback_available
    ):
        print(
            "  hint: completed coding traces need their gates asserted — re-run "
            "with --tests-passed --reviewer-passed --rollback-available once the "
            "run is verified green.",
            file=sys.stderr,
        )
    return 0


# --- open data sources registry --------------------------------------------


def _data_sources_pool(args: argparse.Namespace):
    """Resolve the registry, honoring an optional --registry override."""
    from hermes_cli.jarvis_prime.open_data_sources import load_registry

    path = Path(args.registry) if getattr(args, "registry", None) else None
    return load_registry(path)


def _cmd_data_sources_list(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.open_data_sources import DatasetRole

    sources = _data_sources_pool(args)
    if getattr(args, "role", None):
        want = DatasetRole(args.role)
        sources = [s for s in sources if s.role == want]
    if getattr(args, "core", False):
        sources = [s for s in sources if s.core_ingest]
    if getattr(args, "wall", False):
        sources = [s for s in sources if s.benchmark_wall]

    if getattr(args, "json", False):
        _print_json([s.to_dict() for s in sources])
        return 0
    if not sources:
        print("no matching data sources")
        return 0
    for s in sources:
        flags = []
        if s.core_ingest:
            flags.append("core")
        if s.benchmark_wall:
            flags.append("wall")
        tag = ("[" + ",".join(flags) + "]") if flags else ""
        print(
            f"{s.rank:>2}  {s.key:<22}  {s.role.value:<5}  "
            f"{s.evidence_strength.value:<10}  {s.name} {tag}".rstrip()
        )
    return 0


def _cmd_data_sources_show(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.open_data_sources import get

    src = get(args.key, sources=_data_sources_pool(args))
    if src is None:
        print(f"unknown data source: {args.key!r}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        _print_json(src.to_dict())
        return 0
    d = src.to_dict()
    for label in (
        "name",
        "rank",
        "role",
        "trainable",
        "core_ingest",
        "benchmark_wall",
        "legal_posture",
        "evidence_strength",
        "languages",
        "size",
        "schema_provenance",
        "quality_strengths",
        "biases",
        "best_tasks",
        "license_notes",
        "source_uris",
    ):
        print(f"{label:>18}: {d[label]}")
    return 0


def _cmd_data_sources_register_vault(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.open_data_sources import register_all_in_vault
    from hermes_cli.jarvis_prime.research_vault import ResearchVault

    sources = _data_sources_pool(args)
    dry_run = getattr(args, "dry_run", False)
    vault_path = Path(args.store) if getattr(args, "store", None) else None
    vault = ResearchVault.load(vault_path)
    result = register_all_in_vault(
        vault,
        sources=sources,
        include_restricted=getattr(args, "include_restricted", False),
        persist=not dry_run,
    )
    if getattr(args, "json", False):
        _print_json(
            {
                "dry_run": dry_run,
                "registered": [a.id for a in result.registered],
                "skipped": [{"key": k, "reason": r} for k, r in result.skipped],
                "vault": str(vault._resolve_path()),
            }
        )
        return 0
    verb = "would register" if dry_run else "registered"
    print(f"{verb} {len(result.registered)} source(s) into the Research Vault")
    for key, reason in result.skipped:
        print(f"  skipped {key}: {reason}")
    if not dry_run:
        print(f"  vault: {vault._resolve_path()}")
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
        payload = (
            avatar.voice_for(args.locale).to_dict() if args.locale else avatar.to_dict()
        )
        _print_json(payload)
        return 0

    p = avatar.palette
    voice = avatar.voice_for(args.locale)
    lv = avatar.local_voice
    print(f"{avatar.name} — {avatar.tagline}")
    print(f"Glyph: {avatar.glyph}")
    print(f"Palette: gold {p.gold} · cyan {p.cyan} · ink {p.ink} · signal {p.signal}")
    print(
        f'Voice [{voice.locale} · {voice.language_name}]: "{voice.greeting}" '
        f'(tts: {voice.tts_voice}; listening: "{voice.listening_prompt}")'
    )
    print(
        f"Local voice stack: STT {lv.stt_engine}:{lv.stt_model} ({lv.stt_compute}) · "
        f'TTS {lv.tts_engine} · offline_first={lv.offline_first} · wake "{lv.wake_phrase}"'
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
            _print_json({
                "updated_at": catalog.updated_at,
                "source": catalog.source,
                "tasks": catalog.tasks(),
            })
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


def _cmd_presence(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.companion_presence import (
        CompanionPresencePolicy,
        PresenceSignals,
    )

    policy = CompanionPresencePolicy(attention_threshold=args.attention_threshold)
    signals = PresenceSignals(
        gateway_online=not args.offline,
        emergency_stop=args.emergency_stop,
        microphone_active=args.listening,
        camera_attention_opt_in=args.attention_opt_in,
        user_attention_confidence=args.attention_confidence,
        thinking=args.thinking,
        working=args.working,
        target_app=args.target_app,
        target_on_next_screen=args.next_screen,
        pending_owner_approval=args.pending_approval,
        blocked_reason=args.blocked_reason or "",
    )
    state = policy.state_for(signals)
    payload: dict[str, Any] = {"state": state.value}
    if args.mission:
        plan = policy.plan_task_animation(
            args.mission,
            target_app=args.target_app,
            target_on_next_screen=args.next_screen,
            real_device_action_requested=args.real_action,
        )
        payload["plan"] = plan.to_dict()

    if args.json or args.mission:
        _print_json(payload)
        return 0
    print(f"state: {state.value}")
    return 0


def _cmd_packet(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.natural_language_coder import (
        build_work_packet,
        render_packet_markdown,
        validate_work_packet,
    )

    packet = build_work_packet(args.prompt, branch_prefix=args.branch_prefix)

    # --gate-check: run the planning/build/etc. gate summary over the packet.
    if getattr(args, "gate_check", False):
        from hermes_cli.jarvis_prime.gates import run_gate_summary

        summary = run_gate_summary(packet.to_gate_packet())
        if args.json:
            _print_json({"packet": packet.to_dict(), "gates": summary.to_dict()})
        else:
            print(summary.render())
        return 0

    # --validate: structural validation of the packet.
    if getattr(args, "validate", False):
        result = validate_work_packet(packet)
        if args.json:
            _print_json({"packet": packet.to_dict(), "validation": result.to_dict()})
        else:
            print(f"valid: {result.ok}")
            for f in result.findings:
                print(f"  [{f.severity}] {f.field}: {f.message}")
        return 0

    if getattr(args, "markdown", False):
        print(render_packet_markdown(packet))
        return 0

    if args.json:
        _print_json(packet.to_dict())
        return 0
    print(f"mission: {packet.mission}")
    print(
        f"intent: {packet.intent.value}  risk: {packet.risk_class}  "
        f"branch: {packet.branch}"
    )
    print(f"builder: {packet.primary_worker}  reviewer: {packet.reviewer_worker}")
    if packet.owner_gated_actions:
        print("owner-gated: " + ", ".join(packet.owner_gated_actions))
    if packet.owner_gates:
        print("owner gates: " + ", ".join(g.value for g in packet.owner_gates))
    print("allowed files: " + ", ".join(packet.allowed_files))
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    """Compile plain English into a work packet or an automation flow."""

    from hermes_cli.jarvis_prime import nl_compile

    res = nl_compile.compile_request(
        args.prompt,
        backend=args.backend,
        branch_prefix=args.branch_prefix,
        gate_check=getattr(args, "gate_check", False),
        learn=getattr(args, "learn", False),
    )

    if args.json:
        _print_json(res.to_dict())
        if res.needs_clarification:
            return 2
        # A blocked (gate-bypass) request is not a successful compile — mirror
        # the non-JSON path's exit code so automation can detect it.
        if res.backend is not None and res.backend.blocked:
            return 1
        return 0

    if res.needs_clarification:
        print("Clarifying questions before I can compile:")
        for q in res.clarifying_questions():
            print(f"  - {q}")
        return 2

    from hermes_cli.jarvis_prime.ir_compilers.automation_flow import AutomationFlow
    from hermes_cli.jarvis_prime.natural_language_coder import CodingWorkPacket

    decision = res.backend
    # Past the needs_clarification guard the façade always sets a decision.
    assert decision is not None
    if decision.blocked or decision.selected is None:
        print("blocked: request attempts to bypass owner gates — no backend selected")
        return 1

    print(f"backend: {decision.selected.value}")
    if getattr(args, "explain", False):
        print(f"rationale: {decision.rationale}")
        for s in decision.scores:
            print(f"  score {s.target.value}: {s.score:.2f}  ({s.rationale})")

    result = res.compile_result
    if result is not None:
        artifact = result.artifact
        if isinstance(artifact, CodingWorkPacket):
            print(f"mission: {artifact.mission}")
            print(
                f"intent: {artifact.intent.value}  risk: {artifact.risk_class}  "
                f"branch: {artifact.branch}"
            )
            print("allowed files: " + ", ".join(artifact.allowed_files))
        elif isinstance(artifact, AutomationFlow):
            print(f"flow: {artifact.name}  ({len(artifact.triggers)} triggers, "
                  f"{len(artifact.steps)} steps)")
            if artifact.owner_gated_actions:
                print("owner-gated: " + ", ".join(artifact.owner_gated_actions))
            validation = artifact.validate()
            print(f"flow valid: {validation.ok}")
        for note in result.notes:
            print(f"  note: {note}")

    if res.gate_summary is not None:
        print(res.gate_summary.render())

    return 0


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import model_bootstrap as mb

    result = mb.bootstrap(
        free_first=args.free_first,
        jarvis=args.jarvis,
        dry_run=args.dry_run,
        no_pull=args.no_pull,
        force=args.force,
        local_only=args.local_only,
    )
    if args.json:
        _print_json(result.to_dict())
    else:
        print(result.render())
    return 0 if result.ok else 1


def _cmd_launch(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.launch import launch as _launch

    summary = _launch(
        free_first=args.free_first,
        no_pull=args.no_pull,
        force=args.force,
        local_only=args.local_only,
        dry_run=args.dry_run,
    )
    if args.json:
        _print_json(summary.to_dict())
    else:
        print(summary.render())
    return 0 if summary.ok else 1


def _cmd_launch_doctor(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.launch_doctor import run_launch_doctor

    report = run_launch_doctor()
    if args.json:
        _print_json(report.to_dict())
    else:
        print(report.render())
    return 0 if report.ok else 1


def _cmd_gemma(args: argparse.Namespace) -> int:
    """Module-CLI parity for ``hermes models gemma …`` (logic in gemma_cli)."""
    from hermes_cli.jarvis_prime import gemma_cli

    return gemma_cli.dispatch(args)


def _cmd_memory_tree(args: argparse.Namespace) -> int:
    # Persistent Memory OS operations are addressed by a positional verb
    # (add / search / outline / export-markdown). Without a verb the command
    # keeps its original stateless, in-memory behavior driven by --add/--search.
    if getattr(args, "op", None):
        return _cmd_memory_tree_store(args)

    from hermes_cli.jarvis_prime.memory_tree import MemoryTree

    tree = MemoryTree()
    for raw in args.add or []:
        parts = raw.split("::", 2)
        if len(parts) != 3:
            print(
                f"error: --add expects 'namespace::title::text', got {raw!r}",
                file=sys.stderr,
            )
            return 2
        namespace, title, text = parts
        tree.add(text, namespace=namespace, title=title)

    if args.search:
        hits = tree.search(args.search, namespace=args.namespace, limit=args.limit)
        if args.json:
            _print_json([chunk.to_dict() for chunk in hits])
        else:
            for chunk in hits:
                print(f"[{chunk.namespace}] {chunk.title} ({chunk.source_uri})")
        return 0

    if args.json:
        _print_json([chunk.to_dict() for chunk in tree.chunks])
    else:
        print(tree.outline())
    return 0


def _cmd_memory_tree_store(args: argparse.Namespace) -> int:
    """Persistent Memory Tree operations (durable JSONL-backed store)."""

    from hermes_cli.jarvis_prime.memory_tree import (
        MemoryLayer,
        MemoryTreeStore,
        SourceTrust,
    )

    store_path = Path(args.store) if getattr(args, "store", None) else None
    store = MemoryTreeStore.load(store_path)

    if args.op == "add":
        if not args.arg or args.arg.count("::") < 2:
            print(
                "error: add expects 'namespace::title::text'",
                file=sys.stderr,
            )
            return 2
        namespace, title, text = args.arg.split("::", 2)
        layer = (
            MemoryLayer(args.layer)
            if getattr(args, "layer", None)
            else MemoryLayer.SESSION
        )
        trust = (
            SourceTrust(args.trust)
            if getattr(args, "trust", None)
            else SourceTrust.UNVERIFIED
        )
        result = store.write(
            text,
            namespace=namespace,
            title=title,
            layer=layer,
            source_uri=getattr(args, "source", None),
            source_trust=trust,
            confidence=getattr(args, "confidence", 0.5),
            owner_approved=getattr(args, "owner_approved", False),
        )
        if args.json:
            _print_json(result.to_dict())
        elif result.ok and result.node is not None:
            layer_name = result.effective_layer.value if result.effective_layer else "?"
            print(f"ok: wrote {result.node.id} ({layer_name})")
            if result.contradiction:
                print(f"  contradiction: {result.contradiction.id}")
            for r in result.reasons:
                print(f"  note: {r}")
        else:
            print("rejected: " + "; ".join(result.reasons))
        return 0 if result.ok else 1

    if args.op == "search":
        hits = store.search(
            args.arg or "", include_contested=getattr(args, "contested", False)
        )
        if args.json:
            _print_json([h.to_dict() for h in hits])
        else:
            for h in hits:
                print(f"[{h.node.namespace}] {h.node.title} (score={h.score:.2f})")
        return 0

    if args.op == "outline":
        print(store.outline())
        return 0

    if args.op == "export-markdown":
        print(store.export_markdown())
        return 0

    print(f"error: unknown memory-tree op {args.op!r}", file=sys.stderr)
    return 2


def _cmd_research(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.research_vault import (
        EvidenceStrength,
        ResearchVault,
        SourceType,
    )

    vault_path = Path(args.store) if getattr(args, "store", None) else None
    vault = ResearchVault.load(vault_path)

    if args.op == "add":
        art = vault.add(
            args.title,
            args.uri,
            source_type=SourceType(args.source_type),
            evidence_strength=EvidenceStrength(args.strength),
            excerpt=args.excerpt or "",
        )
        if args.json:
            _print_json(art.to_dict())
        else:
            print(f"ok: added {art.id} {art.title}")
        return 0

    if args.op == "list":
        items = vault.entries()
        if args.json:
            _print_json([a.to_dict() for a in items])
        else:
            for a in items:
                print(
                    f"{a.id} [{a.source_type.value}/{a.evidence_strength.value}] {a.title}"
                )
        return 0

    if args.op == "export-markdown":
        print(vault.export_markdown())
        return 0

    print(f"error: unknown research op {args.op!r}", file=sys.stderr)
    return 2


def _cmd_graph(args: argparse.Namespace) -> int:
    """GraphRAG knowledge-graph lane: build / query / related.

    Supplements (never replaces) the Memory Tree and Research Vault. The graph
    is an additive cache rebuilt from the repo + local stores; ``build`` is
    read-only over those sources and writes only the graph cache file.
    """

    from hermes_cli.jarvis_prime.graphrag import (
        GraphStore,
        build_and_save,
        coding_query,
        find_entity_node,
        global_query,
        local_query,
        related_items,
    )

    store = GraphStore(Path(args.store) if getattr(args, "store", None) else None)

    if args.op == "build":
        indexers = args.indexers.split(",") if getattr(args, "indexers", None) else None
        graph, path = build_and_save(
            args.repo_root, indexers=indexers, store=store
        )
        payload = {"saved": str(path), **graph.stats()}
        if args.json:
            _print_json(payload)
        else:
            print(graph.render())
            print(f"\nsaved: {path}")
        return 0

    # query / related read the cached graph (build it on first use).
    graph = store.load()
    if not graph.nodes:
        graph, _ = build_and_save(args.repo_root, store=store)

    if args.op == "query":
        mode = getattr(args, "mode", "local")
        q = args.query or ""
        if mode == "global":
            answer = global_query(graph, q)
        elif mode == "coding":
            answer = coding_query(graph, q)
        else:
            answer = local_query(graph, q)
        if args.json:
            _print_json(answer.to_dict())
        else:
            print(answer.render())
        return 0

    if args.op == "related":
        node_id_ = find_entity_node(graph, node=args.node, key=args.node)
        if not node_id_:
            print(f"error: no graph node matches {args.node!r}", file=sys.stderr)
            return 2
        items = related_items(graph, node_id_)
        if args.json:
            _print_json({"node": node_id_, "related": items})
        else:
            for it in items:
                flag = "✓" if it["source_backed"] else "·"
                print(f"{flag} [{it['kind']}/{it['relation']}] {it['title']}")
        return 0

    print(f"error: unknown graph op {args.op!r}", file=sys.stderr)
    return 2


def _cmd_model_scorecard(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.model_scorecard import (
        ModelScorecard,
        ScorecardBook,
        local_endpoint_packet,
    )

    if args.op == "local-endpoint":
        _print_json(
            local_endpoint_packet(
                args.model, endpoint=args.endpoint, server=args.server
            )
        )
        return 0

    book_path = Path(args.store) if getattr(args, "store", None) else None
    book = ScorecardBook.load(book_path)

    if args.op == "add":
        card = ModelScorecard(
            model=args.model,
            provider=args.provider,
            task_type=args.task,
            risk_class=getattr(args, "risk_class", "RC1"),
            tests_passed=getattr(args, "tests_passed", 0),
            tests_failed=getattr(args, "tests_failed", 0),
            owner_corrections=getattr(args, "owner_corrections", 0),
            hallucination_corrections=getattr(args, "hallucination_corrections", 0),
            accepted_diff_rate=getattr(args, "accepted_diff_rate", None),
            context_length=getattr(args, "context_length", 0) or 0,
            tool_reliability=getattr(args, "tool_reliability", None),
            citation_accuracy=getattr(args, "citation_accuracy", None),
            mobile_ux_suitability=getattr(args, "mobile_ux_suitability", None),
        )
        book.record(card)
        if args.json:
            _print_json(card.to_dict())
        else:
            print(f"ok: recorded {card.model} score={card.score:.2f}")
        return 0

    if args.op == "list":
        if args.json:
            _print_json([c.to_dict() for c in book.scorecards])
        else:
            print(book.render(task_type=getattr(args, "task", None)))
        return 0

    if args.op == "recommend":
        ranked = book.recommend(
            args.task,
            risk_class=getattr(args, "risk_class", None),
            task_class=getattr(args, "task_class", None) or args.task,
        )
        if args.json:
            _print_json([{"model": m, "score": s, "samples": n} for m, s, n in ranked])
        else:
            for m, s, n in ranked:
                print(f"{m}: score={s:.2f} (n={n})")
        return 0

    print(f"error: unknown model-scorecard op {args.op!r}", file=sys.stderr)
    return 2


def _cmd_route(args: argparse.Namespace) -> int:
    """Explain the evidence-backed model route for a task class."""
    from hermes_cli.jarvis_prime import task_router as tr

    if getattr(args, "task", None):
        try:
            decision = tr.route_for_task(args.task)
        except ValueError as exc:
            print(
                f"error: {exc}. Known task classes: "
                + ", ".join(t.value for t in tr.TaskClass),
                file=sys.stderr,
            )
            return 2
        if args.json:
            _print_json(decision.to_dict())
        else:
            print(tr.explain(decision))
        return 0

    decisions = tr.all_routes()
    if args.json:
        _print_json([d.to_dict() for d in decisions])
    else:
        print("\n\n".join(tr.explain(d) for d in decisions))
    return 0


def _cmd_owner_brief(args: argparse.Namespace) -> int:
    """Render a daily owner brief from a monitor context.

    Read-only. The context comes from one of:
    * ``--auto`` — assemble live local state via monitor_collectors
      (git status, Memory Tree contradictions, model scorecards, proposals).
    * ``--context PATH`` — a supplied JSON monitor-context file.
    * neither — an empty context, so every source reports BLIND (the honest
      signal that nothing was observed).
    """

    from hermes_cli.jarvis_prime.monitors import MonitorBoard
    from hermes_cli.jarvis_prime.owner_brief import build_owner_brief

    context: dict = {}
    if getattr(args, "auto", False):
        from hermes_cli.jarvis_prime.monitor_collectors import collect_context
        from pathlib import Path as _Path

        context = collect_context(
            repo_root=getattr(args, "repo_root", ".") or ".",
            memory_store_path=_Path(args.memory_store)
            if getattr(args, "memory_store", None)
            else None,
            scorecard_path=_Path(args.scorecard_store)
            if getattr(args, "scorecard_store", None)
            else None,
            proposals_path=_Path(args.proposals)
            if getattr(args, "proposals", None)
            else None,
        )
    elif getattr(args, "context", None):
        with open(args.context, "r", encoding="utf-8") as fh:
            context = json.load(fh)

    board = MonitorBoard.default()
    results = board.run(context)
    brief = build_owner_brief(
        results,
        board=board,
        changed=context.get("changed", []),
        learned=context.get("learned", []),
        blocked=context.get("blocked", []),
    )
    if args.json:
        _print_json({
            "brief": brief.to_dict(),
            "monitors": [r.to_dict() for r in results],
        })
    else:
        print(brief.render())
    return 0


def _cmd_navigate(args: argparse.Namespace) -> int:
    """Localize an objective to candidate edit sites (HyperAgent-style).

    Deterministic and read-only — the same navigation a ``/orchestrate`` job
    now runs before dispatch. Ranks the files most likely to need editing,
    with the tests to run; no LLM is used for localization.
    """
    from hermes_cli.jarvis_prime.navigation import Navigator

    nav = Navigator.for_repo(args.repo or ".")
    result = nav.navigate(args.issue, limit=args.limit)
    if args.json:
        _print_json(result.to_dict())
        return 0
    sites = result.edit_sites
    if not sites:
        print(f"No candidate edit sites found for: {result.issue}")
        return 0
    print(f"Navigation for: {result.issue}")
    for s in sites:
        print(f"  [{s.rank}] {s.path}  (confidence {s.confidence:.2f}) — {s.rationale}")
    verify = result.worker_packet().get("verify_with") or []
    if verify:
        print("  verify with: " + ", ".join(str(v) for v in verify))
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

    p_stop = sub.add_parser(
        "stop", help="Emergency stop: clear pending owner gates and disable tick"
    )
    p_stop.add_argument("--reason", default="owner_requested")
    p_stop.set_defaults(func=_cmd_stop)

    p_forget = sub.add_parser(
        "forget", help="Remove all records with a given key from memory"
    )
    p_forget.add_argument("--key", required=True)
    p_forget.set_defaults(func=_cmd_forget)

    p_remember = sub.add_parser("remember", help="Capture a memory record")
    p_remember.add_argument("--key", required=True)
    p_remember.add_argument("--value", required=True)
    p_remember.add_argument(
        "--durable", action="store_true", help="Promote to long-term memory"
    )
    p_remember.set_defaults(func=_cmd_remember)

    p_recollect = sub.add_parser(
        "recollect", help="Print top relevant memories for a query"
    )
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

    p_proposals_reject = p_proposals_sub.add_parser("reject", help="Reject a proposal")
    p_proposals_reject.add_argument("proposal_id")
    p_proposals_reject.set_defaults(func=_cmd_proposals_reject)

    p_registry = sub.add_parser(
        "registry-update",
        help="REG-1: diff the live model catalog vs the repo registry and queue proposals",
        description=(
            "Diff the live, published model-catalog manifest against the in-repo "
            "registry (config/model-catalog.yaml) and queue owner-gated proposals "
            "for any drift. Proposal-only: it never edits the YAML or contacts a "
            "model endpoint. New model ids (a new reachable endpoint) are RC3 and "
            "always need owner approval. Use --check for a dry run."
        ),
    )
    p_registry.add_argument(
        "--check",
        action="store_true",
        help="Dry run — print the delta but don't queue any proposals",
    )
    p_registry.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use the cached catalog instead of forcing a live refresh",
    )
    p_registry.add_argument("--json", action="store_true")
    p_registry.set_defaults(func=_cmd_registry_update)

    p_calendar = sub.add_parser(
        "calendar",
        help="CAL-1: list upcoming events from a local ICS file (local-first, no sync)",
        description=(
            "Read a local ICS (iCalendar) file and print the upcoming agenda. "
            "Local-first by design: no Google/CalDAV network sync (that needs "
            "OAuth and is an owner-gated follow-up). Defaults to "
            "${HERMES_HOME:-~/.hermes}/calendar.ics."
        ),
    )
    p_calendar.add_argument("--file", help="Path to an .ics file (default: ~/.hermes/calendar.ics)")
    p_calendar.add_argument("--days", type=int, default=7, help="Look-ahead window in days")
    p_calendar.add_argument("--json", action="store_true")
    p_calendar.set_defaults(func=_cmd_calendar)

    p_learning = sub.add_parser(
        "learning",
        help="Review/approve/export JARVIS learning-dataset candidates",
        description=(
            "Owner review surface for the JARVIS learning dataset. Candidates "
            "are stored at ${HERMES_HOME:-~/.hermes}/jarvis_prime/"
            "learning_dataset.jsonl. Only validated traces are stored; only "
            "owner-approved traces are exported. 'approve' requires the exact "
            "phrase 'Yes, with authorization.' via --phrase or JARVIS_OWNER_PHRASE."
        ),
    )
    p_learning_sub = p_learning.add_subparsers(
        dest="learning_command", required=True
    )

    p_learning_list = p_learning_sub.add_parser(
        "list", help="List learning candidates"
    )
    p_learning_list.add_argument("--json", action="store_true")
    p_learning_list.set_defaults(func=_cmd_learning_list)

    p_learning_approve = p_learning_sub.add_parser(
        "approve", help="Approve a candidate (requires owner authorization phrase)"
    )
    p_learning_approve.add_argument("candidate_id")
    p_learning_approve.add_argument(
        "--phrase",
        help="Owner authorization phrase. Must be exactly 'Yes, with authorization.'",
    )
    p_learning_approve.set_defaults(func=_cmd_learning_approve)

    p_learning_reject = p_learning_sub.add_parser(
        "reject", help="Reject a candidate"
    )
    p_learning_reject.add_argument("candidate_id")
    p_learning_reject.set_defaults(func=_cmd_learning_reject)

    p_learning_export = p_learning_sub.add_parser(
        "export", help="Export approved candidates to a file"
    )
    p_learning_export.add_argument(
        "--format",
        choices=("jsonl", "preference", "eval", "skill"),
        default="jsonl",
    )
    p_learning_export.add_argument("--out", required=True, help="Output file path")
    p_learning_export.set_defaults(func=_cmd_learning_export)

    p_learning_ingest = p_learning_sub.add_parser(
        "ingest-trajectory",
        help="Ingest a save_trajectory-format JSONL into the candidate queue",
        description=(
            "Completed traces become coding_task_trace candidates; failed "
            "traces become failed_attempt_trace candidates (labeled negative). "
            "Completed coding traces require their verification gates — assert "
            "them with the flags below once the run is verified, or they are "
            "skipped (we never auto-mint a passed example)."
        ),
    )
    p_learning_ingest.add_argument("path", help="Path to the trajectory JSONL")
    p_learning_ingest.add_argument(
        "--tests-passed", action="store_true",
        help="Assert the completed traces' tests passed",
    )
    p_learning_ingest.add_argument(
        "--reviewer-passed", action="store_true",
        help="Assert a reviewer approved the completed traces",
    )
    p_learning_ingest.add_argument(
        "--rollback-available", action="store_true",
        help="Assert a rollback is available for the completed traces",
    )
    p_learning_ingest.add_argument(
        "--citations-verified", action="store_true",
        help="Assert citations were verified (research/evidence traces)",
    )
    p_learning_ingest.set_defaults(func=_cmd_learning_ingest_trajectory)

    # data-sources — open data-source registry for training/eval (read-only +
    # a Research-Vault bridge). Inventory lives in
    # docs/ai-intelligence/open-data-sources.yaml.
    p_data = sub.add_parser(
        "data-sources",
        help="Open data-source registry: list/show, bridge into the Research Vault",
        description=(
            "Browse the open data sources inventoried in "
            "docs/ai-intelligence/open-data-sources.yaml (the registry behind "
            "docs/ai-intelligence/top-open-data-sources-for-training.md) and "
            "bridge them into the Research Vault so the JARVIS learning pipeline "
            "can cite them. Read-only except 'register-vault', which only adds "
            "provenance cards (no dataset is downloaded)."
        ),
    )
    p_data_sub = p_data.add_subparsers(dest="data_command", required=True)

    p_data_list = p_data_sub.add_parser("list", help="List registry sources")
    p_data_list.add_argument(
        "--role", choices=("train", "eval", "both"), help="Filter by role"
    )
    p_data_list.add_argument(
        "--core", action="store_true", help="Only the core training-ingest set"
    )
    p_data_list.add_argument(
        "--wall", action="store_true", help="Only the eval-only benchmark wall"
    )
    p_data_list.add_argument("--registry", help="Override registry YAML path")
    p_data_list.add_argument("--json", action="store_true")
    p_data_list.set_defaults(func=_cmd_data_sources_list)

    p_data_show = p_data_sub.add_parser("show", help="Show one source by key")
    p_data_show.add_argument("key", help="Source key (e.g. the-stack-v2)")
    p_data_show.add_argument("--registry", help="Override registry YAML path")
    p_data_show.add_argument("--json", action="store_true")
    p_data_show.set_defaults(func=_cmd_data_sources_show)

    p_data_reg = p_data_sub.add_parser(
        "register-vault",
        help="Bridge registry sources into the Research Vault as provenance cards",
        description=(
            "Record each source as a Research Vault artifact (source URI, "
            "evidence strength, license notes). Sources legally barred from LLM "
            "training (legal_posture=no_llm_training) are skipped unless "
            "--include-restricted is passed."
        ),
    )
    p_data_reg.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Report what would be registered without writing the vault",
    )
    p_data_reg.add_argument(
        "--include-restricted", dest="include_restricted", action="store_true",
        help="Also register no_llm_training sources (default: skip)",
    )
    p_data_reg.add_argument("--registry", help="Override registry YAML path")
    p_data_reg.add_argument("--store", help="Path to a persistent research-vault JSONL")
    p_data_reg.add_argument("--json", action="store_true")
    p_data_reg.set_defaults(func=_cmd_data_sources_register_vault)

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
        "--locale",
        help="Resolve the voice profile for a locale (e.g. en-US, fr, ja-JP)",
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

    # Gemma 4 wiring (module-CLI parity with `hermes models gemma …`).
    p_gemma = sub.add_parser(
        "gemma",
        help="Gemma 4 wiring: status, doctor, smoke, recommend, scorecards, promote",
    )
    g_sub = p_gemma.add_subparsers(dest="gemma_command")
    _gs = g_sub.add_parser("status", help="Configured/installed/promoted status")
    _gs.add_argument("--json", action="store_true")
    _gd = g_sub.add_parser("doctor", help="Gemma wiring + safety doctor")
    _gd.add_argument("--json", action="store_true")
    _gk = g_sub.add_parser("smoke", help="Opt-in local completion probe")
    _gk.add_argument("--variant")
    _gk.add_argument("--json", action="store_true")
    _gr = g_sub.add_parser("recommend", help="Gemma recommendations by tier/task")
    _gr.add_argument("--tier", choices=["laptop", "desktop", "workstation", "server"])
    _gr.add_argument("--task")
    _gr.add_argument("--json", action="store_true")
    _gc = g_sub.add_parser("scorecards", help="Recorded Gemma scorecards")
    _gc.add_argument("--json", action="store_true")
    _gp = g_sub.add_parser("promote", help="Owner-gated route-promotion proposal")
    _gp.add_argument("--task-class", dest="task_class")
    _gp.add_argument("--dry-run", dest="dry_run", action="store_true")
    _gp.add_argument("--json", action="store_true")
    p_gemma.set_defaults(func=_cmd_gemma)

    p_presence = sub.add_parser(
        "presence",
        help="Companion presence state + task animation plan (policy only)",
        description=(
            "Compute the JARVIS Prime living-companion presence state from "
            "signals and, with --mission, a task animation plan. This is "
            "policy/state only — no camera, microphone, overlay, or device "
            "control is performed. Real device actions stay behind Android "
            "permissions and owner gates."
        ),
    )
    p_presence.add_argument(
        "--mission", help="Build a task animation plan for this mission"
    )
    p_presence.add_argument("--target-app", dest="target_app")
    p_presence.add_argument(
        "--next-screen",
        dest="next_screen",
        action="store_true",
        help="Target app is on the next screen (adds a page-turn step)",
    )
    p_presence.add_argument(
        "--real-action",
        dest="real_action",
        action="store_true",
        help="Request a real device action (forces an owner gate)",
    )
    p_presence.add_argument("--offline", action="store_true", help="Gateway offline")
    p_presence.add_argument(
        "--emergency-stop", dest="emergency_stop", action="store_true"
    )
    p_presence.add_argument(
        "--listening", action="store_true", help="Microphone is active"
    )
    p_presence.add_argument("--thinking", action="store_true")
    p_presence.add_argument("--working", action="store_true")
    p_presence.add_argument(
        "--attention-opt-in",
        dest="attention_opt_in",
        action="store_true",
        help="Camera attention detection is opted in",
    )
    p_presence.add_argument(
        "--attention-confidence",
        dest="attention_confidence",
        type=float,
        default=0.0,
    )
    p_presence.add_argument(
        "--attention-threshold",
        dest="attention_threshold",
        type=float,
        default=0.72,
    )
    p_presence.add_argument(
        "--pending-approval", dest="pending_approval", action="store_true"
    )
    p_presence.add_argument("--blocked-reason", dest="blocked_reason")
    p_presence.add_argument("--json", action="store_true")
    p_presence.set_defaults(func=_cmd_presence)

    p_packet = sub.add_parser(
        "packet",
        help="Turn a plain-English request into a bounded coding work packet",
        description=(
            "Classify a natural-language request into a bounded work packet "
            "(intent, branch, risk class, allowed files, acceptance + "
            "verification plan, builder/reviewer split, owner gates). "
            "Describes scope only — it does not execute anything."
        ),
    )
    p_packet.add_argument("prompt", help="Plain-English request")
    p_packet.add_argument(
        "--branch-prefix",
        dest="branch_prefix",
        default="jarvis",
        help="Prefix for the suggested branch name (default: jarvis)",
    )
    p_packet.add_argument(
        "--markdown", action="store_true", help="Render the packet as Markdown"
    )
    p_packet.add_argument(
        "--validate",
        action="store_true",
        help="Validate packet structure and print findings",
    )
    p_packet.add_argument(
        "--gate-check",
        dest="gate_check",
        action="store_true",
        help="Run the verification-gate summary over the packet",
    )
    p_packet.add_argument("--json", action="store_true")
    p_packet.set_defaults(func=_cmd_packet)

    # `packetize` is an alias of `packet` with the same handler/flags.
    p_packetize = sub.add_parser(
        "packetize",
        help="Alias of `packet`: bound a plain-English request into a work packet",
    )
    p_packetize.add_argument("prompt", help="Plain-English request")
    p_packetize.add_argument("--branch-prefix", dest="branch_prefix", default="jarvis")
    p_packetize.add_argument("--markdown", action="store_true")
    p_packetize.add_argument("--validate", action="store_true")
    p_packetize.add_argument("--gate-check", dest="gate_check", action="store_true")
    p_packetize.add_argument("--json", action="store_true")
    p_packetize.set_defaults(func=_cmd_packet)

    p_memtree = sub.add_parser(
        "memory-tree",
        help="Group source-backed notes by namespace/topic (in-memory only)",
        description=(
            "Build an in-memory Memory Tree from --add entries and either "
            "search it (--search) or print its outline. Stateless per "
            "invocation: no durable recall and no external services."
        ),
    )
    # Optional persistent-store verb. Without it, the legacy --add/--search
    # in-memory behavior runs (kept for backward compatibility).
    p_memtree.add_argument(
        "op",
        nargs="?",
        choices=["add", "search", "outline", "export-markdown"],
        help="Persistent Memory OS operation (durable JSONL store). "
        "Omit to use the stateless --add/--search form.",
    )
    p_memtree.add_argument(
        "arg",
        nargs="?",
        help="For `add`: 'namespace::title::text'. For `search`: the query.",
    )
    p_memtree.add_argument(
        "--add",
        action="append",
        metavar="NS::TITLE::TEXT",
        help="Add a note 'namespace::title::text'. Repeatable. (stateless form)",
    )
    p_memtree.add_argument("--search", help="Search query (default: print the outline)")
    p_memtree.add_argument("--namespace", help="Restrict the search to one namespace")
    p_memtree.add_argument("--limit", type=int, default=5)
    p_memtree.add_argument(
        "--store", help="Path to a persistent memory-tree JSONL file"
    )
    p_memtree.add_argument("--layer", choices=["working", "session", "durable"])
    p_memtree.add_argument("--source", help="Source URI/path for a durable add")
    p_memtree.add_argument(
        "--trust",
        choices=[
            "owner",
            "primary",
            "official_doc",
            "reputable",
            "community",
            "unverified",
        ],
    )
    p_memtree.add_argument("--confidence", type=float, default=0.5)
    p_memtree.add_argument(
        "--owner-approved", dest="owner_approved", action="store_true"
    )
    p_memtree.add_argument(
        "--contested", action="store_true", help="Include contested nodes"
    )
    p_memtree.add_argument("--json", action="store_true")
    p_memtree.set_defaults(func=_cmd_memory_tree)

    # research — Research Vault operations.
    p_research = sub.add_parser(
        "research", help="Research Vault: add/list/export source-cited artifacts"
    )
    p_research.add_argument("op", choices=["add", "list", "export-markdown"])
    p_research.add_argument("--title", default="")
    p_research.add_argument("--uri", default="")
    p_research.add_argument(
        "--source-type",
        dest="source_type",
        default="manual",
        choices=[
            "paper",
            "official_doc",
            "blog",
            "repo",
            "course",
            "benchmark",
            "oss_practice",
            "manual",
        ],
    )
    p_research.add_argument(
        "--strength",
        default="moderate",
        choices=["primary", "strong", "moderate", "weak", "vendor_reported"],
    )
    p_research.add_argument("--excerpt", default="")
    p_research.add_argument(
        "--store", help="Path to a persistent research-vault JSONL file"
    )
    p_research.add_argument("--json", action="store_true")
    p_research.set_defaults(func=_cmd_research)

    # graph — GraphRAG knowledge-graph: build / query / related.
    p_graph = sub.add_parser(
        "graph",
        help="GraphRAG knowledge graph: build, query (local/global/coding), related",
        description=(
            "Build and query a typed, source-backed knowledge graph over the "
            "cognition plane (repo code, docs, Research Vault, Memory Tree, job "
            "and decision ledgers). Supplements — never replaces — existing RAG "
            "and memory. The graph is an additive cache; deleting it is a full "
            "rollback."
        ),
    )
    p_graph.add_argument("op", choices=["build", "query", "related"])
    p_graph.add_argument(
        "query", nargs="?", default="", help="Question (for the query op)"
    )
    p_graph.add_argument(
        "--mode",
        choices=["local", "global", "coding"],
        default="local",
        help="Query mode: nearest nodes / community summary / coding context",
    )
    p_graph.add_argument(
        "--node", help="Node id or key to fetch related items for (related op)"
    )
    p_graph.add_argument(
        "--indexers",
        help="Comma-separated subset of: code,docs,evidence,memory,ledger",
    )
    p_graph.add_argument("--repo-root", dest="repo_root", default=".")
    p_graph.add_argument("--store", help="Path to a persistent graph JSON file")
    p_graph.add_argument("--json", action="store_true")
    p_graph.set_defaults(func=_cmd_graph)

    # model-scorecard — evidence-backed model routing records.
    p_score = sub.add_parser(
        "model-scorecard",
        help="Record/list/recommend model scorecards; emit local endpoint",
    )
    p_score.add_argument("op", choices=["add", "list", "recommend", "local-endpoint"])
    p_score.add_argument("--model", default="")
    p_score.add_argument("--provider", default="unknown")
    p_score.add_argument("--task", default="coding")
    p_score.add_argument("--risk-class", dest="risk_class", default="RC1")
    p_score.add_argument("--tests-passed", dest="tests_passed", type=int, default=0)
    p_score.add_argument("--tests-failed", dest="tests_failed", type=int, default=0)
    p_score.add_argument(
        "--owner-corrections", dest="owner_corrections", type=int, default=0
    )
    p_score.add_argument(
        "--hallucination-corrections",
        dest="hallucination_corrections",
        type=int,
        default=0,
    )
    p_score.add_argument("--accepted-diff-rate", dest="accepted_diff_rate", type=float)
    p_score.add_argument(
        "--context-length", dest="context_length", type=int, default=0,
        help="Max context window the model offers (tokens)",
    )
    p_score.add_argument(
        "--tool-reliability", dest="tool_reliability", type=float,
        help="Measured tool-call reliability [0..1]",
    )
    p_score.add_argument(
        "--citation-accuracy", dest="citation_accuracy", type=float,
        help="Measured citation accuracy [0..1]",
    )
    p_score.add_argument(
        "--mobile-ux-suitability", dest="mobile_ux_suitability", type=float,
        help="Measured suitability for the mobile cockpit [0..1]",
    )
    p_score.add_argument(
        "--task-class", dest="task_class",
        help="Task class to weight the 'recommend' ranking by (defaults to --task)",
    )
    p_score.add_argument("--endpoint", default="http://localhost:8000/v1")
    p_score.add_argument("--server", default="vllm")
    p_score.add_argument("--store", help="Path to a persistent scorecard JSONL file")
    p_score.add_argument("--json", action="store_true")
    p_score.set_defaults(func=_cmd_model_scorecard)

    p_route = sub.add_parser(
        "route",
        help="Explain the evidence-backed model route for a task class",
    )
    p_route.add_argument(
        "--task",
        help="Task class (e.g. coding_build); omit to show all task classes",
    )
    p_route.add_argument("--json", action="store_true")
    p_route.set_defaults(func=_cmd_route)

    # owner-brief — daily owner brief from a monitor context.
    p_brief = sub.add_parser(
        "owner-brief",
        help="Render the daily owner brief from a monitor context (read-only)",
    )
    p_brief.add_argument("--context", help="Path to a JSON monitor-context file")
    p_brief.add_argument(
        "--auto",
        action="store_true",
        help="Assemble live local state (git, memory contradictions, scorecards, proposals)",
    )
    p_brief.add_argument("--repo-root", dest="repo_root", default=".")
    p_brief.add_argument(
        "--memory-store", dest="memory_store", help="Memory Tree JSONL path"
    )
    p_brief.add_argument(
        "--scorecard-store", dest="scorecard_store", help="Scorecard JSONL path"
    )
    p_brief.add_argument("--proposals", help="Proposals JSONL path")
    p_brief.add_argument("--json", action="store_true")
    p_brief.set_defaults(func=_cmd_owner_brief)

    def _add_bootstrap_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--free-first", dest="free_first", action="store_true", default=True
        )
        p.add_argument("--no-free-first", dest="free_first", action="store_false")
        p.add_argument("--jarvis", dest="jarvis", action="store_true", default=True)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--no-pull", action="store_true")
        p.add_argument("--force", action="store_true")
        p.add_argument("--local-only", dest="local_only", action="store_true")
        p.add_argument("--json", action="store_true")

    p_bootstrap = sub.add_parser(
        "bootstrap",
        help="Free-first model bootstrap (local OSS first; paid opt-in only)",
        description=(
            "Detect local runtimes, configured hosted OSS providers, and the "
            "official Claude Code / Codex worker CLIs, then write the JARVIS "
            "free-first model routing policy. No API keys are requested or "
            "stored; paid APIs are explicit opt-in only."
        ),
    )
    _add_bootstrap_flags(p_bootstrap)
    p_bootstrap.set_defaults(func=_cmd_bootstrap)

    p_launch = sub.add_parser(
        "launch",
        help="Run the free-first JARVIS Prime launch path",
        description=(
            "Runtime check → model bootstrap → memory init → owner gate → "
            "emergency stop → slash commands → worker detection → launch "
            "doctor, then print the next commands."
        ),
    )
    _add_bootstrap_flags(p_launch)
    p_launch.set_defaults(func=_cmd_launch)

    p_launch_doctor = sub.add_parser(
        "launch-doctor",
        help="Verify free-first JARVIS launch readiness",
        description=(
            "Run the launch-readiness checks (runtime, owner gate, emergency "
            "stop, model brain, model policy, local runtimes, worker lanes, "
            "installer, Termux compatibility). Exits nonzero only on a hard "
            "launch blocker."
        ),
    )
    p_launch_doctor.add_argument("--json", action="store_true")
    p_launch_doctor.set_defaults(func=_cmd_launch_doctor)

    # navigate — localize an objective to candidate edit sites (the same
    # HyperAgent-style navigation a /orchestrate job runs before dispatch).
    p_navigate = sub.add_parser(
        "navigate",
        help="Localize an objective to candidate edit sites (read-only)",
        description=(
            "Run the deterministic HyperAgent-style repo navigator: rank the "
            "files most likely to need editing for an objective, with the tests "
            "to run. Read-only; no LLM is used for localization."
        ),
    )
    p_navigate.add_argument("issue", help="The objective / issue to localize")
    p_navigate.add_argument("--repo", default=".", help="Repo root (default: cwd)")
    p_navigate.add_argument("--limit", type=int, default=5, help="Max candidate sites")
    p_navigate.add_argument("--json", action="store_true")
    p_navigate.set_defaults(func=_cmd_navigate)

    # compile — natural-language programming front-end: English -> typed intent
    # graph -> work packet or automation-flow DSL. Deterministic, no execution.
    p_compile = sub.add_parser(
        "compile",
        help="Compile plain English into a work packet or automation flow",
        description=(
            "Parse a plain-English request into a typed semantic intent graph, "
            "deterministically select a backend (repo work packet or automation "
            "flow), and emit a gate-compatible artifact. Surfaces clarifying "
            "questions instead of guessing; never executes."
        ),
    )
    p_compile.add_argument("prompt", help="The plain-English request")
    p_compile.add_argument(
        "--backend",
        choices=["auto", "work-packet", "workflow", "automation"],
        default="auto",
        help="Force a backend target (default: auto-select)",
    )
    p_compile.add_argument("--branch-prefix", dest="branch_prefix", default="jarvis")
    p_compile.add_argument(
        "--gate-check", dest="gate_check", action="store_true",
        help="Run the verification gate summary over a compiled work packet",
    )
    p_compile.add_argument(
        "--explain", action="store_true", help="Show backend selection scores"
    )
    p_compile.add_argument(
        "--learn", action="store_true",
        help="Propose parsed vocabulary to the Memory Tree (owner-review, never durable)",
    )
    p_compile.add_argument("--json", action="store_true")
    p_compile.set_defaults(func=_cmd_compile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
