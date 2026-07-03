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
  muse self-update proposals. ``approve`` requires the exact
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
- ``context "<request>" [--task-class coding_build] [--build] [--json]``
  — build a local-first GraphRAG context handoff (architecture summary,
  relevant files/tests, GraphRAG nodes, prior decisions, model-lane
  recommendation, verification plan) instead of a whole-repo dump.
  Network-free; degrades gracefully if the graph isn't built.
- ``data-sources {list|clusters|show|register-vault}`` — browse the open
  data-source registry (``docs/ai-intelligence/open-data-sources.yaml``) and
  bridge sources into the Research Vault. Read-only except ``register-vault``.
- ``persona-corpus {list|search|register-vault}`` — the Breadstick Ricky voice
  corpus (``docs/persona/ricky-and-the-boss/transcripts/``): list/search
  transcripts and bridge them into the Research Vault so muse can quote/riff on
  specific bits. Read-only except ``register-vault``.
- ``architecture {list|show}`` — inspect the machine-readable M.U.S.E
  component registry (``docs/architecture/muse-component-registry.yaml``):
  list components by ``--kind``/``--risk``/``--owner-gated`` or show one by id,
  with ``--json``. Read-only.
- ``toggles {list|show|status|doctor}`` — the opt-in / owner-gated
  environment-toggle registry (``docs/architecture/muse-toggle-registry.yaml``).
  ``list`` the catalog (``--group``/``--owner-gated``), ``show`` one by env
  name, ``status`` resolves each against the live environment, and ``doctor``
  verifies every toggle is actually wired (read_sites exist and mention the env
  var). Read-only.
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
from hermes_cli.jarvis_prime.cli_route import add_route_parser
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
    elif fmt == "parquet":
        from hermes_cli.jarvis_prime.learning_analytics import export_parquet
        try:
            n = export_parquet(store, out)
        except Exception as exc:
            print(f"parquet export failed: {exc}", file=sys.stderr)
            return 1
    else:  # pragma: no cover - argparse choices guard this
        print(f"unknown format: {fmt}", file=sys.stderr)
        return 2
    print(f"exported {n} record(s) ({fmt}) -> {out}")
    return 0


def _cmd_learning_query(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.learning_analytics import query_dataset

    try:
        rows = query_dataset(args.sql, args.parquet)
    except Exception as exc:
        print(f"query failed: {exc}", file=sys.stderr)
        return 1
    _print_json(rows)
    return 0


def _holographic_store():
    """Open the holographic memory store at its configured (profile-aware) path.

    Resolves ``plugins.hermes-memory-store.db_path`` the same way the plugin
    does, so the CLI operates on the live store. Returns None when the plugin
    isn't importable (e.g. minimal install).
    """
    try:
        from hermes_constants import get_hermes_home
        from plugins.memory.holographic import _load_plugin_config
        from plugins.memory.holographic.store import MemoryStore
    except Exception as exc:  # pragma: no cover - minimal install
        print(f"holographic memory store unavailable: {exc}", file=sys.stderr)
        return None

    cfg = _load_plugin_config()
    home = str(get_hermes_home())
    db_path = cfg.get("db_path", home + "/memory_store.db")
    if isinstance(db_path, str):
        db_path = db_path.replace("$HERMES_HOME", home).replace("${HERMES_HOME}", home)
    return MemoryStore(db_path=db_path)


def _cmd_memory_consolidate(args: argparse.Namespace) -> int:
    store = _holographic_store()
    if store is None:
        return 1
    from plugins.memory.holographic.consolidation import consolidate

    try:
        report = consolidate(store, dry_run=not args.apply)
    finally:
        store.close()
    data = report.to_dict()
    if getattr(args, "json", False):
        _print_json(data)
        return 0
    mode = "APPLIED" if args.apply else "dry-run (use --apply to write)"
    s = data["summary"]
    print(f"consolidation {mode}: {data['total']} fact(s) scanned")
    print(
        f"  merged={s['merged']}  contradictions={s['contradictions']}  "
        f"promoted={s['promoted']}  forgotten={s['forgotten']}"
    )
    for m in data["merged"]:
        print(f"  merge {m['drop']} -> {m['keep']} (sim {m['similarity']})")
    for p in data["promoted"]:
        print(f"  promote {p['fact_id']} (short->long, {p['reason']})")
    for fgt in data["forgotten"]:
        print(f"  forget {fgt['fact_id']}: {fgt['content']}")
    return 0


def _cmd_memory_stats(args: argparse.Namespace) -> int:
    store = _holographic_store()
    if store is None:
        return 1
    try:
        facts = store.all_facts_for_consolidation()
    finally:
        store.close()
    tiers: dict[str, int] = {}
    cats: dict[str, int] = {}
    imp_buckets = {"low(<0.34)": 0, "mid": 0, "high(>=0.67)": 0}
    accessed = 0
    for f in facts:
        tiers[f.get("memory_tier") or "short"] = tiers.get(f.get("memory_tier") or "short", 0) + 1
        cats[f.get("category") or "general"] = cats.get(f.get("category") or "general", 0) + 1
        imp = f.get("importance")
        imp = 0.5 if imp is None else float(imp)
        if imp < 0.34:
            imp_buckets["low(<0.34)"] += 1
        elif imp >= 0.67:
            imp_buckets["high(>=0.67)"] += 1
        else:
            imp_buckets["mid"] += 1
        if (f.get("retrieval_count") or 0) > 0:
            accessed += 1
    data = {
        "total": len(facts),
        "tiers": tiers,
        "categories": cats,
        "importance": imp_buckets,
        "ever_accessed": accessed,
    }
    if getattr(args, "json", False):
        _print_json(data)
        return 0
    print(f"memory: {data['total']} fact(s)")
    print(f"  tiers: {tiers}")
    print(f"  importance: {imp_buckets}")
    print(f"  ever recalled: {accessed}")
    return 0


def _memory_sources_config() -> dict:
    """Read jarvis_prime.memory_sources config from config.yaml (per-source gates)."""
    try:
        from hermes_constants import get_hermes_home
        from hermes_cli.config import cfg_get
        import yaml

        path = get_hermes_home() / "config.yaml"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8-sig") as f:
            all_cfg = yaml.safe_load(f) or {}
        return cfg_get(all_cfg, "jarvis_prime", "memory_sources", default={}) or {}
    except Exception:
        return {}


def _cmd_memory_sources(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.memory_sources import REGISTRY, source_enabled

    cfg = _memory_sources_config()
    rows = []
    for name in sorted(REGISTRY):
        p = REGISTRY[name]
        rows.append({
            "source": name,
            "tool": p.tool,
            "sensitivity": p.sensitivity,
            "trust": p.trust,
            "enabled": source_enabled(name, cfg),
        })
    if getattr(args, "json", False):
        _print_json(rows)
        return 0
    print("memory sources (enable under jarvis_prime.memory_sources.<name>.enabled):")
    for r in rows:
        flag = "on " if r["enabled"] else "off"
        print(f"  [{flag}] {r['source']:8s} tool={r['tool']:24s} "
              f"sensitivity={r['sensitivity']:8s} trust={r['trust']}")
    return 0


def _cmd_memory_ingest(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.memory_sources import ingest

    cfg = _memory_sources_config()
    store = None
    if args.apply:
        # Owner gate: writing external data into memory is irreversible-ish and
        # may touch personal sources — require the exact authorization phrase.
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE
        import os

        phrase = args.phrase or os.environ.get("JARVIS_OWNER_PHRASE", "")
        if phrase.strip() != AUTHORIZATION_PHRASE:
            print(
                f"owner authorization required to write — reply exactly: "
                f"{AUTHORIZATION_PHRASE!r} (via --phrase or JARVIS_OWNER_PHRASE)",
                file=sys.stderr,
            )
            return 3
        store = _holographic_store()
        if store is None:
            return 1

    try:
        report = ingest(
            args.source, args.query, limit=args.limit, apply=args.apply,
            config=cfg, store=store,
        )
    finally:
        if store is not None:
            store.close()

    data = report.to_dict()
    if getattr(args, "json", False):
        _print_json(data)
        return 0 if not data["errors"] else 1
    mode = "WROTE" if args.apply else "dry-run (use --apply with owner phrase to write)"
    print(f"ingest {args.source!r} q={args.query!r}: fetched {data['fetched']}, {mode}")
    for c in data["candidates"]:
        print(f"  - [{c['importance']}] {c['title']}  <{c['source_uri']}>")
    if args.apply:
        print(f"  written: {data['written']}")
    for e in data["errors"]:
        print(f"  error: {e}", file=sys.stderr)
    return 0 if not data["errors"] else 1


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


def _cmd_learning_free_recipe(args: argparse.Namespace) -> int:
    """Emit a runnable free Unsloth+TRL training recipe (no paid API)."""

    from hermes_cli.jarvis_prime.free_training import (
        TrainingStage,
        generate_recipe,
    )

    recipe = generate_recipe(
        args.dataset,
        stage=TrainingStage(args.stage),
        base_model=args.base_model,
        out_dir=args.out_dir,
    )
    if getattr(args, "write", None):
        path = recipe.write(args.write)
        # Keep stdout pure JSON in --json mode so automation can parse it.
        print(f"wrote {path}", file=sys.stderr if args.json else sys.stdout)
    if args.json:
        _print_json(recipe.to_dict())
    else:
        print(f"# free {recipe.stage.value} recipe ({recipe.base_model}) — "
              f"valid_python={recipe.valid_python()}, paid_api=False")
        print(recipe.script)
    return 0


def _cmd_learning_free_plan(args: argparse.Namespace) -> int:
    """Describe the free, continuous, gated self-improvement loop."""

    from hermes_cli.jarvis_prime.free_training import FreeContinuousPlan

    plan = FreeContinuousPlan(base_model=args.base_model)
    if args.json:
        _print_json(plan.to_dict())
        return 0
    print("Free continuous gated training loop:")
    print(f"  base model : {plan.base_model}")
    print(f"  stages     : {' -> '.join(plan.stages)}")
    print(f"  reward     : {plan.reward}")
    print(f"  eval set   : {plan.eval_set}")
    print(f"  promotion  : {plan.promotion}")
    print(f"  compute    : {', '.join(plan.compute)} (paid_api=False)")
    return 0


def _cmd_learning_free_loop(args: argparse.Namespace) -> int:
    """Run one harvest → export → recipe pass of the free, gated loop."""

    from hermes_cli.jarvis_prime.free_training import TrainingStage, run_free_loop

    if getattr(args, "stages", None):
        stages = tuple(TrainingStage(s) for s in args.stages)
    else:
        from hermes_cli.jarvis_prime.free_training import DEFAULT_LOOP_STAGES

        stages = DEFAULT_LOOP_STAGES

    report = run_free_loop(
        base_model=args.base_model,
        out_dir=args.out_dir,
        stages=stages,
        min_examples=getattr(args, "min_examples", 1),
        write_dir=getattr(args, "write", None),
    )
    if args.json:
        _print_json(report.to_dict())
        return 0
    print("Free continuous gated loop — one pass:")
    print(f"  harvested  : {report.harvested} owner-approved trace(s)")
    print(f"  ready      : {report.ready}")
    print(f"  dataset    : {report.dataset_path}")
    if report.preference_dataset_path:
        print(f"  preference : {report.preference_dataset_path} "
              f"({report.preference_pairs} pair(s)) — for orpo/dpo")
    print(f"  recipes    : {', '.join(r.stage.value for r in report.recipes)} "
          f"(base {report.plan.base_model}, paid_api=False)")
    if report.written_to:
        print(f"  written to : {report.written_to}")
    for note in report.notes:
        print(f"  - {note}")
    return 0


def _cmd_learning_promote(args: argparse.Namespace) -> int:
    """Assess measure-gated promotion via model_scorecard.promotion_eligible."""

    from hermes_cli.jarvis_prime.model_scorecard import (
        DEFAULT_PROMOTION_MIN_MEAN_DELTA,
        DEFAULT_PROMOTION_MIN_SAMPLES,
        ScorecardBook,
        promotion_eligible,
    )

    book = ScorecardBook.load()
    min_samples: int = (
        args.min_samples
        if getattr(args, "min_samples", None) is not None
        else DEFAULT_PROMOTION_MIN_SAMPLES
    )
    min_mean_delta: float = (
        args.min_mean_delta
        if getattr(args, "min_mean_delta", None) is not None
        else DEFAULT_PROMOTION_MIN_MEAN_DELTA
    )
    assessment = promotion_eligible(
        book,
        task_class=args.task_class,
        candidate=args.candidate,
        baseline=getattr(args, "baseline", None),
        min_samples=min_samples,
        min_mean_delta=min_mean_delta,
    )
    if args.json:
        _print_json(assessment.to_dict())
    else:
        print(assessment.rationale())
    return 0 if assessment.eligible else 1


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
    if getattr(args, "cluster", None):
        sources = [s for s in sources if s.cluster == args.cluster]
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
            f"{s.rank:>2}  {s.key:<26}  {s.cluster:<22}  {s.role.value:<5}  "
            f"{s.evidence_strength.value:<10}  {s.name} {tag}".rstrip()
        )
    return 0


def _cmd_data_sources_clusters(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.open_data_sources import (
        by_cluster,
        load_clusters,
    )

    sources = _data_sources_pool(args)
    clusters = load_clusters(getattr(args, "registry", None) or None)
    if getattr(args, "json", False):
        payload = []
        for c in clusters:
            members = by_cluster(c.id, sources=sources)
            d = c.to_dict()
            d["num_sources"] = len(members)
            d["num_core_ingest"] = sum(1 for s in members if s.core_ingest)
            payload.append(d)
        _print_json(payload)
        return 0
    for c in clusters:
        members = by_cluster(c.id, sources=sources)
        core = sum(1 for s in members if s.core_ingest)
        print(f"{c.id:<24} {len(members):>2} sources ({core} core)  {c.title}")
        if c.model_task_classes:
            print("    task-classes: " + ", ".join(c.model_task_classes))
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


# --- persona voice corpus (Breadstick Ricky) --------------------------------


def _cmd_persona_corpus_list(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.persona_corpus import load_corpus

    corpus_dir = Path(args.corpus_dir) if getattr(args, "corpus_dir", None) else None
    transcripts = load_corpus(corpus_dir)
    if getattr(args, "json", False):
        _print_json(
            [
                {
                    "video_id": t.video_id,
                    "title": t.title,
                    "url": t.url,
                    "characters": list(t.characters),
                    "themes": list(t.themes),
                    "words": t.word_count,
                }
                for t in transcripts
            ]
        )
        return 0
    print(f"{len(transcripts)} transcript(s) in the persona corpus")
    for t in transcripts:
        who = ", ".join(t.characters) or "ensemble"
        print(f"  {t.video_id}  {t.title[:60]}  [{who}]")
    return 0


def _cmd_persona_corpus_search(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.persona_corpus import search_corpus

    corpus_dir = Path(args.corpus_dir) if getattr(args, "corpus_dir", None) else None
    hits = search_corpus(args.query, corpus_dir=corpus_dir, limit=args.limit)
    if getattr(args, "json", False):
        _print_json(
            [
                {
                    "title": a.title,
                    "video_id": a.citation_anchors[0] if a.citation_anchors else "",
                    "url": a.source_uri,
                    "tags": list(a.tags),
                }
                for a in hits
            ]
        )
        return 0
    if not hits:
        print(f"no persona-corpus matches for {args.query!r}")
        return 0
    print(f"top {len(hits)} match(es) for {args.query!r}:")
    for a in hits:
        vid = a.citation_anchors[0] if a.citation_anchors else "?"
        print(f"  {vid}  {a.title[:60]}")
        print(f"    {a.source_uri}")
    return 0


def _cmd_persona_corpus_register_vault(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.persona_corpus import register_all_in_vault
    from hermes_cli.jarvis_prime.research_vault import ResearchVault

    corpus_dir = Path(args.corpus_dir) if getattr(args, "corpus_dir", None) else None
    dry_run = getattr(args, "dry_run", False)
    vault_path = Path(args.store) if getattr(args, "store", None) else None
    vault = ResearchVault.load(vault_path)
    result = register_all_in_vault(vault, corpus_dir=corpus_dir, persist=not dry_run)
    if getattr(args, "json", False):
        _print_json(
            {
                "dry_run": dry_run,
                "registered": [a.id for a in result.registered],
                "skipped": [{"video_id": k, "reason": r} for k, r in result.skipped],
                "vault": str(vault._resolve_path()),
            }
        )
        return 0
    verb = "would register" if dry_run else "registered"
    print(f"{verb} {result.count} transcript(s) into the Research Vault")
    for vid, reason in result.skipped:
        print(f"  skipped {vid}: {reason}")
    if not dry_run:
        print(f"  vault: {vault._resolve_path()}")
    return 0


# --- NVIDIA deep learning software registry --------------------------------


def _nvidia_dl_software_pool(args: argparse.Namespace):
    """Resolve the NVIDIA registry, honoring an optional --registry override."""
    from hermes_cli.jarvis_prime.nvidia_dl_software import load_registry

    path = Path(args.registry) if getattr(args, "registry", None) else None
    return load_registry(path)


def _cmd_nvidia_dl_software_list(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.nvidia_dl_software import ToolCategory

    tools = _nvidia_dl_software_pool(args)
    if getattr(args, "section", None):
        tools = [t for t in tools if t.section == args.section]
    if getattr(args, "category", None):
        want = ToolCategory(args.category)
        tools = [t for t in tools if t.category == want]

    if getattr(args, "json", False):
        _print_json([t.to_dict() for t in tools])
        return 0
    if not tools:
        print("no matching tools")
        return 0
    for t in tools:
        gpu = "[gpu]" if t.requires_gpu else ""
        print(
            f"{t.rank:>2}  {t.key:<28}  {t.category.value:<22}  "
            f"{t.license:<12}  {t.name} {gpu}".rstrip()
        )
    return 0


def _cmd_nvidia_dl_software_show(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.nvidia_dl_software import get

    tool = get(args.key, tools=_nvidia_dl_software_pool(args))
    if tool is None:
        print(f"unknown nvidia-dl-software tool: {args.key!r}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        _print_json(tool.to_dict())
        return 0
    d = tool.to_dict()
    for label in (
        "name",
        "rank",
        "section",
        "category",
        "interfaces",
        "requires_gpu",
        "license",
        "purpose",
        "capabilities",
        "official_uri",
        "source_uris",
        "license_notes",
        "evidence_strength",
    ):
        print(f"{label:>18}: {d[label]}")
    return 0


def _cmd_nvidia_dl_software_register_vault(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.nvidia_dl_software import register_all_in_vault
    from hermes_cli.jarvis_prime.research_vault import ResearchVault

    tools = _nvidia_dl_software_pool(args)
    dry_run = getattr(args, "dry_run", False)
    vault_path = Path(args.store) if getattr(args, "store", None) else None
    vault = ResearchVault.load(vault_path)
    result = register_all_in_vault(vault, tools=tools, persist=not dry_run)
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
    print(f"{verb} {len(result.registered)} NVIDIA tool(s) into the Research Vault")
    for key, reason in result.skipped:
        print(f"  skipped {key}: {reason}")
    if not dry_run:
        print(f"  vault: {vault._resolve_path()}")
    return 0


# --- component architecture registry ---------------------------------------


def _architecture_pool(args: argparse.Namespace):
    """Resolve the component registry, honoring an optional --registry override."""
    from hermes_cli.jarvis_prime.component_registry import load_registry

    path = Path(args.registry) if getattr(args, "registry", None) else None
    return load_registry(path)


def _cmd_architecture_list(args: argparse.Namespace) -> int:
    components = _architecture_pool(args)
    if getattr(args, "kind", None):
        components = [c for c in components if c.kind == args.kind]
    if getattr(args, "risk", None):
        components = [c for c in components if c.risk_class == args.risk]
    if getattr(args, "owner_gated", False):
        components = [c for c in components if c.is_owner_gated]

    if getattr(args, "json", False):
        _print_json([c.to_dict() for c in components])
        return 0
    if not components:
        print("no matching components")
        return 0
    for c in components:
        gate = "GATED" if c.is_owner_gated else ""
        print(
            f"{c.id:<22}  {c.kind:<13}  {c.risk_class:<4}  {gate:<5}  "
            f"{c.name}".rstrip()
        )
    return 0


def _cmd_architecture_show(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.component_registry import get

    comp = get(args.component_id, components=_architecture_pool(args))
    if comp is None:
        print(f"unknown component: {args.component_id!r}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        _print_json(comp.to_dict())
        return 0
    d = comp.to_dict()
    for label in (
        "name",
        "kind",
        "risk_class",
        "owner_module",
        "entrypoints",
        "capabilities",
        "owner_gated_actions",
        "is_owner_gated",
        "tests",
        "rollback",
        "observability",
        "docs",
    ):
        print(f"{label:>20}: {d[label]}")
    return 0


def _toggle_pool(args: argparse.Namespace):
    from hermes_cli.jarvis_prime.toggles import load_toggles

    path = getattr(args, "registry", None)
    return load_toggles(Path(path) if path else None)


def _cmd_toggles_list(args: argparse.Namespace) -> int:
    toggles = _toggle_pool(args)
    if getattr(args, "group", None):
        toggles = [t for t in toggles if t.group == args.group]
    if getattr(args, "owner_gated", False):
        toggles = [t for t in toggles if t.owner_gated]

    if getattr(args, "json", False):
        _print_json([t.to_dict() for t in toggles])
        return 0
    if not toggles:
        print("no matching toggles")
        return 0
    for t in toggles:
        gate = "GATED" if t.owner_gated else ""
        dflt = "on" if t.default else "off"
        print(
            f"{t.env:<34}  {t.group:<3}  {gate:<5}  default={dflt:<3}  "
            f"{t.summary}".rstrip()
        )
    return 0


def _cmd_toggles_show(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.toggles import get

    t = get(args.env, toggles=_toggle_pool(args))
    if t is None:
        print(f"unknown toggle: {args.env!r}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        _print_json(t.to_dict())
        return 0
    d = t.to_dict()
    for label in (
        "env",
        "group",
        "owner_gated",
        "default",
        "summary",
        "read_sites",
        "docs",
    ):
        print(f"{label:>12}: {d[label]}")
    return 0


def _cmd_toggles_status(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.toggles import evaluate_all

    results = evaluate_all()
    if getattr(args, "group", None):
        results = [(t, on) for t, on in results if t.group == args.group]
    if getattr(args, "enabled_only", False):
        results = [(t, on) for t, on in results if on]

    if getattr(args, "json", False):
        _print_json([{**t.to_dict(), "enabled": on} for t, on in results])
        return 0
    for t, on in results:
        state = "ON " if on else "off"
        gate = "GATED" if t.owner_gated else ""
        print(f"[{state}] {t.env:<34}  {t.group:<3}  {gate}".rstrip())
    return 0


def _cmd_toggles_doctor(args: argparse.Namespace) -> int:
    """Verify every declared read_site exists and actually mentions the env."""
    toggles = _toggle_pool(args)
    problems: list[tuple[str, str]] = []
    for t in toggles:
        if not t.read_sites:
            problems.append((t.env, "no read_sites declared"))
            continue
        for rel, path in zip(t.read_sites, t.read_site_paths()):
            if not path.exists():
                problems.append((t.env, f"missing read_site: {rel}"))
            elif t.env not in path.read_text(encoding="utf-8", errors="ignore"):
                problems.append(
                    (t.env, f"read_site does not mention {t.env}: {rel}")
                )

    if getattr(args, "json", False):
        _print_json(
            {
                "ok": not problems,
                "problems": [{"env": e, "detail": d} for e, d in problems],
            }
        )
        return 0 if not problems else 1
    if not problems:
        print(
            f"✓ all {len(toggles)} toggles are wired "
            "(every read_site exists and mentions its env)"
        )
        return 0
    for env_name, detail in problems:
        print(f"✗ {env_name}: {detail}")
    return 1


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

    clarifications: dict[str, str] = {}
    for item in getattr(args, "clarify", None) or []:
        if "=" in item:
            k, v = item.split("=", 1)
            clarifications[k.strip()] = v.strip()

    res = nl_compile.compile_request(
        args.prompt,
        backend=args.backend,
        branch_prefix=args.branch_prefix,
        gate_check=getattr(args, "gate_check", False),
        learn=getattr(args, "learn", False),
        clarifications=clarifications or None,
        rerank=getattr(args, "rerank", False),
        refine_exec=getattr(args, "refine_exec", False),
        refine_run=getattr(args, "refine_run", False),
        grammar_repair=getattr(args, "grammar_repair", False),
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
        else:
            # Language backends (python / rust / sql) carry emitted text.
            d = result.artifact_dict
            valid = getattr(artifact, "validate", lambda: None)()
            if valid is not None:
                print(f"valid: {getattr(valid, 'ok', '?')}")
            if "source" in d:
                print("--- source ---")
                print(d["source"])
            elif "sql" in d:
                print("--- sql ---")
                print(d["sql"])
        for note in result.notes:
            print(f"  note: {note}")

    if res.lane is not None:
        print(f"model lane: {res.lane.lane}  (source: {res.lane.source})")
    if res.grammar is not None:
        print(f"grammar ok: {res.grammar.get('ok')}")
    if res.refinement is not None:
        print(f"refinement ran: {res.refinement.ran}")

    if res.gate_summary is not None:
        print(res.gate_summary.render())

    return 0


def _cmd_flow_exec(args: argparse.Namespace) -> int:
    """Execute an automation flow — simulate by default; real execution gated."""

    from hermes_cli.jarvis_prime import nl_compile
    from hermes_cli.jarvis_prime.ir_compilers.automation_flow import AutomationFlow
    from hermes_cli.jarvis_prime.nlp_flow_exec import FlowExecutor
    from hermes_cli.jarvis_prime.owner_auth import (
        AUTHORIZATION_PHRASE,
        authorize_challenge,
        create_challenge,
    )

    # Obtain a flow: from a JSON file, or by compiling a prompt.
    if getattr(args, "flow_file", None):
        try:
            flow = AutomationFlow.from_dict(
                json.loads(Path(args.flow_file).read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"error: could not load flow file: {exc}", file=sys.stderr)
            return 2
    else:
        res = nl_compile.compile_request(args.prompt or "", backend="automation")
        if res.needs_clarification:
            print("Clarifying questions before I can build a flow:")
            for q in res.clarifying_questions():
                print(f"  - {q}")
            return 2
        artifact = res.compile_result.artifact if res.compile_result else None
        if not isinstance(artifact, AutomationFlow):
            print("error: prompt did not compile to an automation flow",
                  file=sys.stderr)
            return 2
        flow = artifact

    grant = None
    mode = "execute" if getattr(args, "execute", False) else "simulate"
    if mode == "execute":
        phrase = (getattr(args, "authorize", None) or "").strip()
        gated = tuple(flow.owner_gated_actions)
        if not gated:
            pass  # nothing gated; execute freely
        elif phrase != AUTHORIZATION_PHRASE:
            if not args.json:
                print("execute refused: pass --authorize with the exact phrase "
                      f'"{AUTHORIZATION_PHRASE}"')
            # fall through to executor which will refuse without a grant
        elif len(gated) == 1:
            ch = create_challenge(gated[0], rationale="cli flow-exec")
            grant = authorize_challenge(ch, ch.required_phrase)
        else:
            if not args.json:
                print("execute refused: multiple owner-gated actions require "
                      "per-action authorization via the API; running simulate.")
            mode = "simulate"

    run = FlowExecutor().run(flow, mode=mode, grant=grant)
    if args.json:
        _print_json(run.to_dict())
        return 0 if run.executed or mode == "simulate" else 1
    print(f"flow: {flow.name}  mode={mode}  executed={run.executed}")
    for sr in run.steps:
        print(f"  [{sr.step_id}] {sr.op}: performed={sr.performed} ({sr.detail})")
    for line in run.log:
        print(f"  log: {line}")
    return 0


def _cmd_learning_export_finetune(args: argparse.Namespace) -> int:
    """Compile a prompt and export the trace into the learning dataset (PENDING)."""

    from hermes_cli.jarvis_prime import nl_compile
    from hermes_cli.jarvis_prime.nlp_training import export_compile_trace

    res = nl_compile.compile_request(args.prompt, gate_check=True)
    if res.needs_clarification or res.compile_result is None:
        print("error: prompt needs clarification or did not compile",
              file=sys.stderr)
        return 2
    try:
        cand = export_compile_trace(
            res.compile_result, res.parse, res.gate_summary,
            owner_approve=getattr(args, "approve", False),
        )
    except Exception as exc:  # RejectedTrace etc.
        print(f"trace rejected: {exc}")
        return 1
    if args.json:
        _print_json({"candidate_id": cand.id, "status": str(cand.status)})
    else:
        print(f"exported candidate {cand.id} — status {cand.status}")
    return 0


def _cmd_learning_prepare_job(args: argparse.Namespace) -> int:
    """Prepare (dry-run) a fine-tune job spec from owner-approved examples."""

    from hermes_cli.jarvis_prime.nlp_training import prepare_finetune_job

    spec = prepare_finetune_job(
        base_model=args.base_model,
        out_dir=args.out_dir,
        method=getattr(args, "method", "lora"),
        min_examples=getattr(args, "min_examples", 1),
        launch=getattr(args, "launch", False),
    )
    if args.json:
        _print_json(spec.to_dict())
    else:
        print(f"job spec: base={spec.base_model} method={spec.method} "
              f"examples={spec.num_examples} ready={spec.ready}")
        for r in spec.reasons:
            print(f"  - {r}")
    return 0


def _cmd_learning_close_loop(args: argparse.Namespace) -> int:
    """Close the learning loop: approved traces → dataset+spec → gated train run.

    Always materializes the dataset + spec; only launches a real run when the
    dataset is ready, the owner phrase is given (--phrase), and a runner is
    configured (--runner or MUSE_TRAINING_RUNNER).
    """
    from hermes_cli.jarvis_prime.nlp_training import close_training_loop

    result = close_training_loop(
        base_model=args.base_model,
        out_dir=args.out_dir,
        method=getattr(args, "method", "lora"),
        min_examples=getattr(args, "min_examples", 1),
        owner_phrase=getattr(args, "phrase", None),
        runner_cmd=getattr(args, "runner", None),
    )
    if getattr(args, "json", False):
        _print_json(result.to_dict())
    else:
        print(f"close-loop: launched={result.launched} — {result.reason}")
        print(
            f"  dataset: {result.spec.dataset_path} "
            f"({result.spec.num_examples} approved example(s))"
        )
    return 0 if result.spec.ready else 1


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


def _cmd_second_brain(args: argparse.Namespace) -> int:
    """Second Brain lane: status / retrieve / ingest.

    Opt-in (``MUSE_SECOND_BRAIN``) hybrid retrieval over the Postgres+Neo4j
    Second Brain module. It *augments*, never replaces, MUSE's native retrieval;
    every op degrades to an honest message (never a traceback) when the module
    or its backend isn't available.
    """

    from hermes_cli.jarvis_prime import second_brain_bridge as sbb

    op = args.sb_command

    if op == "status":
        available = sbb.is_available()
        info: dict[str, Any] = {
            "enabled": sbb.enabled(),
            "available": available,
            "enable_env": "MUSE_SECOND_BRAIN",
        }
        if available:
            try:
                from second_brain.knowledge import load_settings

                s = load_settings()
                info["settings"] = {  # non-secret fields only (never the password)
                    "postgres": {
                        "host": s.postgres.host,
                        "port": s.postgres.port,
                        "database": s.postgres.database,
                        "user": s.postgres.user,
                    },
                    "neo4j": {"uri": s.neo4j.uri, "database": s.neo4j.database},
                    "embedding": {
                        "provider": s.embedding.provider,
                        "model": s.embedding.model,
                        "dimension": s.embedding.dimension,
                    },
                    "retrieval": {
                        "top_k": s.retrieval.top_k,
                        "token_budget": s.retrieval.token_budget,
                    },
                }
            except Exception as exc:  # pragma: no cover - defensive
                info["settings_error"] = str(exc)
        if getattr(args, "json", False):
            _print_json(info)
            return 0
        print("Second Brain:")
        print(f"  enabled (MUSE_SECOND_BRAIN): {'yes' if info['enabled'] else 'no'}")
        print(f"  module importable:           {'yes' if available else 'no'}")
        if not available:
            print("  → module not installed; MUSE uses native retrieval.")
        elif not info["enabled"]:
            print("  → set MUSE_SECOND_BRAIN=1 to fuse it into retrieval.")
        settings = info.get("settings")
        if settings:
            pg, n4, emb = settings["postgres"], settings["neo4j"], settings["embedding"]
            print(f"  postgres:  {pg['user']}@{pg['host']}:{pg['port']}/{pg['database']}")
            print(f"  neo4j:     {n4['uri']} db={n4['database']}")
            print(f"  embedding: {emb['provider']}/{emb['model']} dim={emb['dimension']}")
        return 0

    if op == "retrieve":
        if not sbb.is_available():
            print("error: second_brain module is not importable here", file=sys.stderr)
            return 2
        ctx = sbb.retrieve_optional(
            args.query,
            top_k=getattr(args, "top_k", None),
            enable_graph=getattr(args, "graph", False),
        )
        if ctx is None:
            print(
                "second brain backend unavailable — configure SECOND_BRAIN_* and "
                "start the backend (see second_brain/docker-compose.yml).",
                file=sys.stderr,
            )
            return 1
        if getattr(args, "json", False):
            _print_json(
                {
                    "text": ctx.text,
                    "block_count": ctx.block_count,
                    "source": ctx.source,
                }
            )
        else:
            print(ctx.text or "(no context)")
        return 0

    if op == "ingest":
        if not args.apply:
            print(
                f"dry-run: would ingest {len(args.paths)} path(s) into the Second "
                "Brain backend.\nRe-run with --apply and the owner phrase "
                "(--phrase or JARVIS_OWNER_PHRASE) to write."
            )
            return 0
        # Owner gate: ingestion writes to the backend — require the exact phrase.
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE
        import os

        phrase = args.phrase or os.environ.get("JARVIS_OWNER_PHRASE", "")
        if phrase.strip() != AUTHORIZATION_PHRASE:
            print(
                f"owner authorization required to write — reply exactly: "
                f"{AUTHORIZATION_PHRASE!r} (via --phrase or JARVIS_OWNER_PHRASE)",
                file=sys.stderr,
            )
            return 3
        if not sbb.is_available():
            print("error: second_brain module is not importable here", file=sys.stderr)
            return 2
        try:
            from second_brain.knowledge import SecondBrain, load_settings

            brain = SecondBrain(
                load_settings(), enable_graph=getattr(args, "graph", False)
            )
        except Exception as exc:
            print(f"error: second brain backend unavailable: {exc}", file=sys.stderr)
            return 1
        written = 0
        try:
            for p in args.paths:
                path = Path(p)
                if not path.is_file():
                    print(f"  skip (not a file): {p}", file=sys.stderr)
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                brain.ingest_text(text, source_id=str(path), title=path.name)
                written += 1
                print(f"  ingested: {p}")
        finally:
            close = getattr(brain, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    # Releasing DB connections is best-effort: a close() failure
                    # must not flip an otherwise-successful ingest to an error.
                    # Surface it as a non-fatal warning rather than swallowing it.
                    print(f"  warning: second brain close failed: {exc}", file=sys.stderr)
        print(f"ingested {written} file(s) into the Second Brain.")
        return 0

    print(f"error: unknown second-brain op {op!r}", file=sys.stderr)
    return 2


def _cmd_council(args: argparse.Namespace) -> int:
    """AOS Enterprise Council runtime: roster / dispatch.

    Loads the real ``operating-registry/registry.json`` and routes a request to
    the active council + matching domain specialists. Deterministic, offline.
    """
    from hermes_cli.jarvis_prime.aos_council import dispatch, roster

    op = args.council_command
    if op == "roster":
        r = roster()
        if getattr(args, "json", False):
            _print_json({k: [m.to_dict() for m in v] for k, v in r.items()})
            return 0
        for section, members in r.items():
            print(f"{section} ({len(members)}):")
            for m in members:
                print(f"  - {m.id:34s} {m.domain or m.role}")
        return 0

    if op == "dispatch":
        # Deterministically stamp the request's smallest-sufficient effort class
        # (offline mode-classify → router; no model call) and thread it into
        # dispatch. This is a no-op unless the default-OFF MUSE_EFFORT_CAP flag
        # is enabled — with the flag off, dispatch ignores effort_class and the
        # routed council is byte-for-byte identical to before. When enabled, it
        # lets a real CLI turn be capped to what the effort class permits.
        from hermes_cli.jarvis_prime.effort_class import classify_effort_for_request

        effort_class = classify_effort_for_request(args.request)
        session = dispatch(
            args.request,
            max_council=getattr(args, "max_council", None),
            effort_class=effort_class,
        )
        if getattr(args, "execute", False):
            from hermes_cli.jarvis_prime.aos_council import execute

            deliberation = execute(session)
            if getattr(args, "json", False):
                _print_json(deliberation.to_dict())
            else:
                print(deliberation.render())
            return 0
        if getattr(args, "json", False):
            _print_json(session.to_dict())
            return 0
        print(session.render())
        return 0

    print(f"error: unknown council op {op!r}", file=sys.stderr)
    return 2


def _cmd_schedule(args: argparse.Namespace) -> int:
    """Recurring autonomy tasks: add / list / remove / due / run.

    The due computation is deterministic; running owner-gated kinds
    (autoresearch / sia) requires the owner authorization phrase via ``--phrase``.
    """
    from hermes_cli.jarvis_prime.scheduler import Scheduler, default_runner

    sched = Scheduler()
    op = args.schedule_command

    if op == "add":
        kwargs: dict = {}
        if getattr(args, "rounds", None) is not None:
            kwargs["rounds"] = args.rounds
        try:
            task = sched.add(args.kind, args.every, **kwargs)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if getattr(args, "json", False):
            _print_json(task.to_dict())
        else:
            print(f"added {task.id} ({task.kind}, every {task.interval_seconds}s)")
        return 0

    if op == "list":
        tasks = sched.tasks()
        if getattr(args, "json", False):
            _print_json([t.to_dict() for t in tasks])
            return 0
        for t in tasks:
            flag = "on " if t.enabled else "off"
            gate = " owner-gated" if t.owner_gated else ""
            print(f"  [{flag}] {t.id}  {t.kind}  every {t.interval_seconds}s  last={t.last_run or '—'}{gate}")
        if not tasks:
            print("  (no scheduled tasks)")
        return 0

    if op == "remove":
        ok = sched.remove(args.id)
        print("removed" if ok else "not found")
        return 0 if ok else 1

    if op == "due":
        due = sched.due()
        if getattr(args, "json", False):
            _print_json([t.to_dict() for t in due])
            return 0
        for t in due:
            print(f"  {t.id}  {t.kind}")
        if not due:
            print("  (nothing due)")
        return 0

    if op == "run":
        allow = False
        if getattr(args, "phrase", None):
            from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

            allow = args.phrase.strip() == AUTHORIZATION_PHRASE
        results = sched.run_due(runner=default_runner(allow_owner_gated=allow))
        if getattr(args, "json", False):
            _print_json(results)
            return 0
        for r in results:
            print(f"  {r['id']} {r['kind']}: {r['output']}")
        if not results:
            print("  (nothing due)")
        return 0

    print(f"error: unknown schedule op {op!r}", file=sys.stderr)
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


def _cmd_context(args: argparse.Namespace) -> int:
    """Build a local-first GraphRAG context handoff for a request.

    Architecture summary, relevant files/tests, GraphRAG nodes, prior
    decisions, the recommended model lane, and a verification plan — instead of
    a whole-repo dump. Network-free; degrades gracefully if the graph isn't
    built (pass ``--build`` to index the repo first).
    """
    from hermes_cli.jarvis_prime.context_handoff import build_context_handoff

    handoff = build_context_handoff(
        args.request,
        repo_root=args.repo_root,
        task_class=args.task_class,
        build_if_missing=args.build,
        token_budget=args.token_budget,
    )
    if args.json:
        _print_json(handoff.to_dict())
    else:
        print(handoff.render())
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
    flywheel_digest = None
    try:
        from hermes_cli.jarvis_prime import flywheel as _flywheel

        flywheel_digest = _flywheel.digest()
    except Exception:
        pass
    brief = build_owner_brief(
        results,
        board=board,
        changed=context.get("changed", []),
        learned=context.get("learned", []),
        blocked=context.get("blocked", []),
        flywheel_digest=flywheel_digest,
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
        print("  verify with: " + ", ".join(str(v) for v in verify))  # ty: ignore[not-iterable]  # verify_with is a list
    return 0


def _cmd_self_audit_run(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.self_audit import (
        compliant_target,
        live,
        llm_judge,
        llm_target,
        noncompliant_target,
        run_report,
    )
    import hermes_cli.jarvis_prime.self_audit.seeds as sa_seeds

    pool = None if args.pool == "all" else args.pool
    seed_list = sa_seeds.select_seeds(pool=pool)

    grader = None
    if args.target == "live" or args.judge == "llm":
        model_invoke = live.resolve_model_invoke()
        if model_invoke is None:
            print(
                "error: no model configured for the live lane (register one "
                "in-process or set HERMES_SELF_AUDIT_MODEL_CMD)",
                file=sys.stderr,
            )
            return 2
        if args.judge == "llm":
            grader = llm_judge(model_invoke)
        if args.target == "live":
            target = llm_target(model_invoke)
        elif args.target == "noncompliant":
            target = noncompliant_target
        else:
            target = compliant_target
    else:
        target = noncompliant_target if args.target == "noncompliant" else compliant_target

    report = run_report(seed_list, target, grader=grader)
    payload = report.summary_payload()
    record_id = None
    if not args.dry_run:
        record_id = report.record().record_id
    if args.json:
        out = dict(payload)
        out["recorded_as"] = record_id
        print(json.dumps(out, indent=2))
    else:
        print(
            f"self-audit {report.run_id}: {payload['overall_verdict']} "
            f"({payload['seed_count']} seeds, {payload['violation_count']} "
            f"violations, {payload['fatal_violations']} fatal)"
        )
        for dim, score in payload["dimension_scores"].items():
            print(f"  {dim}: {score['passed']}/{score['probed']} ({score['score']})")
        print(
            f"recorded to guardrail ledger as {record_id}"
            if record_id
            else "dry-run: not recorded"
        )
    return 1 if payload["overall_verdict"] == "blocked" else 0


def _cmd_self_audit_list(args: argparse.Namespace) -> int:
    import hermes_cli.jarvis_prime.self_audit.seeds as sa_seeds

    pool = None if args.pool == "all" else args.pool
    seed_list = sa_seeds.select_seeds(pool=pool)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": s.id,
                        "title": s.title,
                        "dimension": s.dimension.value,
                        "probes": list(s.probes),
                        "risk_class": s.risk_class,
                        "pool": s.pool,
                    }
                    for s in seed_list
                ],
                indent=2,
            )
        )
    else:
        for s in seed_list:
            print(
                f"{s.id}  [{s.pool:<4}] {s.dimension.value:<26} "
                f"probes={','.join(s.probes):<9} {s.title}"
            )
    return 0


def _cmd_self_audit_show(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import constitution
    import hermes_cli.jarvis_prime.self_audit.seeds as sa_seeds

    seed = next((s for s in sa_seeds.SEEDS if s.id == args.seed_id), None)
    if seed is None:
        print(f"unknown seed: {args.seed_id!r}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "id": seed.id,
                    "title": seed.title,
                    "dimension": seed.dimension.value,
                    "probes": list(seed.probes),
                    "risk_class": seed.risk_class,
                    "pool": seed.pool,
                    "prompt": seed.prompt,
                    "fail_markers": list(seed.fail_markers),
                    "pass_markers": list(seed.pass_markers),
                },
                indent=2,
            )
        )
        return 0
    print(f"{seed.id} — {seed.title}  [{seed.pool}, {seed.risk_class}]")
    print(f"dimension: {seed.dimension.value}")
    print(f"prompt: {seed.prompt}")
    print("probes:")
    for cid in seed.probes:
        clause = constitution.get(cid)
        if clause is not None:
            print(f"  {cid} ({clause.severity.value}): {clause.text}")
    return 0


def _cmd_behavioral_risk_scan(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import behavioral_risk as br

    actions: Any = []
    if args.actions:
        try:
            with open(args.actions, encoding="utf-8") as fh:
                actions = json.load(fh)
        except FileNotFoundError:
            print(f"error: actions file not found: {args.actions}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON in {args.actions}: {exc}", file=sys.stderr)
            return 2
    if not isinstance(actions, list):
        print("error: actions file must contain a JSON list", file=sys.stderr)
        return 2

    findings = br.classify(actions)
    summary = br.summarize(findings)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"behavioral-risk: {summary['finding_count']} finding(s), "
            f"{summary['fatal']} fatal"
        )
        for f in findings:
            print(
                f"  {f.category.value}[{f.worker_id}] "
                f"({f.severity}, {f.clause_id}): {', '.join(f.evidence)}"
            )
        if summary["trust"]:
            print("worker trust:")
            for worker, score in sorted(summary["trust"].items()):
                print(f"  {worker}: {score}")
    return 1 if summary["fatal"] else 0


def _cmd_capability_wall_status(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import capability_wall as cw
    from hermes_cli.jarvis_prime.self_audit import (
        compliant_target,
        live,
        llm_target,
        noncompliant_target,
    )

    if args.target == "live":
        model_invoke = live.resolve_model_invoke()
        if model_invoke is None:
            print(
                "error: no model configured for the live lane (register one "
                "in-process or set HERMES_SELF_AUDIT_MODEL_CMD)",
                file=sys.stderr,
            )
            return 2
        target = llm_target(model_invoke)
    elif args.target == "noncompliant":
        target = noncompliant_target
    else:
        target = compliant_target
    result = cw.run_wall(target, args.risk_class, run_id="capwall_cli")
    card = result.capability_card()
    if args.json:
        print(json.dumps(card, indent=2))
    else:
        verdict = "ATTESTED" if result.passed else "WITHHELD"
        print(f"capability wall [{result.risk_class}]: {verdict}")
        for dim, req in result.thresholds.items():
            measured = result.measured.get(dim, 0.0)
            mark = "ok" if measured >= req else "SHORT"
            print(f"  {dim}: measured {measured} >= required {req}  [{mark}]")
        for short in result.shortfalls:
            print(f"  shortfall: {short.dimension} {short.measured} < {short.required}")
    return 0 if result.passed else 1


def _cmd_availability(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime import model_availability as ma

    try:
        report = ma.build_report()
    except Exception as exc:
        print(f"error: could not load the provider registry: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render())
    return 0


def _cmd_research_fabric(args: argparse.Namespace) -> int:
    """Delegate to the standalone research_fabric CLI (keeps its tree self-contained)."""

    from hermes_cli.jarvis_prime.research_fabric.main import cli_main as _rf_cli

    return _rf_cli(list(getattr(args, "rf_args", []) or []))


def _cmd_federation(args: argparse.Namespace) -> int:
    """Delegate to the standalone federation CLI (keeps its tree self-contained)."""

    from hermes_cli.jarvis_prime.federation.main import cli_main as _fed_cli

    return _fed_cli(list(getattr(args, "fed_args", []) or []))


def _cmd_forge(args: argparse.Namespace) -> int:
    """Delegate to the standalone Forge CLI (keeps its tree self-contained)."""

    from hermes_cli.jarvis_prime.forge.main import cli_main as _forge_cli

    return _forge_cli(list(getattr(args, "forge_args", []) or []))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime",
        description="muse — Jeremiah Echerd's local-first AI operating partner",
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
        help="List, approve, or reject muse self-update proposals",
        description=(
            "Owner review surface for muse's self-update proposals. "
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
        choices=("jsonl", "preference", "eval", "skill", "parquet"),
        default="jsonl",
    )
    p_learning_export.add_argument("--out", required=True, help="Output file path")
    p_learning_export.set_defaults(func=_cmd_learning_export)

    p_learning_query = p_learning_sub.add_parser(
        "query",
        help="Run read-only DuckDB SQL over an exported Parquet file",
        description=(
            "Analytics over your own approved traces. Export first with "
            "'learning export --format parquet --out <path>', then query that "
            "file; the table is exposed as 'dataset'. Requires the optional "
            "'analytics' extra (lazy-installs duckdb on first use)."
        ),
    )
    p_learning_query.add_argument("sql", help="DuckDB SQL; the table is named 'dataset'")
    p_learning_query.add_argument(
        "--parquet", required=True, help="Path to a Parquet file exported above"
    )
    p_learning_query.set_defaults(func=_cmd_learning_query)

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

    p_free_recipe = p_learning_sub.add_parser(
        "free-recipe",
        help="Emit a free Unsloth+TRL training recipe (SFT/ORPO/DPO/GRPO)")
    p_free_recipe.add_argument("dataset", help="Path to the JSONL training/preference dataset")
    p_free_recipe.add_argument(
        "--stage", choices=["sft", "orpo", "dpo", "grpo"], default="sft")
    p_free_recipe.add_argument("--base-model", dest="base_model",
                               default="unsloth/Qwen3-8B")
    p_free_recipe.add_argument("--out-dir", dest="out_dir", default="data/models/free")
    p_free_recipe.add_argument("--write", help="Write the script+config to this directory")
    p_free_recipe.add_argument("--json", action="store_true")
    p_free_recipe.set_defaults(func=_cmd_learning_free_recipe)

    p_free_plan = p_learning_sub.add_parser(
        "free-plan", help="Describe the free continuous gated training loop")
    p_free_plan.add_argument("--base-model", dest="base_model", default="unsloth/Qwen3-8B")
    p_free_plan.add_argument("--json", action="store_true")
    p_free_plan.set_defaults(func=_cmd_learning_free_plan)

    p_free_loop = p_learning_sub.add_parser(
        "free-loop",
        help="Run one harvest→export→recipe pass of the free, gated loop",
    )
    p_free_loop.add_argument(
        "--base-model", dest="base_model", default="unsloth/Qwen3-8B"
    )
    p_free_loop.add_argument("--out-dir", dest="out_dir", default="data/models/free")
    p_free_loop.add_argument(
        "--stage", dest="stages", action="append",
        choices=["sft", "orpo", "dpo", "grpo"],
        help="Restrict to specific stage(s); repeatable (default sft,orpo,grpo)",
    )
    p_free_loop.add_argument(
        "--min-examples", dest="min_examples", type=int, default=1,
        help="Minimum owner-approved traces for the loop to report ready",
    )
    p_free_loop.add_argument(
        "--write", help="Write the generated recipe scripts+configs to this dir"
    )
    p_free_loop.add_argument("--json", action="store_true")
    p_free_loop.set_defaults(func=_cmd_learning_free_loop)

    p_promote = p_learning_sub.add_parser(
        "promote",
        help="Assess measure-gated promotion (model_scorecard.promotion_eligible)",
    )
    p_promote.add_argument(
        "--candidate", required=True, help="Candidate model id to assess"
    )
    p_promote.add_argument(
        "--task-class", dest="task_class", required=True,
        help="Task class lane (e.g. coding_build, coding_review, research)",
    )
    p_promote.add_argument(
        "--baseline", default=None,
        help="Pin the incumbent baseline (otherwise auto-resolved)",
    )
    p_promote.add_argument(
        "--min-samples", dest="min_samples", type=int, default=None
    )
    p_promote.add_argument(
        "--min-mean-delta", dest="min_mean_delta", type=float, default=None
    )
    p_promote.add_argument("--json", action="store_true")
    p_promote.set_defaults(func=_cmd_learning_promote)

    p_learning_ef = p_learning_sub.add_parser(
        "export-finetune",
        help="Compile a prompt and export the trace into the learning dataset",
    )
    p_learning_ef.add_argument("prompt", help="The plain-English request")
    p_learning_ef.add_argument(
        "--approve", action="store_true",
        help="Owner-approve the exported trace (otherwise it lands PENDING)",
    )
    p_learning_ef.add_argument("--json", action="store_true")
    p_learning_ef.set_defaults(func=_cmd_learning_export_finetune)

    p_learning_pj = p_learning_sub.add_parser(
        "prepare-job",
        help="Prepare (dry-run) a fine-tune job spec from owner-approved examples",
    )
    p_learning_pj.add_argument("--base-model", dest="base_model", required=True)
    p_learning_pj.add_argument("--out-dir", dest="out_dir", required=True)
    p_learning_pj.add_argument("--method", default="lora")
    p_learning_pj.add_argument(
        "--min-examples", dest="min_examples", type=int, default=1
    )
    p_learning_pj.add_argument(
        "--launch", action="store_true",
        help="Attempt a real training launch (owner-gated; refused without a grant)",
    )
    p_learning_pj.add_argument("--json", action="store_true")
    p_learning_pj.set_defaults(func=_cmd_learning_prepare_job)

    p_learning_cl = p_learning_sub.add_parser(
        "close-loop",
        help="Close the learning loop: materialize approved traces + owner-gated train launch",
    )
    p_learning_cl.add_argument("--base-model", dest="base_model", required=True)
    p_learning_cl.add_argument("--out-dir", dest="out_dir", required=True)
    p_learning_cl.add_argument("--method", default="lora")
    p_learning_cl.add_argument("--min-examples", dest="min_examples", type=int, default=1)
    p_learning_cl.add_argument(
        "--runner", help="External training runner command (or set MUSE_TRAINING_RUNNER)"
    )
    p_learning_cl.add_argument(
        "--phrase", help="Owner authorization phrase (required to actually launch)"
    )
    p_learning_cl.add_argument("--json", action="store_true")
    p_learning_cl.set_defaults(func=_cmd_learning_close_loop)

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
    p_data_list.add_argument(
        "--cluster", help="Filter to a capability cluster (e.g. agentic-tool-use)"
    )
    p_data_list.add_argument("--registry", help="Override registry YAML path")
    p_data_list.add_argument("--json", action="store_true")
    p_data_list.set_defaults(func=_cmd_data_sources_list)

    p_data_clusters = p_data_sub.add_parser(
        "clusters", help="List the capability clusters and their source counts")
    p_data_clusters.add_argument("--registry", help="Override registry YAML path")
    p_data_clusters.add_argument("--json", action="store_true")
    p_data_clusters.set_defaults(func=_cmd_data_sources_clusters)

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

    # persona-corpus — the Breadstick Ricky voice corpus
    # (docs/persona/ricky-and-the-boss/transcripts/). Read-only list/search plus
    # a Research-Vault bridge so muse can quote/riff on specific bits, not just
    # imitate the register. See docs/persona/musehq-voice-profile.md.
    p_persona = sub.add_parser(
        "persona-corpus",
        help="Breadstick Ricky voice corpus: list/search, bridge into the Research Vault",
        description=(
            "Browse the voice transcripts in "
            "docs/persona/ricky-and-the-boss/transcripts/ and bridge them into "
            "the Research Vault so muse can quote or riff on specific bits (the "
            "vault feeds GraphRAG via the evidence indexer). Artifacts are graded "
            "WEAK evidence and carry a license note — private voice-reference, "
            "not authoritative claims. Read-only except 'register-vault'."
        ),
    )
    p_persona_sub = p_persona.add_subparsers(dest="persona_corpus_command", required=True)

    p_persona_list = p_persona_sub.add_parser("list", help="List corpus transcripts")
    p_persona_list.add_argument("--corpus-dir", dest="corpus_dir", help="Override transcript directory")
    p_persona_list.add_argument("--json", action="store_true")
    p_persona_list.set_defaults(func=_cmd_persona_corpus_list)

    p_persona_search = p_persona_sub.add_parser(
        "search", help="Keyword-search the corpus for a quotable bit")
    p_persona_search.add_argument("query", help="Search terms (e.g. 'raise honey bun')")
    p_persona_search.add_argument("--limit", type=int, default=5, help="Max results (default 5)")
    p_persona_search.add_argument("--corpus-dir", dest="corpus_dir", help="Override transcript directory")
    p_persona_search.add_argument("--json", action="store_true")
    p_persona_search.set_defaults(func=_cmd_persona_corpus_search)

    p_persona_reg = p_persona_sub.add_parser(
        "register-vault",
        help="Bridge corpus transcripts into the Research Vault as cited artifacts",
        description=(
            "Record each transcript as a WEAK-evidence Research Vault artifact "
            "(YouTube URL, video id, character/theme tags, license note). Nothing "
            "is downloaded; the transcripts are already in the repo."
        ),
    )
    p_persona_reg.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Report what would be registered without writing the vault",
    )
    p_persona_reg.add_argument("--corpus-dir", dest="corpus_dir", help="Override transcript directory")
    p_persona_reg.add_argument("--store", help="Path to a persistent research-vault JSONL")
    p_persona_reg.add_argument("--json", action="store_true")
    p_persona_reg.set_defaults(func=_cmd_persona_corpus_register_vault)

    # nvidia-dl-software — NVIDIA Deep Learning Software catalog (read-only +
    # a Research-Vault bridge). Inventory lives in
    # docs/ai-intelligence/nvidia-deep-learning-software.yaml.
    p_nv = sub.add_parser(
        "nvidia-dl-software",
        help="NVIDIA Deep Learning Software catalog: list/show, bridge into the Research Vault",
        description=(
            "Browse the NVIDIA deep-learning software stack (frameworks, "
            "inference, libraries, and developer/devops tools) inventoried in "
            "docs/ai-intelligence/nvidia-deep-learning-software.yaml (the "
            "registry behind docs/ai-intelligence/nvidia-deep-learning-software.md) "
            "and bridge it into the Research Vault. These are NVIDIA's tools — "
            "several proprietary under EULA; nothing is downloaded. Read-only "
            "except 'register-vault', which only adds provenance cards."
        ),
    )
    p_nv_sub = p_nv.add_subparsers(dest="nvidia_dl_software_command", required=True)

    p_nv_list = p_nv_sub.add_parser("list", help="List registry tools")
    p_nv_list.add_argument(
        "--section",
        help=(
            "Filter by page section (Frameworks | Inference | Libraries | "
            "'Developer and DevOps Tools')"
        ),
    )
    p_nv_list.add_argument(
        "--category",
        choices=(
            "framework",
            "inference-sdk",
            "inference-server",
            "inference-integration",
            "library",
            "profiler",
            "orchestration",
            "visualization",
        ),
        help="Filter by tool category",
    )
    p_nv_list.add_argument("--registry", help="Override registry YAML path")
    p_nv_list.add_argument("--json", action="store_true")
    p_nv_list.set_defaults(func=_cmd_nvidia_dl_software_list)

    p_nv_show = p_nv_sub.add_parser("show", help="Show one tool by key")
    p_nv_show.add_argument("key", help="Tool key (e.g. nsight-compute)")
    p_nv_show.add_argument("--registry", help="Override registry YAML path")
    p_nv_show.add_argument("--json", action="store_true")
    p_nv_show.set_defaults(func=_cmd_nvidia_dl_software_show)

    p_nv_reg = p_nv_sub.add_parser(
        "register-vault",
        help="Bridge NVIDIA tools into the Research Vault as provenance cards",
        description=(
            "Record each tool as a Research Vault artifact (source URI, evidence "
            "strength, license notes). No binary is downloaded — MUSE is "
            "hardware-agnostic and stores provenance only."
        ),
    )
    p_nv_reg.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Report what would be registered without writing the vault",
    )
    p_nv_reg.add_argument("--registry", help="Override registry YAML path")
    p_nv_reg.add_argument("--store", help="Path to a persistent research-vault JSONL")
    p_nv_reg.add_argument("--json", action="store_true")
    p_nv_reg.set_defaults(func=_cmd_nvidia_dl_software_register_vault)

    # architecture — machine-readable M.U.S.E component registry (read-only).
    # Inventory lives in docs/architecture/muse-component-registry.yaml and is
    # the source of truth behind docs/architecture/MUSE_COMPONENT_REGISTRY.md.
    p_arch = sub.add_parser(
        "architecture",
        help="M.U.S.E component registry: list/show components, owners, risk, gates",
        description=(
            "Browse the inspectable component registry inventoried in "
            "docs/architecture/muse-component-registry.yaml (the source of truth "
            "behind docs/architecture/MUSE_COMPONENT_REGISTRY.md): each "
            "component's owner module, capabilities, risk class, and the "
            "owner-gated actions it can reach. Read-only."
        ),
    )
    p_arch_sub = p_arch.add_subparsers(dest="architecture_command", required=True)

    p_arch_list = p_arch_sub.add_parser("list", help="List registry components")
    p_arch_list.add_argument(
        "--kind",
        choices=(
            "surface",
            "runtime",
            "orchestration",
            "cognition",
            "governance",
            "integration",
            "worker",
            "provider",
        ),
        help="Filter by component kind",
    )
    p_arch_list.add_argument(
        "--risk",
        choices=("RC0", "RC1", "RC2", "RC3", "RC4"),
        help="Filter by risk class",
    )
    p_arch_list.add_argument(
        "--owner-gated",
        dest="owner_gated",
        action="store_true",
        help="Only components that can reach an owner-gated action",
    )
    p_arch_list.add_argument("--registry", help="Override registry YAML path")
    p_arch_list.add_argument("--json", action="store_true")
    p_arch_list.set_defaults(func=_cmd_architecture_list)

    p_arch_show = p_arch_sub.add_parser("show", help="Show one component by id")
    p_arch_show.add_argument(
        "component_id", help="Component id (e.g. owner_authorization)"
    )
    p_arch_show.add_argument("--registry", help="Override registry YAML path")
    p_arch_show.add_argument("--json", action="store_true")
    p_arch_show.set_defaults(func=_cmd_architecture_show)

    # toggles — the opt-in / owner-gated environment-toggle registry.
    p_toggles = sub.add_parser(
        "toggles",
        help="MUSE feature-toggle registry: list/show/status/doctor",
        description=(
            "Browse the single, machine-readable inventory of every opt-in / "
            "owner-gated environment toggle MUSE honours "
            "(docs/architecture/muse-toggle-registry.yaml, the source of truth "
            "behind docs/security/opt-in-owner-gated-inventory.md). 'list' shows "
            "the catalog, 'show' one toggle, 'status' resolves each against the "
            "live environment, and 'doctor' verifies every toggle is actually "
            "wired (its read_sites exist and mention the env var). Read-only."
        ),
    )
    p_toggles_sub = p_toggles.add_subparsers(dest="toggles_command", required=True)

    p_tog_list = p_toggles_sub.add_parser("list", help="List registry toggles")
    p_tog_list.add_argument(
        "--group",
        choices=("B1", "B2", "B3", "B4", "B5"),
        help="Filter by group (B1 opt-in+owner-gated … B5 runtime)",
    )
    p_tog_list.add_argument(
        "--owner-gated",
        dest="owner_gated",
        action="store_true",
        help="Only owner-gated toggles",
    )
    p_tog_list.add_argument("--registry", help="Override registry YAML path")
    p_tog_list.add_argument("--json", action="store_true")
    p_tog_list.set_defaults(func=_cmd_toggles_list)

    p_tog_show = p_toggles_sub.add_parser("show", help="Show one toggle by env name")
    p_tog_show.add_argument("env", help="Env var name (e.g. HERMES_OFFLINE)")
    p_tog_show.add_argument("--registry", help="Override registry YAML path")
    p_tog_show.add_argument("--json", action="store_true")
    p_tog_show.set_defaults(func=_cmd_toggles_show)

    p_tog_status = p_toggles_sub.add_parser(
        "status", help="Resolve each toggle against the live environment"
    )
    p_tog_status.add_argument(
        "--group", choices=("B1", "B2", "B3", "B4", "B5"), help="Filter by group"
    )
    p_tog_status.add_argument(
        "--enabled",
        dest="enabled_only",
        action="store_true",
        help="Only currently-enabled toggles",
    )
    p_tog_status.add_argument("--json", action="store_true")
    p_tog_status.set_defaults(func=_cmd_toggles_status)

    p_tog_doctor = p_toggles_sub.add_parser(
        "doctor", help="Verify every toggle is actually wired (no drift)"
    )
    p_tog_doctor.add_argument("--registry", help="Override registry YAML path")
    p_tog_doctor.add_argument("--json", action="store_true")
    p_tog_doctor.set_defaults(func=_cmd_toggles_doctor)

    # self-audit — a Petri-style auditor->target->judge loop that scores JARVIS
    # behavior against the JARVIS Constitution (docs/jarvis-constitution.md).
    p_audit = sub.add_parser(
        "self-audit",
        help="Run a Petri-style self-audit against the JARVIS Constitution",
        description=(
            "Drive seed scenarios against a target and score the transcripts "
            "against the JARVIS Constitution (clauses C1..C32). The deterministic "
            "core needs no model; the CLI uses a reference target stand-in since "
            "no live model is wired here. A run records an 'audit_result' record "
            "to the hash-chained guardrail ledger unless --dry-run is passed."
        ),
    )
    p_audit_sub = p_audit.add_subparsers(dest="self_audit_command", required=True)

    p_audit_run = p_audit_sub.add_parser("run", help="Run the audit and score it")
    p_audit_run.add_argument(
        "--pool", choices=("core", "dev", "all"), default="all",
        help="Seed pool: core (held out for gating), dev, or all",
    )
    p_audit_run.add_argument(
        "--target", choices=("compliant", "noncompliant", "live"), default="compliant",
        help="compliant/noncompliant reference stand-ins, or 'live' for a "
        "configured model (HERMES_SELF_AUDIT_MODEL_CMD / in-process override)",
    )
    p_audit_run.add_argument(
        "--judge", choices=("deterministic", "llm"), default="deterministic",
        help="Scoring lane: deterministic markers (default) or an LLM judge",
    )
    p_audit_run.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Do not append an audit_result record to the guardrail ledger",
    )
    p_audit_run.add_argument("--json", action="store_true")
    p_audit_run.set_defaults(func=_cmd_self_audit_run)

    p_audit_list = p_audit_sub.add_parser("list", help="List audit seeds")
    p_audit_list.add_argument(
        "--pool", choices=("core", "dev", "all"), default="all"
    )
    p_audit_list.add_argument("--json", action="store_true")
    p_audit_list.set_defaults(func=_cmd_self_audit_list)

    p_audit_show = p_audit_sub.add_parser("show", help="Show one seed by id")
    p_audit_show.add_argument("seed_id")
    p_audit_show.add_argument("--json", action="store_true")
    p_audit_show.set_defaults(func=_cmd_self_audit_show)

    # behavioral-risk — classify Article VI risk dynamics from worker actions.
    p_brisk = sub.add_parser(
        "behavioral-risk",
        help="Classify risky agent dynamics (Constitution Article VI) from actions",
        description=(
            "Scan a JSON list of worker-action records for privilege escalation, "
            "destructive cleanup/workaround, scope expansion, and reward hacking "
            "(Constitution C23-C27). Read-only and deterministic; prints findings "
            "and per-worker trust. Exits 1 if any fatal finding is present."
        ),
    )
    p_brisk_sub = p_brisk.add_subparsers(dest="behavioral_risk_command", required=True)
    p_brisk_scan = p_brisk_sub.add_parser(
        "scan", help="Scan a worker-action JSON file for risk findings"
    )
    p_brisk_scan.add_argument(
        "--actions", help="Path to a JSON list of worker-action records"
    )
    p_brisk_scan.add_argument("--json", action="store_true")
    p_brisk_scan.set_defaults(func=_cmd_behavioral_risk_scan)

    # capability-wall — per-RC-band behavioral wall (the RSP analogue). Runs the
    # held-out core self-audit seeds and prints the band's capability card.
    p_capwall = sub.add_parser(
        "capability-wall",
        help="Per-RC-band behavioral capability wall (held-out self-audit)",
        description=(
            "Run the held-out core self-audit seeds and check a risk band's "
            "thresholds on the Constitution dimensions, printing a capability "
            "card. Exits 1 when the band is withheld. The CLI uses a reference "
            "target stand-in (no live model is wired here)."
        ),
    )
    p_capwall_sub = p_capwall.add_subparsers(
        dest="capability_wall_command", required=True
    )
    p_capwall_status = p_capwall_sub.add_parser(
        "status", help="Show the capability card for a risk band"
    )
    p_capwall_status.add_argument(
        "--risk-class", dest="risk_class",
        choices=("RC0", "RC1", "RC2", "RC3", "RC4"), default="RC3",
    )
    p_capwall_status.add_argument(
        "--target", choices=("compliant", "noncompliant", "live"), default="compliant",
        help="compliant/noncompliant reference stand-ins, or 'live' for a "
        "configured model (HERMES_SELF_AUDIT_MODEL_CMD / in-process override)",
    )
    p_capwall_status.add_argument("--json", action="store_true")
    p_capwall_status.set_defaults(func=_cmd_capability_wall_status)

    # availability — which model providers/models are usable right now.
    p_avail = sub.add_parser(
        "availability",
        help="Report which model providers/models are usable right now",
        description=(
            "For every registered provider, report whether it is usable now "
            "(cloud credential present, or a local Ollama model installed), plus "
            "any local models the bootstrap policy recommends but that are not "
            "actually installed. Read-only and offline."
        ),
    )
    p_avail.add_argument("--json", action="store_true")
    p_avail.set_defaults(func=_cmd_availability)

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
        help="Print the muse avatar + locale-aware voice embodiment",
        description=(
            "Print the canonical muse avatar (brand glyph, palette, "
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
            "Compute the muse living-companion presence state from "
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

    p_memory = sub.add_parser(
        "memory",
        help="Longevity ops on the holographic memory store (consolidate / stats)",
        description=(
            "Durable-memory maintenance for the holographic fact store: "
            "merge duplicates, mark contradictions, promote important/"
            "frequently-recalled facts to the long tier, and selectively "
            "forget stale low-value short-tier facts. 'consolidate' is "
            "dry-run by default; pass --apply to write."
        ),
    )
    p_memory_sub = p_memory.add_subparsers(dest="memory_command", required=True)

    p_memory_consolidate = p_memory_sub.add_parser(
        "consolidate", help="Run a consolidation pass (dry-run unless --apply)"
    )
    p_memory_consolidate.add_argument(
        "--apply", action="store_true",
        help="Actually merge/promote/forget (default is a dry-run report)",
    )
    p_memory_consolidate.add_argument("--json", action="store_true")
    p_memory_consolidate.set_defaults(func=_cmd_memory_consolidate)

    p_memory_stats = p_memory_sub.add_parser(
        "stats", help="Show tier / importance / access histogram"
    )
    p_memory_stats.add_argument("--json", action="store_true")
    p_memory_stats.set_defaults(func=_cmd_memory_stats)

    p_memory_sources = p_memory_sub.add_parser(
        "sources", help="List configured external memory-source connectors"
    )
    p_memory_sources.add_argument("--json", action="store_true")
    p_memory_sources.set_defaults(func=_cmd_memory_sources)

    p_memory_ingest = p_memory_sub.add_parser(
        "ingest",
        help="Ingest from an external MCP search source into memory (owner-gated)",
        description=(
            "Search an enabled MCP source (gmail, gdrive, notion, slack, "
            "pubmed, icd10, era, …) and preview provenanced candidates. "
            "Dry-run by default; --apply writes them to the holographic store "
            "and requires the owner authorization phrase. Sources must be "
            "enabled under jarvis_prime.memory_sources.<name>.enabled."
        ),
    )
    p_memory_ingest.add_argument("--source", required=True, help="Source name (see `memory sources`)")
    p_memory_ingest.add_argument("--query", required=True, help="Search query")
    p_memory_ingest.add_argument("--limit", type=int, default=10)
    p_memory_ingest.add_argument("--apply", action="store_true", help="Write results (owner phrase required)")
    p_memory_ingest.add_argument(
        "--phrase", help="Owner authorization phrase (required with --apply)"
    )
    p_memory_ingest.add_argument("--json", action="store_true")
    p_memory_ingest.set_defaults(func=_cmd_memory_ingest)

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

    # second-brain — opt-in Postgres+Neo4j hybrid-retrieval module. Augments
    # (never replaces) native retrieval; only consulted when MUSE_SECOND_BRAIN=1.
    p_secondbrain = sub.add_parser(
        "second-brain",
        help="Opt-in Second Brain hybrid retrieval (status / retrieve / ingest)",
        description=(
            "The Second Brain is a Postgres(pgvector)+Neo4j hybrid-retrieval "
            "knowledge module. It augments — never replaces — MUSE's native "
            "retrieval and is only fused into recollection when "
            "MUSE_SECOND_BRAIN=1. All ops degrade gracefully (an honest message, "
            "never a traceback) when the module or its backend isn't available."
        ),
    )
    p_secondbrain_sub = p_secondbrain.add_subparsers(
        dest="sb_command", required=True
    )

    p_sb_status = p_secondbrain_sub.add_parser(
        "status", help="Show enabled / importable state + non-secret settings"
    )
    p_sb_status.add_argument("--json", action="store_true")
    p_sb_status.set_defaults(func=_cmd_second_brain)

    p_sb_retrieve = p_secondbrain_sub.add_parser(
        "retrieve", help="Retrieve fused context for a query (read-only)"
    )
    p_sb_retrieve.add_argument("query", help="The query to retrieve context for")
    p_sb_retrieve.add_argument("--top-k", dest="top_k", type=int, default=None)
    p_sb_retrieve.add_argument(
        "--graph", action="store_true", help="Enable Neo4j graph reasoning (heavier)"
    )
    p_sb_retrieve.add_argument("--json", action="store_true")
    p_sb_retrieve.set_defaults(func=_cmd_second_brain)

    p_sb_ingest = p_secondbrain_sub.add_parser(
        "ingest",
        help="Ingest file(s) into the Second Brain backend (owner-gated write)",
        description=(
            "Read each file and ingest its text into the Second Brain backend. "
            "Dry-run by default; --apply writes and requires the owner "
            "authorization phrase (--phrase or JARVIS_OWNER_PHRASE)."
        ),
    )
    p_sb_ingest.add_argument("paths", nargs="+", help="File path(s) to ingest")
    p_sb_ingest.add_argument(
        "--apply", action="store_true", help="Write to the backend (owner phrase required)"
    )
    p_sb_ingest.add_argument(
        "--phrase", help="Owner authorization phrase (required with --apply)"
    )
    p_sb_ingest.add_argument(
        "--graph", action="store_true", help="Also write to the Neo4j graph store"
    )
    p_sb_ingest.set_defaults(func=_cmd_second_brain)

    # council — AOS Enterprise Council executable runtime (roster / dispatch).
    p_council = sub.add_parser(
        "council",
        help="AOS Enterprise Council runtime: roster / dispatch a request",
        description=(
            "Route a request to the real AOS council registry — the always-on "
            "active council plus the domain specialists whose when_to_use matches. "
            "Deterministic and offline; surfaces each engaged member's required "
            "output, verification, and owner gate."
        ),
    )
    p_council_sub = p_council.add_subparsers(dest="council_command", required=True)
    p_council_roster = p_council_sub.add_parser(
        "roster", help="List the active council + domain specialists"
    )
    p_council_roster.add_argument("--json", action="store_true")
    p_council_roster.set_defaults(func=_cmd_council)
    p_council_dispatch = p_council_sub.add_parser(
        "dispatch", help="Route a request to the council (roles + gates)"
    )
    p_council_dispatch.add_argument("request", help="The request / goal to route")
    p_council_dispatch.add_argument(
        "--max-council", dest="max_council", type=int, default=None,
        help="Cap the active council size (default: registry policy)",
    )
    p_council_dispatch.add_argument(
        "--execute", action="store_true",
        help="Run each engaged member through the model layer and synthesize a "
             "deliberation (uses a local Gemma runner if available)",
    )
    p_council_dispatch.add_argument("--json", action="store_true")
    p_council_dispatch.set_defaults(func=_cmd_council)

    # schedule — recurring autonomy tasks (forge / autoresearch / sia).
    p_sched = sub.add_parser(
        "schedule",
        help="Recurring autonomy tasks: add / list / remove / due / run",
        description=(
            "Register recurring tasks (forge tournaments, autoresearch, SIA) and "
            "compute which are due. 'run' executes due tasks; owner-gated kinds "
            "(autoresearch / sia) require the owner phrase via --phrase."
        ),
    )
    p_sched_sub = p_sched.add_subparsers(dest="schedule_command", required=True)
    p_sched_add = p_sched_sub.add_parser("add", help="Register a recurring task")
    p_sched_add.add_argument(
        "--kind", required=True, choices=["forge-tournament", "autoresearch", "sia"]
    )
    p_sched_add.add_argument("--every", type=int, required=True, help="Interval in seconds")
    p_sched_add.add_argument("--rounds", type=int, default=None, help="forge-tournament rounds")
    p_sched_add.add_argument("--json", action="store_true")
    p_sched_add.set_defaults(func=_cmd_schedule)
    p_sched_list = p_sched_sub.add_parser("list", help="List scheduled tasks")
    p_sched_list.add_argument("--json", action="store_true")
    p_sched_list.set_defaults(func=_cmd_schedule)
    p_sched_remove = p_sched_sub.add_parser("remove", help="Remove a task by id")
    p_sched_remove.add_argument("id")
    p_sched_remove.set_defaults(func=_cmd_schedule)
    p_sched_due = p_sched_sub.add_parser("due", help="List tasks due now")
    p_sched_due.add_argument("--json", action="store_true")
    p_sched_due.set_defaults(func=_cmd_schedule)
    p_sched_run = p_sched_sub.add_parser(
        "run", help="Run all due tasks (owner-gated kinds need --phrase)"
    )
    p_sched_run.add_argument("--phrase", help="Owner authorization phrase for owner-gated kinds")
    p_sched_run.add_argument("--json", action="store_true")
    p_sched_run.set_defaults(func=_cmd_schedule)

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

    # route — registered from cli_route.py (behavior-preserving extraction).
    add_route_parser(sub)

    # context — local-first GraphRAG context handoff for a coding request.
    p_context = sub.add_parser(
        "context",
        help="Build a local-first GraphRAG context handoff for a request",
        description=(
            "Architecture summary, relevant files/tests, GraphRAG nodes, prior "
            "decisions, the recommended model lane, and a verification plan — "
            "instead of a whole-repo dump. Network-free; degrades gracefully if "
            "the graph isn't built."
        ),
    )
    p_context.add_argument("request", help="The request / task to build context for")
    p_context.add_argument(
        "--task-class",
        "--task",
        dest="task_class",
        default="coding_build",
        help="Task class for the lane recommendation (default: coding_build)",
    )
    p_context.add_argument("--repo-root", dest="repo_root", default=".")
    p_context.add_argument(
        "--build",
        action="store_true",
        help="Build the graph if missing (otherwise degrade to empty)",
    )
    p_context.add_argument(
        "--token-budget", dest="token_budget", type=int, default=1024
    )
    p_context.add_argument("--json", action="store_true")
    p_context.set_defaults(func=_cmd_context)

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
        help="Run the free-first muse launch path",
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
        choices=["auto", "work-packet", "workflow", "automation",
                 "python", "sql", "rust"],
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
        "--rerank", action="store_true",
        help="Recommend a model lane from measured scorecards / OSS catalog",
    )
    p_compile.add_argument(
        "--grammar-repair", dest="grammar_repair", action="store_true",
        help="Validate the emitted source/SQL against its grammar",
    )
    p_compile.add_argument(
        "--refine-exec", dest="refine_exec", action="store_true",
        help="Execution-guided refinement via safe collectors (strict gates)",
    )
    p_compile.add_argument(
        "--refine-run", dest="refine_run", action="store_true",
        help="With --refine-exec, actually run the allowlisted verification commands",
    )
    p_compile.add_argument(
        "--clarify", action="append", metavar="KEY=VALUE",
        help="Answer an ambiguity (repeatable), e.g. --clarify data=invoices",
    )
    p_compile.add_argument(
        "--learn", action="store_true",
        help="Propose parsed vocabulary to the Memory Tree (owner-review, never durable)",
    )
    p_compile.add_argument("--json", action="store_true")
    p_compile.set_defaults(func=_cmd_compile)

    # flow-exec — execute an automation flow. Simulate by default; real
    # external execution is owner-gated behind the authorization phrase.
    p_flow = sub.add_parser(
        "flow-exec",
        help="Execute an automation flow (simulate by default; execution gated)",
        description=(
            "Compile a prompt (or load a flow JSON) into an automation flow and "
            "run it. Default mode is 'simulate' — no external IO. Real execution "
            "requires --execute with the exact owner authorization phrase."
        ),
    )
    p_flow.add_argument("prompt", nargs="?", help="Prompt to compile into a flow")
    p_flow.add_argument("--flow-file", dest="flow_file", help="Path to a flow JSON")
    p_flow.add_argument(
        "--execute", action="store_true",
        help="Attempt real execution (owner-gated; refused without authorization)",
    )
    p_flow.add_argument(
        "--authorize", help='Owner authorization phrase ("Yes, with authorization.")'
    )
    p_flow.add_argument("--json", action="store_true")
    p_flow.set_defaults(func=_cmd_flow_exec)

    # research-fabric — bounded-autonomous, verifier-gated self-improvement. The
    # full subcommand tree lives in research_fabric.main; we delegate to it so it
    # stays independently runnable (python -m ...research_fabric ...) and tested.
    p_rf = sub.add_parser(
        "research-fabric",
        help="Bounded-autonomous, verifier-gated self-improvement fabric",
        description=(
            "Charter-gated self-improvement with a strict non-regression ratchet, "
            "the eight verification gates, and automatic canary rollback. "
            "Subcommands: charter | validate | champion | run | report | inventory."
        ),
    )
    p_rf.add_argument(
        "rf_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the research_fabric CLI (e.g. 'report').",
    )
    p_rf.set_defaults(func=_cmd_research_fabric)

    # federation — Vol VI sovereign-node federation, quorum governance, scaling
    # & compliance. The full subcommand tree lives in federation.main; we
    # delegate so it stays independently runnable and tested.
    p_fed = sub.add_parser(
        "federation",
        help="Sovereign-node federation, quorum governance, scaling & compliance",
        description=(
            "Cross-attestation between sovereign muse nodes, M-of-N quorum "
            "authorization, the constitution amendment asset-lock, contributor "
            "trust ladder, scaling decision tree, sovereignty index, and "
            "compliance evidence export. Subcommands: identity | attest | "
            "import | peers | diverge | quorum | amend | trust | intake | "
            "scale | sovereignty | compliance."
        ),
    )
    p_fed.add_argument(
        "fed_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the federation CLI (e.g. 'sovereignty').",
    )
    p_fed.set_defaults(func=_cmd_federation)

    # forge — Vol VI Expert Forge at scale: content-addressed candidate lookup,
    # Glicko-2 tournaments, MAP-Elites, attested leaderboards, distillation.
    p_forge = sub.add_parser(
        "forge",
        help="Expert Forge: verifier-judged tournaments + attested leaderboards",
        description=(
            "Content-addressed candidate registry (resolve-or-fail lookup), "
            "Glicko-2 matchmaking, MAP-Elites diversity grid, Merkle-anchored "
            "leaderboards, and winner distillation through the poison filter. "
            "Subcommands: register | lookup | candidates | duel | tournament | "
            "ratings | elites | leaderboard | anchor | verify-anchor | distill."
        ),
    )
    p_forge.add_argument(
        "forge_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the Forge CLI (e.g. 'leaderboard').",
    )
    p_forge.set_defaults(func=_cmd_forge)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
