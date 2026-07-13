"""
muse_delegate_dispatcher.py — the host-side wiring that finishes the MUSE ↔ n8n sync.

WHERE THIS SITS
---------------
    perceive → classify → decide → gate (AXIOM) → [delegate] → speak
                                                      ▲
                                                      └── this module

`JarvisPrime.delegate(route, packet)` (hermes_cli/jarvis_prime/runtime.py) builds a
delegation *envelope* but deliberately does not dispatch — "returns a dict the caller
hands to the orchestrator/model_router." This module is that caller for the n8n lane.
It takes the envelope, re-checks the two things a real-world side effect must never
skip — (1) the verification gate passed, (2) any owner authorization is present and
exact — then calls `N8nBridge.trigger_workflow(...)` and appends every attempt to the
hash-chained GuardrailLedger.

INVARIANT
---------
*Intelligence proposes; the verifier disposes.* This module never re-decides whether an
action is a good idea and never relaxes a gate. It refuses on gate failure or missing
owner phrase; it does not "try anyway."

LEDGER
------
Every attempt (allow, refuse, success, failure) is appended to the same hash-chained
ledger MUSE already uses: GuardrailLedger.append(kind, subject, payload) →
$HERMES_HOME/jarvis_prime/guardrail_ledger.jsonl (mode 0600, O_APPEND). If the real
GuardrailLedger cannot be imported (running standalone), a byte-compatible local
hash-chain fallback writes the same on-disk shape so nothing is lost.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

try:  # package-relative first, then flat import
    from .muse_n8n_bridge import N8nBridge, N8nError, N8nResult
except Exception:  # pragma: no cover - flat layout / direct run
    from muse_n8n_bridge import N8nBridge, N8nError, N8nResult  # type: ignore

# ── contracts mirrored from the live runtime (single source of truth there) ──
# hermes_cli/jarvis_prime/owner_auth.py::AUTHORIZATION_PHRASE
AUTHORIZATION_PHRASE = "Yes, with authorization."

# hermes_cli/jarvis_prime/owner_auth.py::OWNER_GATED_ACTIONS
OWNER_GATED_ACTIONS = frozenset({
    "spend_money", "post_publicly", "create_third_party_account", "oauth_change",
    "credential_change", "production_deploy", "dns_change", "force_push",
    "package_publish", "app_store_submission", "delete_recovered_sources",
    "modify_secrets", "change_default_active_agents", "registry_mutation",
    "regulated_claim", "grant_autonomy_charter",
})

# action → n8n connector webhook path (extend as connectors are built)
CONNECTOR_ROUTES = {
    "send_email": "muse-connector-gmail-send",
    "post_message": "muse-connector-slack-post",
    "post_publicly": "muse-connector-slack-post",
}


class DelegationRefused(RuntimeError):
    """Raised when a delegation is refused by a gate or a missing owner authorization."""


# ── hash-chained ledger writer (real GuardrailLedger, else byte-compatible fallback) ──
def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class _LocalHashChainLedger:
    """Fallback that reproduces guardrail_evidence.GuardrailLedger's on-disk format."""

    def __init__(self, path: Optional[str] = None):
        home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
        self.path = path or os.path.join(home, "jarvis_prime", "guardrail_ledger.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _latest_hash(self) -> str:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                last = None
                for line in fh:
                    line = line.strip()
                    if line:
                        last = line
                if last:
                    return json.loads(last).get("record_hash", "0" * 64)
        except FileNotFoundError:
            pass
        return "0" * 64

    def append(self, kind: str, subject: str, payload: dict) -> dict:
        record = {
            "record_id": uuid.uuid4().hex,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": kind,
            "subject": subject,
            "payload": payload,
            "previous_record_hash": self._latest_hash(),
        }
        record["record_hash"] = hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.path, flags, 0o600)
        try:
            os.write(fd, (json.dumps(record) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        return record


def _resolve_ledger():
    """Prefer the real GuardrailLedger; fall back to the byte-compatible local chain."""
    try:  # the real hash chain used across the runtime
        from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger  # type: ignore
        return GuardrailLedger()
    except Exception:
        return _LocalHashChainLedger()


class LedgerWriter:
    """Adapts GuardrailLedger.append(kind, subject, payload) to the bridge's
    ledger_writer: Callable[[dict], None]. This is the arity adapter the Stage-1
    prototype's `ledger_writer=axiom_ledger.append` illustration never supplied."""

    def __init__(self, ledger=None, kind: str = "n8n_delegation"):
        self._ledger = ledger or _resolve_ledger()
        self._kind = kind

    def __call__(self, record: dict) -> None:
        subject = record.get("webhook_path") or record.get("subject") or ""
        self._ledger.append(self._kind, subject, record)

    def latest_hash(self) -> Optional[str]:
        for meth in ("latest_hash", "_latest_hash"):
            fn = getattr(self._ledger, meth, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    return None
        return None


@dataclass
class Decision:
    allowed: bool
    reason: str
    connector_path: Optional[str] = None
    idempotency_key: Optional[str] = None
    verified_by: Optional[str] = None


@dataclass
class DelegateDispatcher:
    """Dispatches AXIOM-approved actions to the n8n connector layer."""

    n8n_base_url: str = "http://localhost:5678"
    ledger_writer: Optional[Callable[[dict], None]] = None
    timeout_s: float = 15.0
    max_retries: int = 2

    def __post_init__(self):
        if self.ledger_writer is None:
            self.ledger_writer = LedgerWriter()

    # -- pure decision, no network — the gate/owner check --
    def plan(
        self,
        action: str,
        *,
        idempotency_key: str,
        verified_by: str,
        gate_passed: bool = True,
        requires_owner_authorization: bool = False,
        owner_authorization: str = "",
        connector: Optional[str] = None,
    ) -> Decision:
        if not gate_passed:
            return Decision(False, "refused: verification gate did not pass")
        needs_owner = requires_owner_authorization or action in OWNER_GATED_ACTIONS
        if needs_owner and owner_authorization != AUTHORIZATION_PHRASE:
            return Decision(False, f"refused: owner authorization required for '{action}'")
        path = connector or CONNECTOR_ROUTES.get(action)
        if not path:
            return Decision(False, f"refused: no connector mapped for action '{action}'")
        return Decision(True, "allowed", path, idempotency_key, verified_by)

    # -- decision + actual dispatch --
    def dispatch(
        self,
        action: str,
        payload: dict,
        *,
        idempotency_key: str,
        verified_by: str,
        gate_passed: bool = True,
        requires_owner_authorization: bool = False,
        owner_authorization: str = "",
        connector: Optional[str] = None,
    ) -> N8nResult:
        d = self.plan(
            action,
            idempotency_key=idempotency_key,
            verified_by=verified_by,
            gate_passed=gate_passed,
            requires_owner_authorization=requires_owner_authorization,
            owner_authorization=owner_authorization,
            connector=connector,
        )
        if not d.allowed:
            # record the refusal in the ledger too — a refused side effect is still an event
            try:
                self.ledger_writer({
                    "event": "n8n_delegation_refused", "webhook_path": d.connector_path or action,
                    "action": action, "idempotency_key": idempotency_key,
                    "verified_by": verified_by, "reason": d.reason, "ok": False,
                })
            except Exception:
                pass
            raise DelegationRefused(d.reason)

        bridge = N8nBridge(
            base_url=self.n8n_base_url,
            timeout_s=self.timeout_s,
            max_retries=self.max_retries,
            ledger_writer=self.ledger_writer,
        )
        return bridge.trigger_workflow(
            webhook_path=d.connector_path,
            payload=payload,
            idempotency_key=idempotency_key,
            verified_by=verified_by,
        )

    # -- convenience: take the JarvisPrime.delegate() envelope dict directly --
    def dispatch_envelope(self, envelope: dict, *, owner_authorization: str = "") -> N8nResult:
        action = envelope.get("action") or envelope.get("delegate_to") or "delegate"
        return self.dispatch(
            action,
            payload=envelope.get("payload", {}),
            idempotency_key=envelope.get("idempotency_key") or envelope.get("packet_id") or uuid.uuid4().hex,
            verified_by=envelope.get("verified_by") or envelope.get("ledger_latest_hash") or "unknown-gate",
            gate_passed=bool(envelope.get("gate_passed", True)),
            requires_owner_authorization=bool(envelope.get("requires_owner_authorization", False)),
            owner_authorization=owner_authorization,
            connector=envelope.get("connector_path"),
        )


if __name__ == "__main__":
    # Dry-run self-test: exercises the gate/owner logic with NO network calls.
    disp = DelegateDispatcher(n8n_base_url="http://localhost:5678")
    samples = [
        ("send_email", dict(idempotency_key="a1", verified_by="hash1", gate_passed=True)),
        ("send_email", dict(idempotency_key="a2", verified_by="hash2", gate_passed=False)),
        ("post_publicly", dict(idempotency_key="a3", verified_by="hash3",
                               requires_owner_authorization=True, owner_authorization="")),
        ("post_publicly", dict(idempotency_key="a4", verified_by="hash4",
                               requires_owner_authorization=True,
                               owner_authorization=AUTHORIZATION_PHRASE)),
        ("mystery_action", dict(idempotency_key="a5", verified_by="hash5")),
    ]
    print("DelegateDispatcher dry-run (plan only, no network):\n")
    for action, kw in samples:
        d = disp.plan(action, **kw)
        flag = "ALLOW " if d.allowed else "REFUSE"
        print(f"  [{flag}] {action:<15} -> {d.connector_path or '-':<28} {d.reason}")
    print("\nLedger target:", disp.ledger_writer.latest_hash.__self__.__class__.__name__
          if hasattr(disp.ledger_writer, "latest_hash") else "n/a")
