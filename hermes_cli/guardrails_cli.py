"""``hermes guardrails`` — operate and inspect the verifiable guardrail subsystem.

Subcommands:

* ``status``           — ledger path, head hash, chain validity, pending owner
                         challenges, active worker leases, proposed-memory count.
* ``doctor``           — run the operational proof suite (ledger, strict gate,
                         owner challenge, secret scan, memory exclusion).
* ``verify-ledger``    — validate the hash chain and report any break.
* ``collect``          — collect git-diff / secret-scan / rollback evidence for a
                         packet JSON (optionally run its verification commands).
* ``authorize``        — mint a challenge and print the exact required phrase.
* ``authorize-response`` — answer a challenge; append the grant to the ledger.

Everything runs with no network and no credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def register(subparsers: Any) -> None:
    """Register the ``guardrails`` command group on ``subparsers``."""

    parser = subparsers.add_parser(
        "guardrails",
        help="Verifiable guardrails: evidence ledger, strict gates, owner challenges",
        description=(
            "Inspect and operate the verifiable guardrail subsystem: a "
            "tamper-evident decision ledger, evidence-bound strict gates, "
            "challenge-bound owner authorization, and a secret scanner. Gates "
            "pass only on captured evidence, never on a packet's self-attestation."
        ),
    )
    sub = parser.add_subparsers(dest="guardrails_command")

    p_status = sub.add_parser("status", help="Show guardrail subsystem status")
    p_status.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Prove the guardrails are operational")
    p_doctor.add_argument("--json", action="store_true")

    p_verify = sub.add_parser("verify-ledger", help="Validate the ledger hash chain")
    p_verify.add_argument("--json", action="store_true")

    p_collect = sub.add_parser("collect", help="Collect evidence for a packet JSON")
    p_collect.add_argument("--packet", required=True, help="Path to a packet JSON file")
    p_collect.add_argument(
        "--run-tests",
        action="store_true",
        help="Execute the packet's (allowlisted) verification commands",
    )
    p_collect.add_argument("--json", action="store_true")

    p_auth = sub.add_parser("authorize", help="Mint an owner-authorization challenge")
    p_auth.add_argument("action", help="Owner-gated action category")
    p_auth.add_argument("--subject", default="", help="What the action applies to")
    p_auth.add_argument("--rationale", default="", help="Why it is being requested")
    p_auth.add_argument("--json", action="store_true")

    p_resp = sub.add_parser(
        "authorize-response", help="Answer a challenge with the exact phrase"
    )
    p_resp.add_argument("challenge_id", help="Challenge id from `authorize`")
    p_resp.add_argument("phrase", help='The exact required phrase (incl. "Code: NNNNNN")')
    p_resp.add_argument("--json", action="store_true")

    p_reseal = sub.add_parser(
        "reseal",
        help="Archive a broken ledger and start a fresh sealed chain (never rewrites history)",
    )
    p_reseal.add_argument(
        "--force",
        action="store_true",
        help="Reseal even if the current chain already verifies",
    )
    p_reseal.add_argument("--json", action="store_true")

    parser.set_defaults(func=cmd_guardrails)


# ---------------------------------------------------------------------------


def cmd_guardrails(args: Any) -> None:
    action = getattr(args, "guardrails_command", None)
    if action == "status":
        _emit(_status(), args)
    elif action == "doctor":
        report = _doctor()
        _emit(report, args)
        raise SystemExit(0 if report["ok"] else 1)
    elif action == "verify-ledger":
        diag = _verify_ledger()
        _emit(diag, args)
        raise SystemExit(0 if diag["ok"] else 1)
    elif action == "collect":
        _emit(_collect(args), args)
    elif action == "authorize":
        _emit(_authorize(args), args)
    elif action == "authorize-response":
        result = _authorize_response(args)
        _emit(result, args)
        raise SystemExit(0 if result.get("authorized") else 1)
    elif action == "reseal":
        result = _reseal(force=bool(getattr(args, "force", False)))
        _emit(result, args)
        raise SystemExit(0 if result.get("ok") else 1)
    else:
        print(
            "usage: hermes guardrails "
            "{status|doctor|verify-ledger|collect|authorize|authorize-response|reseal}"
        )
        raise SystemExit(2)
    raise SystemExit(0)


def _emit(data: dict, args: Any) -> None:
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(_render(data))


def _render(data: dict) -> str:
    lines = []
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{key}:")
            lines.append(json.dumps(value, indent=2, default=str))
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


def _status() -> dict:
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    ledger = GuardrailLedger()
    diag = ledger.verify_chain()
    out: dict[str, Any] = {
        "ledger_path": str(ledger.path),
        "ledger_exists": ledger.path.exists(),
        "ledger_records": diag.length,
        "ledger_head_hash": diag.head_hash,
        "chain_ok": diag.ok,
        "chain_reason": diag.reason,
    }
    try:
        from hermes_cli.jarvis_prime import worker_locks as wl

        out["active_branch_leases"] = [
            {"branch": l.branch, "worker": l.worker} for l in wl.list_leases()
        ]
    except Exception:
        out["active_branch_leases"] = []
    try:
        from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore

        out["memory_proposed_count"] = len(MemoryTreeStore().proposed())
    except Exception:
        out["memory_proposed_count"] = None
    return out


def _verify_ledger() -> dict:
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    return GuardrailLedger().verify_chain().to_dict()


def _reseal(*, force: bool = False) -> dict:
    """Archive a broken (or force-resealed) ledger and seed a fresh chain.

    Never rewrites historical hashes. The broken file is renamed beside the
    active ledger; a genesis decision record documents the break.
    """
    from datetime import datetime, timezone
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    ledger = GuardrailLedger()
    diag = ledger.verify_chain()
    if diag.ok and not force:
        return {
            "ok": True,
            "resealed": False,
            "reason": "chain already intact; pass --force to reseal anyway",
            **diag.to_dict(),
        }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = ledger.path.with_name(f"guardrail_ledger.broken-{ts}.jsonl")
    broken_at = diag.broken_at
    reason = diag.reason
    length = diag.length
    if ledger.path.exists():
        ledger.path.replace(archive)
    # Fresh empty path — append genesis documentation record
    fresh = GuardrailLedger(path=ledger.path)
    fresh.append(
        "ledger_reseal",
        subject="guardrail_ledger",
        payload={
            "archived_path": str(archive),
            "previous_broken_at": broken_at,
            "previous_reason": reason,
            "previous_length": length,
            "forced": force,
            "note": "History was archived, not rewritten.",
        },
    )
    new_diag = fresh.verify_chain()
    return {
        "ok": bool(new_diag.ok),
        "resealed": True,
        "archived_path": str(archive),
        "previous_broken_at": broken_at,
        "previous_reason": reason,
        **new_diag.to_dict(),
    }


def _authorize(args: Any) -> dict:
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
    from hermes_cli.jarvis_prime.owner_auth import create_challenge

    try:
        challenge = create_challenge(
            args.action,
            rationale=getattr(args, "rationale", ""),
            subject=getattr(args, "subject", ""),
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    # Persist the challenge (minus the nonce echo is impossible — the challenge
    # itself is not a secret; only the owner's *response* proves authorization).
    try:
        GuardrailLedger().append(
            "owner_authorization_challenge", challenge.action, challenge.to_dict()
        )
    except Exception:
        pass
    return {
        "ok": True,
        "challenge_id": challenge.challenge_id,
        "action": challenge.action,
        "subject": challenge.subject,
        "expires_at": challenge.expires_at,
        "required_phrase": challenge.required_phrase,
        "instructions": (
            "Reply with: hermes guardrails authorize-response "
            f"{challenge.challenge_id} \"{challenge.required_phrase}\""
        ),
    }


def _authorize_response(args: Any) -> dict:
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
    from hermes_cli.jarvis_prime.owner_auth import (
        OwnerAuthorizationChallenge,
        authorize_challenge,
    )

    ledger = GuardrailLedger()
    # Recover the challenge from the ledger (stateless verification).
    challenge = None
    for record in reversed(ledger.read_all()):
        if (
            record.kind == "owner_authorization_challenge"
            and record.payload.get("challenge_id") == args.challenge_id
        ):
            challenge = OwnerAuthorizationChallenge.from_dict(dict(record.payload))
            break
    if challenge is None:
        return {"ok": False, "authorized": False, "error": "unknown challenge id"}

    grant = authorize_challenge(challenge, args.phrase)
    if grant is None:
        return {
            "ok": True,
            "authorized": False,
            "reason": "wrong/expired phrase — authorization not granted",
        }
    record = ledger.append(
        "owner_authorization_grant", grant.subject or grant.action, grant.to_dict()
    )
    return {
        "ok": True,
        "authorized": True,
        "grant": grant.to_dict(),
        "ledger_record_hash": record.record_hash,
    }


def _collect(args: Any) -> dict:
    from hermes_cli.jarvis_prime import guardrail_collectors as gc

    packet_path = Path(args.packet)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    repo_root = str(packet.get("repo_root") or ".")
    allowed = packet.get("allowed_files") or packet.get("planned_allowed_files") or []
    protected = packet.get("forbidden_files") or []
    commands = (
        packet.get("planned_verification_commands")
        or packet.get("verification_plan")
        or []
    )
    rollback = packet.get("planned_rollback") or packet.get("rollback_plan") or []
    # The acting agent that authored the change, if the packet carries it (same
    # identity namespace as a review's reviewer_id). Absent ⇒ the C19 gate fails
    # open (see strict_review_gate). Wiring this end-to-end from the orchestrator
    # is a follow-up; reading it here means any caller that already knows it wins.
    author_id = str(
        packet.get("acting_agent_id") or packet.get("author_id") or ""
    ).strip()
    # Planned reviewer identity (an ASSIGNMENT, not a verdict — no review has run
    # at collect time). Same identity namespace as author_id, for the strict
    # review gate's Clause C19 builder ≠ reviewer check.
    reviewer_id = str(
        packet.get("reviewer_worker") or packet.get("reviewer_id") or ""
    ).strip()

    diff_art = gc.collect_git_diff_evidence(
        repo_root, allowed, protected, author_id=author_id
    )
    changed = list(diff_art.payload.get("changed_files") or [])
    scan_art = gc.collect_secret_scan_evidence(repo_root, changed or list(allowed))
    rollback_art = gc.collect_rollback_evidence(
        repo_root,
        rollback,
        changed_files=changed,
        branch=str(diff_art.payload.get("branch") or ""),
    )
    artifacts = [diff_art, scan_art, rollback_art]
    # When a reviewer is genuinely assigned, record a NON-approving reviewer-
    # assignment artifact so C19's builder ≠ reviewer identity check is reachable.
    # It fixes the verdict to ``needs_owner`` (never a spurious PASS) — a real
    # approve/request_changes verdict must still come from an actual review step.
    # No reviewer assigned ⇒ nothing is added and behavior is unchanged.
    review_art = gc.collect_reviewer_assignment_evidence(
        reviewer_id, diff_hash=str(diff_art.payload.get("head_commit") or "")
    )
    if review_art is not None:
        artifacts.append(review_art)
    if getattr(args, "run_tests", False):
        artifacts.extend(gc.collect_test_evidence(repo_root, commands, run=True))
    return {
        "ok": True,
        "packet_id": packet.get("packet_id"),
        "artifacts": [a.to_dict() for a in artifacts],
    }


def _doctor() -> dict:
    """Operational proof suite — reuses launch_doctor's guardrail checks plus a
    memory-exclusion proof."""

    from hermes_cli.jarvis_prime import launch_doctor as ld

    checks = [
        ld._check_guardrail_ledger_writable(),
        ld._check_guardrail_ledger_verifies(),
        ld._check_strict_gate_rejects_self_attestation(),
        ld._check_owner_challenge_nonce_enforced(),
        ld._check_secret_scan_operational(),
        ld._check_emergency_stop_journaled(),
        ld._check_packet_id_stable(),
        _check_memory_proposed_excluded(),
    ]
    results = [
        {"name": c.name, "status": c.status, "detail": c.detail} for c in checks
    ]
    ok = all(c.status == ld.PASS for c in checks)
    return {"ok": ok, "checks": results}


def _check_memory_proposed_excluded():
    """Prove a proposed memory item never enters live recall before approval."""

    from hermes_cli.jarvis_prime import launch_doctor as ld

    try:
        from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryTreeStore(path=Path(tmp) / "tree.jsonl")
            # Use a distinctive content token ("xylophone") that does NOT appear
            # in the recall query, so a match can only come from leaked content,
            # not the query echo in the context-pack header.
            res = store.write(
                "owner keeps a xylophone in the cockpit",
                namespace="prefs",
                title="ui",
            )
            if not res.ok or res.node is None:
                return ld.LaunchCheck(
                    "memory_proposed_excluded",
                    ld.WARN,
                    "could not stage a proposed memory item",
                    hard=False,
                )
            pack = store.context_pack(
                "cockpit", token_budget=256, include_contested=False
            )
            text = pack.render()
            if "xylophone" in str(text):
                return ld.LaunchCheck(
                    "memory_proposed_excluded",
                    ld.FAIL,
                    "proposed memory leaked into live recall before approval",
                )
            # And the item is preserved (still pending), not dropped.
            preserved = any(n.id == res.node.id for n in store.proposed())
            if not preserved:
                return ld.LaunchCheck(
                    "memory_proposed_excluded",
                    ld.FAIL,
                    "proposed memory was dropped instead of held for approval",
                )
        return ld.LaunchCheck(
            "memory_proposed_excluded",
            ld.PASS,
            "proposed memory held for approval, excluded from live recall",
        )
    except Exception as exc:
        return ld.LaunchCheck(
            "memory_proposed_excluded", ld.WARN, f"check skipped: {exc}", hard=False
        )


__all__ = ["register", "cmd_guardrails"]
