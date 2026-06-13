"""Standalone federation CLI (delegated from ``hermes_cli.jarvis_prime``).

Usage: ``python -m hermes_cli.jarvis_prime federation <subcommand> ...`` or
directly via :func:`cli_main`. Everything is file-based and local-first;
exit code 1 signals a refusal (divergence, locked amendment, unsatisfied
quorum), 2 a usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from . import FederationError
from .amendment import AmendmentProposal, evaluate_amendment
from .attestation import AttestationBundle, FederationRegistry, attest_local, detect_divergence
from .compliance_matrix import generate_evidence_package
from .identity import init_identity, load_identity
from .quorum_auth import (
    QuorumChallenge,
    QuorumPolicy,
    create_quorum_challenge,
    finalize,
    is_satisfied,
    respond,
)
from .scaling import EVALUATION_MATRIX, ScaleSignals, recommend_scale
from .sovereignty import compute_sovereignty_index
from .trust_ladder import ContributorStore, promote_to_maintainer
from .forge_intake import evaluate_contribution
from .attestation import ArtifactAttestation


def _emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cmd_identity(args: argparse.Namespace) -> int:
    if args.identity_cmd == "init":
        identity = init_identity(args.name)
        _emit(identity.to_dict(), args.json)
        return 0
    identity = load_identity()
    if identity is None:
        print("no node identity — run: federation identity init --name <name>", file=sys.stderr)
        return 1
    _emit(identity.to_dict(), args.json)
    return 0


def _cmd_attest(args: argparse.Namespace) -> int:
    identity = load_identity()
    if identity is None:
        print("no node identity — run: federation identity init --name <name>", file=sys.stderr)
        return 1
    ledger = GuardrailLedger()
    try:
        bundle = attest_local(ledger, identity)
    except FederationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    if args.out:
        bundle.write(Path(args.out))
        print(f"wrote {args.out} (bundle_sha256={bundle.bundle_sha256})")
    else:
        _emit(bundle.to_dict(), True)
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    registry = FederationRegistry(Path(args.registry) if args.registry else None)
    ledger = GuardrailLedger()
    try:
        bundle = AttestationBundle.read(Path(args.bundle))
        record = registry.record(bundle, ledger=ledger, allow_divergent=args.allow_divergent)
    except FederationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    _emit(record.to_dict(), args.json)
    return 0


def _cmd_peers(args: argparse.Namespace) -> int:
    registry = FederationRegistry(Path(args.registry) if args.registry else None)
    peers = [p.to_dict() for p in registry.peers()]
    _emit(peers if args.json else f"{len(peers)} peer(s)", args.json)
    if not args.json:
        for peer in peers:
            print(f"  {peer['node_id']}  {peer['display_name']}  heads={peer['heads']}")
    return 0


def _cmd_diverge(args: argparse.Namespace) -> int:
    registry = FederationRegistry(Path(args.registry) if args.registry else None)
    try:
        bundle = AttestationBundle.read(Path(args.bundle))
    except FederationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    findings = detect_divergence(registry, bundle)
    _emit([f.to_dict() for f in findings], True)
    return 1 if findings else 0


def _cmd_quorum(args: argparse.Namespace) -> int:
    if args.quorum_cmd == "create":
        signers = tuple(s.strip() for s in (args.signers or "owner").split(",") if s.strip())
        policy = QuorumPolicy(threshold=args.threshold, signers=signers)
        try:
            challenge = create_quorum_challenge(
                args.action, policy=policy, rationale=args.rationale or ""
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        Path(args.out).write_text(
            json.dumps(challenge.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"wrote {args.out} ({challenge.quorum_id}); per-signer phrases inside")
        return 0

    challenge = QuorumChallenge.from_dict(_load_json(args.file))
    if args.quorum_cmd == "respond":
        grant = respond(challenge, args.signer, args.phrase)
        Path(args.file).write_text(
            json.dumps(challenge.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        if grant is None:
            print("refused: phrase/nonce mismatch, unknown signer, or expired", file=sys.stderr)
            return 1
        print(f"signer {args.signer} granted ({len(challenge.grants)}/{challenge.policy.threshold})")
        return 0
    if args.quorum_cmd == "status":
        _emit(
            {
                "quorum_id": challenge.quorum_id,
                "action": challenge.action,
                "threshold": challenge.policy.threshold,
                "granted": sorted(challenge.grants),
                "satisfied": is_satisfied(challenge),
                "expires_at": challenge.expires_at,
            },
            args.json,
        )
        return 0
    # finalize
    ledger = GuardrailLedger()
    grant = finalize(challenge, ledger=ledger)
    if grant is None:
        print("refused: quorum not satisfied or challenge expired", file=sys.stderr)
        return 1
    _emit(grant.to_dict(), args.json)
    if args.kill:
        if challenge.action != "emergency_stop":
            print("--kill is only valid for the emergency_stop action", file=sys.stderr)
            return 2
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        runtime = JarvisPrime()
        runtime.stop(reason=f"quorum_kill:{grant.quorum_id}")
        print("emergency stop executed under quorum grant")
    return 0


def _cmd_amend(args: argparse.Namespace) -> int:
    proposal = AmendmentProposal.from_dict(_load_json(args.proposal))
    decision = evaluate_amendment(proposal, ledger=GuardrailLedger())
    _emit(decision.to_dict(), args.json)
    return 0 if decision.allowed else 1


def _cmd_trust(args: argparse.Namespace) -> int:
    store = ContributorStore()
    if args.trust_cmd == "show":
        if args.contributor:
            _emit(store.get(args.contributor).to_dict(), args.json)
        else:
            _emit([r.to_dict() for r in store.all()], True)
        return 0
    if args.trust_cmd == "outcome":
        record = store.record_outcome(
            args.contributor,
            accepted=args.accepted,
            fatal=args.fatal,
            ledger=GuardrailLedger(),
        )
        _emit(record.to_dict(), args.json)
        return 0
    # promote — requires a serialized grant file produced by quorum finalize.
    grant_data = _load_json(args.grant)
    from .quorum_auth import QuorumGrant

    grant = QuorumGrant(
        quorum_id=str(grant_data.get("quorum_id", "")),
        action=str(grant_data.get("action", "")),
        subject=str(grant_data.get("subject", "")),
        risk_class=str(grant_data.get("risk_class", "RC3")),
        threshold=int(grant_data.get("threshold", 1)),
        signer_ids=tuple(grant_data.get("signer_ids", ())),
        granted_at=str(grant_data.get("granted_at", "")),
    )
    try:
        record = promote_to_maintainer(
            store.get(args.contributor), grant, store=store, ledger=GuardrailLedger()
        )
    except FederationError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    _emit(record.to_dict(), args.json)
    return 0


def _cmd_intake(args: argparse.Namespace) -> int:
    trajectory = _load_json(args.trajectory)
    store = ContributorStore()
    attestation = None
    if args.attestation:
        attestation = ArtifactAttestation.from_dict(_load_json(args.attestation))
    decision = evaluate_contribution(
        trajectory,
        contributor=store.get(args.contributor),
        verifier_passed=args.verifier_passed,
        attestation=attestation,
        store=store,
        ledger=GuardrailLedger(),
    )
    _emit(decision.to_dict(), args.json)
    return 0 if decision.admitted else 1


def _cmd_scale(args: argparse.Namespace) -> int:
    if args.scale_cmd == "matrix":
        _emit({s.value: row for s, row in EVALUATION_MATRIX.items()}, args.json)
        return 0
    signals = (
        ScaleSignals.from_dict(_load_json(args.signals)) if args.signals else ScaleSignals()
    )
    rec = recommend_scale(signals, ledger=GuardrailLedger() if args.record else None)
    if args.json:
        _emit(rec.to_dict(), True)
    else:
        print(f"recommended scale: {rec.recommended.value}")
        for step in rec.decision_path:
            print(f"  {step}")
        print(f"rationale: {rec.rationale}")
    return 0


def _cmd_sovereignty(args: argparse.Namespace) -> int:
    report = compute_sovereignty_index(
        registry=FederationRegistry(), record=args.record
    )
    if args.json:
        _emit(report.to_dict(), True)
    else:
        print(f"sovereignty index: {report.score:.2f}")
        for check in report.checks:
            mark = "ok " if check.passed else "FAIL"
            print(f"  [{mark}] {check.check_id}: {check.detail}")
    return 0 if report.score == 1.0 else 1


def _cmd_compliance(args: argparse.Namespace) -> int:
    framework = args.framework.replace("-", "_")
    try:
        package = generate_evidence_package(framework, registry=FederationRegistry())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        package.write(Path(args.out))
        print(f"wrote {args.out} (package_sha256={package.package_sha256})")
    else:
        _emit(package.to_dict(), True)
    return 0


def cli_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime federation",
        description="Sovereign-node federation, quorum governance, scaling & compliance",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_id = sub.add_parser("identity", help="Node identity (init/show)")
    id_sub = p_id.add_subparsers(dest="identity_cmd", required=True)
    p_id_init = id_sub.add_parser("init", help="Create this node's identity")
    p_id_init.add_argument("--name", required=True)
    p_id_init.add_argument("--json", action="store_true")
    p_id_show = id_sub.add_parser("show", help="Show this node's identity")
    p_id_show.add_argument("--json", action="store_true")
    p_id.set_defaults(func=_cmd_identity)

    p_attest = sub.add_parser("attest", help="Attest the local ledger head to a bundle file")
    p_attest.add_argument("--out", default="")
    p_attest.set_defaults(func=_cmd_attest)

    p_import = sub.add_parser("import", help="Import a peer attestation bundle")
    p_import.add_argument("bundle")
    p_import.add_argument("--registry", default="")
    p_import.add_argument("--allow-divergent", action="store_true")
    p_import.add_argument("--json", action="store_true")
    p_import.set_defaults(func=_cmd_import)

    p_peers = sub.add_parser("peers", help="List cross-attesting peers")
    p_peers.add_argument("--registry", default="")
    p_peers.add_argument("--json", action="store_true")
    p_peers.set_defaults(func=_cmd_peers)

    p_div = sub.add_parser("diverge", help="Check a bundle for divergence without recording")
    p_div.add_argument("bundle")
    p_div.add_argument("--registry", default="")
    p_div.set_defaults(func=_cmd_diverge)

    p_q = sub.add_parser("quorum", help="M-of-N threshold authorization")
    q_sub = p_q.add_subparsers(dest="quorum_cmd", required=True)
    p_qc = q_sub.add_parser("create", help="Mint a quorum challenge file")
    p_qc.add_argument("--action", required=True)
    p_qc.add_argument("--signers", default="owner", help="Comma-separated signer ids")
    p_qc.add_argument("--threshold", type=int, default=1)
    p_qc.add_argument("--rationale", default="")
    p_qc.add_argument("--out", default="quorum.json")
    for name, extra in (("respond", True), ("status", False), ("finalize", False)):
        p_qx = q_sub.add_parser(name)
        p_qx.add_argument("--file", required=True)
        p_qx.add_argument("--json", action="store_true")
        if extra:
            p_qx.add_argument("--signer", required=True)
            p_qx.add_argument("--phrase", required=True)
        if name == "finalize":
            p_qx.add_argument("--kill", action="store_true")
    p_q.set_defaults(func=_cmd_quorum)

    p_amend = sub.add_parser("amend", help="Adjudicate a constitution amendment proposal")
    amend_sub = p_amend.add_subparsers(dest="amend_cmd", required=True)
    p_ae = amend_sub.add_parser("evaluate")
    p_ae.add_argument("--proposal", required=True)
    p_ae.add_argument("--json", action="store_true")
    p_amend.set_defaults(func=_cmd_amend)

    p_trust = sub.add_parser("trust", help="Contributor trust ladder")
    trust_sub = p_trust.add_subparsers(dest="trust_cmd", required=True)
    p_ts = trust_sub.add_parser("show")
    p_ts.add_argument("--contributor", default="")
    p_ts.add_argument("--json", action="store_true")
    p_to = trust_sub.add_parser("outcome")
    p_to.add_argument("--contributor", required=True)
    group = p_to.add_mutually_exclusive_group(required=True)
    group.add_argument("--accepted", dest="accepted", action="store_true")
    group.add_argument("--rejected", dest="accepted", action="store_false")
    p_to.add_argument("--fatal", action="store_true")
    p_to.add_argument("--json", action="store_true")
    p_tp = trust_sub.add_parser("promote")
    p_tp.add_argument("--contributor", required=True)
    p_tp.add_argument("--grant", required=True)
    p_tp.add_argument("--json", action="store_true")
    p_trust.set_defaults(func=_cmd_trust)

    p_intake = sub.add_parser("intake", help="Evaluate a contributed trajectory (poison filter)")
    intake_sub = p_intake.add_subparsers(dest="intake_cmd", required=True)
    p_ie = intake_sub.add_parser("evaluate")
    p_ie.add_argument("--trajectory", required=True)
    p_ie.add_argument("--contributor", required=True)
    p_ie.add_argument("--attestation", default="")
    p_ie.add_argument("--verifier-passed", action="store_true")
    p_ie.add_argument("--json", action="store_true")
    p_intake.set_defaults(func=_cmd_intake)

    p_scale = sub.add_parser("scale", help="Scaling decision tree + evaluation matrix")
    scale_sub = p_scale.add_subparsers(dest="scale_cmd", required=True)
    p_sr = scale_sub.add_parser("recommend")
    p_sr.add_argument("--signals", default="")
    p_sr.add_argument("--record", action="store_true")
    p_sr.add_argument("--json", action="store_true")
    p_sm = scale_sub.add_parser("matrix")
    p_sm.add_argument("--json", action="store_true")
    p_scale.set_defaults(func=_cmd_scale)

    p_sov = sub.add_parser("sovereignty", help="Compute the sovereignty index")
    p_sov.add_argument("--record", action="store_true")
    p_sov.add_argument("--json", action="store_true")
    p_sov.set_defaults(func=_cmd_sovereignty)

    p_comp = sub.add_parser("compliance", help="Compliance evidence package")
    comp_sub = p_comp.add_subparsers(dest="compliance_cmd", required=True)
    p_ce = comp_sub.add_parser("export")
    p_ce.add_argument(
        "--framework",
        default="all",
        choices=["eu-ai-act", "eu_ai_act", "soc2", "iso27001", "all"],
    )
    p_ce.add_argument("--out", default="")
    p_comp.set_defaults(func=_cmd_compliance)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
