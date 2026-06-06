"""CLI for the research fabric — ``python -m hermes_cli.jarvis_prime.research_fabric``.

Subcommands:

* ``charter challenge`` — mint a nonce-bound owner challenge (prints the exact
  phrase to echo).
* ``charter grant``     — answer the challenge to mint an Autonomy Charter.
* ``charter revoke``    — revoke a charter by id.
* ``charter status``    — show the active charter / all charters.
* ``validate``          — run the strict ratchet against the current champion.
* ``champion show``     — show the current champion.
* ``run``               — dry-run a candidate through the full envelope.
* ``report``            — ledger + champion + charter + chain verification.
* ``inventory``         — print the registered model/benchmark/dataset catalog.

Auto-apply is never performed by the CLI: ``run`` is always a dry-run because no
``applier`` is injected here (live apply is a programmatic path, charter-gated).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailEvidenceBundle, hermes_home
from hermes_cli.jarvis_prime.owner_auth import (
    OwnerAuthorizationChallenge,
    authorize_challenge,
    create_challenge,
)
from hermes_cli.jarvis_prime.self_update import ProposalKind

from .apply import GitApplier, GitRollback
from .catalog import candidate_dicts
from .charter import CharterBook, CharterRejected, DEFAULT_ALLOWED_KINDS
from .pipeline import open_context, report_payload
from .selfplay.evolve import evolve
from .selfplay.loop import run_selfplay
from .selfplay.tasks import (
    DEMO_BASELINE_CODE,
    DEMO_EVOLVE_TASK,
    SEED_TASKS,
    demo_variant_proposer,
    reference_solver,
)
from .validators import evaluate_ratchet
from .verifier import Candidate


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _resolve_owner_phrase(args: argparse.Namespace) -> Optional[str]:
    phrase = getattr(args, "phrase", None)
    if phrase is None:
        phrase = os.environ.get("JARVIS_OWNER_PHRASE")
    return phrase


def _challenge_store_path() -> Path:
    return hermes_home() / "jarvis_prime" / "charter_challenges.jsonl"


def _save_challenge(ch: OwnerAuthorizationChallenge, extra: dict[str, Any]) -> None:
    p = _challenge_store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"challenge": ch.to_dict(), "charter_params": extra}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def _load_challenge(challenge_id: str) -> Optional[dict[str, Any]]:
    p = _challenge_store_path()
    if not p.exists():
        return None
    found: Optional[dict[str, Any]] = None
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("challenge", {}).get("challenge_id") == challenge_id:
            found = rec
    return found


# --------------------------------------------------------------------------
# charter
# --------------------------------------------------------------------------


def _cmd_charter_challenge(args: argparse.Namespace) -> int:
    kinds = tuple(args.allowed_kinds or DEFAULT_ALLOWED_KINDS)
    # Refuse to even mint a challenge for hard-walled kinds.
    try:
        ch = create_challenge(
            "grant_autonomy_charter",
            risk_class="RC3",
            rationale=f"autonomy charter for kinds={list(kinds)} ceiling={args.risk_ceiling}",
            subject="research_fabric_autonomy",
            ttl_seconds=args.challenge_ttl,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    params = {
        "allowed_kinds": list(kinds),
        "risk_band_ceiling": args.risk_ceiling,
        "per_window_budget": args.budget,
        "window_seconds": args.window_seconds,
        "ttl_seconds": args.ttl,
    }
    _save_challenge(ch, params)
    _print(
        {
            "challenge_id": ch.challenge_id,
            "required_phrase": ch.required_phrase,
            "expires_at": ch.expires_at,
            "charter_params": params,
            "next": "research-fabric charter grant --challenge-id <id> --phrase '<required_phrase>'",
        }
    )
    return 0


def _cmd_charter_grant(args: argparse.Namespace) -> int:
    phrase = _resolve_owner_phrase(args)
    if not phrase:
        print("error: --phrase (or JARVIS_OWNER_PHRASE) required", file=sys.stderr)
        return 1
    rec = _load_challenge(args.challenge_id)
    if rec is None:
        print(f"error: unknown challenge id {args.challenge_id!r}", file=sys.stderr)
        return 1
    challenge = OwnerAuthorizationChallenge.from_dict(rec["challenge"])
    grant = authorize_challenge(challenge, phrase)
    if grant is None:
        print(
            "error: phrase did not match the nonce-bound required_phrase "
            "(or challenge expired)",
            file=sys.stderr,
        )
        return 1
    params = rec["charter_params"]
    book = CharterBook.load(getattr(args, "charter_path", None))
    try:
        charter = book.grant(
            allowed_kinds=tuple(params["allowed_kinds"]),
            risk_band_ceiling=params["risk_band_ceiling"],
            per_window_budget=int(params["per_window_budget"]),
            window_seconds=int(params["window_seconds"]),
            ttl_seconds=int(params["ttl_seconds"]),
            grant=grant,
        )
    except CharterRejected as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print({"granted": charter.to_dict()})
    return 0


def _cmd_charter_revoke(args: argparse.Namespace) -> int:
    book = CharterBook.load(getattr(args, "charter_path", None))
    ok = book.revoke(args.charter_id)
    _print({"charter_id": args.charter_id, "revoked": ok})
    return 0 if ok else 1


def _cmd_charter_status(args: argparse.Namespace) -> int:
    book = CharterBook.load(getattr(args, "charter_path", None))
    active = book.active()
    _print(
        {
            "active_charter": active.to_dict() if active else None,
            "all_charters": [c.to_dict() for c in book.charters],
        }
    )
    return 0


# --------------------------------------------------------------------------
# validate / champion / run / report / inventory
# --------------------------------------------------------------------------


def _parse_scores(raw: Optional[str]) -> dict[str, float]:
    if not raw:
        return {}
    data = json.loads(raw)
    return {str(k): float(v) for k, v in data.items()}


def _cmd_validate(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        champ = ctx.champions.current()
        verdict = evaluate_ratchet(
            champion_domain_scores=champ.domain_scores if champ else None,
            candidate_domain_scores=_parse_scores(args.scores),
            holdout_scores=_parse_scores(args.holdout),
            candidate_safety_counts=_parse_scores(args.safety),
            champion_safety_counts=champ.safety_counts if champ else None,
            eval_win_rate=args.eval_win_rate,
        )
        ctx.store.record_snapshot("validate", "ratchet", verdict.to_dict())
        _print(verdict.to_dict())
    finally:
        ctx.close()
    return 0


def _cmd_champion_show(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        champ = ctx.champions.current()
        _print({"champion": champ.to_dict() if champ else None})
    finally:
        ctx.close()
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    spec = json.loads(Path(args.candidate_json).read_text(encoding="utf-8"))
    repo_root = Path(args.repo_root).resolve()

    execute = bool(getattr(args, "execute", False))
    controller_kwargs: dict[str, Any] = {}
    if execute:
        # Live auto-apply path: charter-gated (the controller enforces an active
        # charter) + real git apply/rollback. Default gate runner = strict gates.
        controller_kwargs["applier"] = GitApplier(repo_root)
        controller_kwargs["rollback"] = GitRollback(repo_root)
        canary_scores = _to_floats(spec.get("canary_scores", {}))
        if canary_scores:
            controller_kwargs["canary"] = lambda _c, _s=canary_scores: {"domain_scores": _s}

    ctx = open_context(repo_root, **controller_kwargs)
    try:
        candidate = Candidate(
            candidate_id=str(spec.get("candidate_id", "cand")),
            kind=ProposalKind(spec.get("kind", "skill_update")),
            target_path=str(spec.get("target_path", "")),
            risk_class=str(spec.get("risk_class", "RC1")),
            domain_scores=_to_floats(spec.get("domain_scores", {})),
            holdout_scores=_to_floats(spec.get("holdout_scores", {})),
            safety_counts=_to_floats(spec.get("safety_counts", {})),
            eval_win_rate=spec.get("eval_win_rate"),
            ambition_scores=_to_floats(spec.get("ambition_scores", {})),
            diff_text=str(spec.get("diff_text", "")),
        )
        bundle = GuardrailEvidenceBundle(packet_id=candidate.candidate_id)
        packet = {"packet_id": candidate.candidate_id}
        outcome = ctx.controller.evaluate_and_apply(
            candidate, evidence_bundle=bundle, packet=packet, dry_run=not execute
        )
        _print(outcome.to_dict())
    finally:
        ctx.close()
    return 0


def _cmd_selfplay_run(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        result = run_selfplay(SEED_TASKS, reference_solver, ledger=ctx.ledger)
        _print(result.to_dict())
    finally:
        ctx.close()
    return 0


def _cmd_selfplay_evolve(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        result = evolve(
            DEMO_EVOLVE_TASK,
            DEMO_BASELINE_CODE,
            demo_variant_proposer,
            generations=args.generations,
            ledger=ctx.ledger,
        )
        _print(result.to_dict())
    finally:
        ctx.close()
    return 0


def _cmd_archive_list(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        rows = ctx.store.list_snapshots("champion_freeze")
        lineage = []
        for r in rows:
            payload = json.loads(r["payload_json"])
            champ = payload.get("champion", {})
            lineage.append(
                {
                    "champion_id": champ.get("champion_id"),
                    "composite": champ.get("composite"),
                    "frozen_at": champ.get("frozen_at"),
                    "reason": payload.get("reason"),
                    "rollback_handle": champ.get("rollback_handle"),
                }
            )
        _print({"lineage": lineage, "count": len(lineage)})
    finally:
        ctx.close()
    return 0


def _to_floats(d: dict[str, Any]) -> dict[str, float]:
    return {str(k): float(v) for k, v in d.items()}


def _cmd_report(args: argparse.Namespace) -> int:
    ctx = open_context(Path(args.repo_root))
    try:
        _print(report_payload(ctx))
    finally:
        ctx.close()
    return 0


def _cmd_inventory(args: argparse.Namespace) -> int:
    _print(candidate_dicts())
    return 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-fabric",
        description="Bounded-autonomous, verifier-gated self-improvement for hermes-agent.",
    )
    parser.add_argument("--repo-root", default=".", help="Path to the repo root.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # charter group
    p_ch = sub.add_parser("charter", help="Manage autonomy charters (owner-gated).")
    ch_sub = p_ch.add_subparsers(dest="charter_command", required=True)

    p_chal = ch_sub.add_parser("challenge", help="Mint a nonce-bound owner challenge.")
    p_chal.add_argument("--allowed-kinds", nargs="*", default=list(DEFAULT_ALLOWED_KINDS))
    p_chal.add_argument("--risk-ceiling", default="RC2")
    p_chal.add_argument("--budget", type=int, default=5)
    p_chal.add_argument("--window-seconds", type=int, default=86400)
    p_chal.add_argument("--ttl", type=int, default=86400, help="Charter lifetime (s).")
    p_chal.add_argument("--challenge-ttl", type=int, default=600, help="Challenge TTL (s).")
    p_chal.set_defaults(func=_cmd_charter_challenge)

    p_grant = ch_sub.add_parser("grant", help="Answer a challenge to mint a charter.")
    p_grant.add_argument("--challenge-id", required=True)
    p_grant.add_argument("--phrase", default=None)
    p_grant.set_defaults(func=_cmd_charter_grant)

    p_rev = ch_sub.add_parser("revoke", help="Revoke a charter.")
    p_rev.add_argument("--charter-id", required=True)
    p_rev.set_defaults(func=_cmd_charter_revoke)

    p_stat = ch_sub.add_parser("status", help="Show charter status.")
    p_stat.set_defaults(func=_cmd_charter_status)

    # validate
    p_val = sub.add_parser("validate", help="Run the ratchet against the champion.")
    p_val.add_argument("--scores", required=True, help="JSON: domain->score.")
    p_val.add_argument("--holdout", default=None, help="JSON: held-out domain->score.")
    p_val.add_argument("--safety", default=None, help="JSON: safety count name->value.")
    p_val.add_argument("--eval-win-rate", type=float, default=None)
    p_val.set_defaults(func=_cmd_validate)

    # champion
    p_champ = sub.add_parser("champion", help="Champion operations.")
    champ_sub = p_champ.add_subparsers(dest="champion_command", required=True)
    p_champ_show = champ_sub.add_parser("show", help="Show the current champion.")
    p_champ_show.set_defaults(func=_cmd_champion_show)

    # run
    p_run = sub.add_parser(
        "run",
        help="Run a candidate through the envelope (dry-run unless --execute).",
    )
    p_run.add_argument("--candidate-json", required=True, help="Path to a candidate spec JSON.")
    p_run.add_argument(
        "--execute",
        action="store_true",
        help="Live auto-apply via git (charter-gated; uses real GitApplier/rollback).",
    )
    p_run.set_defaults(func=_cmd_run)

    # selfplay
    p_sp = sub.add_parser("selfplay", help="Self-play curriculum operations.")
    sp_sub = p_sp.add_subparsers(dest="selfplay_command", required=True)
    p_sp_run = sp_sub.add_parser("run", help="Run the seed self-play loop (verifier-gated).")
    p_sp_run.set_defaults(func=_cmd_selfplay_run)
    p_sp_evolve = sp_sub.add_parser(
        "evolve", help="Evolve a correct baseline toward lower op-count (demo)."
    )
    p_sp_evolve.add_argument("--generations", type=int, default=5)
    p_sp_evolve.set_defaults(func=_cmd_selfplay_evolve)

    # archive
    p_arch = sub.add_parser("archive", help="Champion/challenger archive operations.")
    arch_sub = p_arch.add_subparsers(dest="archive_command", required=True)
    p_arch_list = arch_sub.add_parser("list", help="List champion lineage (promotions).")
    p_arch_list.set_defaults(func=_cmd_archive_list)

    # report
    p_rep = sub.add_parser("report", help="Ledger + champion + charter + chain check.")
    p_rep.set_defaults(func=_cmd_report)

    # inventory
    p_inv = sub.add_parser("inventory", help="Print the registered candidate catalog.")
    p_inv.set_defaults(func=_cmd_inventory)

    return parser


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(cli_main())
