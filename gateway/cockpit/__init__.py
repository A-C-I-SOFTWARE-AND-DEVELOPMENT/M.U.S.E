"""Hermes cockpit API — the loopback HTTP surface the Jarvis Prime Android
app talks to.

Implements the contract in ``docs/android/hermes-apk-api-contract.md``:
bearer-token-authenticated, loopback-only JSON/NDJSON endpoints backed by
the **real** Hermes subsystems (JARVIS Prime runtime for chat, the
orchestrator/job-queue for tasks, the decision ledger for audit, the
JARVIS memory store, owner-auth for approvals, the model policy, the
launch doctor for diagnostics, …) — never mocks or echoes.

Stdlib-only at import time (Termux-safe). Heavy subsystems are imported
lazily inside the route handlers.
"""

from __future__ import annotations

from gateway.cockpit.auth import (
    cockpit_dir,
    extract_bearer,
    load_or_create_token,
    read_token,
    rotate_token,
    token_matches,
    token_path,
)

__all__ = [
    "cockpit_dir",
    "extract_bearer",
    "load_or_create_token",
    "read_token",
    "rotate_token",
    "token_matches",
    "token_path",
]
