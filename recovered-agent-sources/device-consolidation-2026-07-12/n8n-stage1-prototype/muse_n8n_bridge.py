"""
muse_n8n_bridge.py — M.U.S.E. -> n8n delegation bridge.

PURPOSE
-------
Lets M.U.S.E.'s Delegate stage hand an AXIOM-approved action to self-hosted
n8n, which executes it against n8n's 400+ app integrations instead of
M.U.S.E. maintaining bespoke connector code for every external app
(email, calendars, CRMs, Slack, etc.).

WHERE THIS SITS IN THE PIPELINE
--------------------------------
    perceive -> classify -> decide -> gate (AXIOM) -> [THIS MODULE] -> speak

Call this only AFTER AXIOM's Gate stage has verified and approved the
action. This module does not re-verify anything and has no opinion on
whether the action *should* happen — consistent with "Intelligence
proposes; the verifier disposes," verification is the Gate's job, not
this bridge's. Wiring this module in earlier than Delegate would bypass
the invariant.

QUICK START
-----------
    from muse_n8n_bridge import N8nBridge, N8nError

    bridge = N8nBridge(
        base_url="http://localhost:5678",
        ledger_writer=axiom_ledger.append,   # optional but recommended, see below
    )

    result = bridge.trigger_workflow(
        webhook_path="muse-echo",
        payload={"action": "send_email", "to": "x@example.com"},
        idempotency_key=gate_decision.action_id,
        verified_by=gate_decision.gate_id,
    )

LEDGER INTEGRATION
------------------
Pass any callable as `ledger_writer` and this module calls it once per
attempt with a dict describing the delegation event (workflow path,
idempotency key, status, latency, error if any). Wire this straight into
AXIOM's hash-chained ledger so every delegated action — success or
failure — gets an append-only record. If you skip `ledger_writer`,
delegation still works, but a delegated real-world action with no ledger
entry is exactly the failure mode the hash chain exists to prevent, so
treat skipping it as fine for local testing only, not for anything that
touches a real inbox, calendar, or CRM.

IDEMPOTENCY
-----------
n8n itself does not dedupe incoming webhook calls. This module sends
`idempotency_key` as both a header and a payload field so the target n8n
workflow (or the API it calls downstream) can dedupe if it supports it.
Retries in this module only happen on connection errors, timeouts, or 5xx
responses — never on 4xx, since retrying a bad request won't fix it and
could double-fire a side effect if the receiving end has no dedup logic
of its own. If a given n8n workflow triggers something non-idempotent
(e.g. "send an email"), make sure that workflow itself checks
idempotency_key before acting, or set max_retries=0 when calling it.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("muse.n8n_bridge")


class N8nError(RuntimeError):
    """Raised when a delegated n8n workflow call fails after all retries."""


@dataclass
class N8nResult:
    ok: bool
    status_code: Optional[int]
    body: Any
    latency_ms: float
    attempts: int


@dataclass
class N8nBridge:
    base_url: str
    timeout_s: float = 15.0
    max_retries: int = 2
    backoff_base_s: float = 1.5
    api_key: Optional[str] = None  # only if you put a shared-secret check in front of the webhook node
    ledger_writer: Optional[Callable[[dict], None]] = None

    def trigger_workflow(
        self,
        webhook_path: str,
        payload: dict,
        idempotency_key: str,
        verified_by: str = "unknown-gate",
    ) -> N8nResult:
        """
        POST `payload` to the n8n webhook registered at `webhook_path`.

        idempotency_key: pass the AXIOM action_id / decision id here.
        verified_by: identifier of the AXIOM gate/decision that approved
            this action — recorded in the ledger entry, not sent to n8n
            for any enforcement purpose (n8n doesn't know what AXIOM is).
        """
        url = f"{self.base_url.rstrip('/')}/webhook/{webhook_path.lstrip('/')}"
        body = {
            "idempotency_key": idempotency_key,
            "verified_by": verified_by,
            "payload": payload,
        }
        data = json.dumps(body).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if self.api_key:
            headers["X-MUSE-Api-Key"] = self.api_key

        last_exc: Optional[Exception] = None
        total_attempts = self.max_retries + 1

        for attempt in range(1, total_attempts + 1):
            start = time.monotonic()
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                    latency_ms = (time.monotonic() - start) * 1000
                    try:
                        parsed = json.loads(raw) if raw else None
                    except json.JSONDecodeError:
                        parsed = raw
                    result = N8nResult(
                        ok=200 <= resp.status < 300,
                        status_code=resp.status,
                        body=parsed,
                        latency_ms=latency_ms,
                        attempts=attempt,
                    )
                    self._log(webhook_path, idempotency_key, verified_by, result, None)
                    return result

            except urllib.error.HTTPError as e:
                latency_ms = (time.monotonic() - start) * 1000
                raw = e.read().decode("utf-8", errors="replace")
                result = N8nResult(
                    ok=False, status_code=e.code, body=raw, latency_ms=latency_ms, attempts=attempt
                )
                self._log(webhook_path, idempotency_key, verified_by, result, str(e))
                if e.code < 500:
                    return result  # don't retry client errors
                last_exc = e

            except (urllib.error.URLError, TimeoutError) as e:
                last_exc = e
                self._log(webhook_path, idempotency_key, verified_by, None, str(e))

            if attempt < total_attempts:
                time.sleep(self.backoff_base_s * attempt)

        raise N8nError(f"n8n workflow '{webhook_path}' failed after {total_attempts} attempts: {last_exc}")

    def _log(
        self,
        webhook_path: str,
        idempotency_key: str,
        verified_by: str,
        result: Optional[N8nResult],
        error: Optional[str],
    ) -> None:
        record = {
            "event": "n8n_delegation",
            "webhook_path": webhook_path,
            "idempotency_key": idempotency_key,
            "verified_by": verified_by,
            "ok": result.ok if result else False,
            "status_code": result.status_code if result else None,
            "latency_ms": result.latency_ms if result else None,
            "attempts": result.attempts if result else None,
            "error": error,
        }
        logger.info("n8n delegation: %s", record)
        if self.ledger_writer:
            try:
                self.ledger_writer(record)
            except Exception:
                logger.exception("ledger_writer raised while recording n8n delegation")


if __name__ == "__main__":
    # Self-test: after `docker compose up -d` and importing + activating
    # muse_echo_workflow.json in the n8n UI, run:
    #     python muse_n8n_bridge.py
    import sys

    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5678"
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    bridge = N8nBridge(base_url=base)
    print(f"Pinging n8n at {base} ...")
    try:
        result = bridge.trigger_workflow(
            webhook_path="muse-echo",
            payload={"hello": "from M.U.S.E."},
            idempotency_key="self-test-001",
            verified_by="manual-self-test",
        )
        print(f"OK ({result.status_code}, {result.latency_ms:.0f}ms): {result.body}")
    except N8nError as e:
        print(f"FAILED: {e}")
        print("Check: is the container running? Did you import + ACTIVATE muse_echo_workflow.json?")
        sys.exit(1)
