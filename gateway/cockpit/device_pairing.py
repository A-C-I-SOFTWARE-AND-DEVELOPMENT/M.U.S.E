"""Per-device cockpit pairing (Sprint 6, additive layer).

The cockpit already has a SINGLE shared bearer token
(:mod:`gateway.cockpit.auth`) that stays re-displayable for backward
compatibility. This module adds a **second**, per-device credential
path **alongside** it — it does not replace or alter the shared token.

A new device pairs in two steps:

1. :func:`start_pairing` mints a short-lived pairing id + code (no token yet)
   and stores them pending. Rate-limited and lockout-protected, mirroring
   :mod:`gateway.pairing`.
2. :func:`confirm_pairing` exchanges that matching, unexpired pair for a fresh
   per-device token (via :func:`hermes_cli.cockpit_token.generate_token`).
   Only the token's **hash** is persisted (keyed by a new ``device_id``);
   the raw token is returned exactly once and never stored or logged.

Thereafter :func:`verify_device_token` authenticates a presented raw
token against the stored hashes (constant-time, honoring a revoked set)
via :func:`hermes_cli.cockpit_token.is_authorized`, and
:func:`revoke_device` tombstones a device.

Storage: ``${HERMES_HOME}/cockpit/devices.jsonl`` — a durable JSON-lines
store, written owner-only (0600) via an atomic temp-file rename so
readers never see a partial write. Stdlib-only (Termux-safe); no
network, no third-party deps, no secret logging.
"""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from gateway.cockpit import auth as cockpit_auth
from hermes_cli import cockpit_token

# Pairing code: unambiguous alphabet (no 0/O, 1/I/l) so a code read aloud
# or typed on a phone is hard to mistype.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 8

# Timing + limits (seconds / counts). Mirrors gateway/pairing.py intent,
# but the cockpit code is short-lived (5 minutes) since it's confirmed
# immediately by the same owner on the same device.
CODE_TTL_SECONDS = 300            # pairing code expires after 5 minutes
RATE_LIMIT_SECONDS = 30           # min spacing between start_pairing calls
LOCKOUT_SECONDS = 900             # lockout duration after too many failures
MAX_PENDING = 5                   # max simultaneously-pending codes
MAX_FAILED_CONFIRMS = 5           # failed confirms before lockout

_RATE_KEY = "_rate"
_FAILURES_KEY = "_failures"
_LOCKOUT_KEY = "_lockout_until"

# Guards every read-modify-write of the store. The cockpit server is a
# ThreadingHTTPServer, so concurrent pair requests share this store.
_LOCK = threading.RLock()


@dataclass(frozen=True)
class PairingStart:
    """Result of :func:`start_pairing`."""

    pairing_id: str
    pairing_code: str
    expires_at: float


@dataclass(frozen=True)
class PairingConfirm:
    """Result of :func:`confirm_pairing` — the raw token is returned ONCE."""

    device_id: str
    token: str


def _devices_path() -> Path:
    """``${HERMES_HOME}/cockpit/devices.jsonl`` — the device store path."""
    return cockpit_auth.cockpit_dir() / "devices.jsonl"


def _now() -> float:
    return time.time()


def _new_device_id() -> str:
    return "dev_" + secrets.token_hex(8)


def _new_pairing_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def _new_pairing_id() -> str:
    return "pair_" + secrets.token_urlsafe(18)


# --- durable store ----------------------------------------------------------
#
# The store is a JSON-lines file with exactly two record kinds:
#   * "_meta"  — a single bookkeeping line (pending codes, rate/lockout).
#   * "device" — one confirmed device per line (device_id, token *hash*,
#                name, timestamps, revoked flag). NEVER the raw token.
# We rewrite the whole file on each mutation (the device set is tiny —
# a handful of phones), which keeps the on-disk shape trivially correct.


def _empty_state() -> dict[str, Any]:
    return {
        "meta": {
            "pending": {},          # code -> {pairing_id, device_name, created_at}
            _RATE_KEY: 0.0,         # last start_pairing time
            _FAILURES_KEY: 0,       # consecutive failed confirms
            _LOCKOUT_KEY: 0.0,      # locked-out until (epoch)
        },
        "devices": {},              # device_id -> device record
    }


def _load_state() -> dict[str, Any]:
    """Read the store into a normalized state dict. Corrupt/missing → empty."""
    state = _empty_state()
    path = _devices_path()
    if not path.is_file():
        return state
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - defensive
        return state
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip a torn/garbage line rather than crash
        if not isinstance(rec, dict):
            continue
        if rec.get("kind") == "_meta":
            meta = rec.get("meta")
            if isinstance(meta, dict):
                state["meta"].update(meta)
                # Normalize the nested pending dict.
                pending = state["meta"].get("pending")
                state["meta"]["pending"] = pending if isinstance(pending, dict) else {}
        elif rec.get("kind") == "device":
            device_id = rec.get("device_id")
            if isinstance(device_id, str) and device_id:
                state["devices"][device_id] = rec
    return state


def _serialize(state: dict[str, Any]) -> str:
    lines = [json.dumps({"kind": "_meta", "meta": state["meta"]}, ensure_ascii=False)]
    for rec in state["devices"].values():
        out = {**rec, "kind": "device"}
        lines.append(json.dumps(out, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def _save_state(state: dict[str, Any]) -> None:
    """Atomically persist *state* owner-only (0600)."""
    path = _devices_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_serialize(state))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover - platform-dependent (Windows)
            pass
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --- rate-limit / lockout helpers (operate on a loaded state) ---------------


def _prune_expired_pending(state: dict[str, Any], now: float) -> None:
    pending = state["meta"]["pending"]
    expired = [
        code
        for code, info in pending.items()
        if (now - float(info.get("created_at", 0))) > CODE_TTL_SECONDS
    ]
    for code in expired:
        del pending[code]


def _is_locked_out(state: dict[str, Any], now: float) -> bool:
    return now < float(state["meta"].get(_LOCKOUT_KEY, 0))


def _record_failed_confirm(state: dict[str, Any], now: float) -> None:
    fails = int(state["meta"].get(_FAILURES_KEY, 0)) + 1
    if fails >= MAX_FAILED_CONFIRMS:
        state["meta"][_LOCKOUT_KEY] = now + LOCKOUT_SECONDS
        state["meta"][_FAILURES_KEY] = 0  # reset the counter after lockout
    else:
        state["meta"][_FAILURES_KEY] = fails


# --- public API -------------------------------------------------------------


def start_pairing(device_name: str) -> Optional[PairingStart]:
    """Begin pairing a device: mint and store a short-lived pairing code.

    Returns a :class:`PairingStart` (id, code, and ``expires_at`` epoch),
    or ``None`` when the request is refused:

      * rate-limited (a ``start_pairing`` happened within
        ``RATE_LIMIT_SECONDS``),
      * locked out after ``MAX_FAILED_CONFIRMS`` bad confirms, or
      * ``MAX_PENDING`` codes are already outstanding.

    No token is created here — only a pending code. The code is never logged.
    """
    name = (device_name or "").strip() or "unnamed-device"
    with _LOCK:
        state = _load_state()
        now = _now()
        _prune_expired_pending(state, now)

        if _is_locked_out(state, now):
            return None
        last = float(state["meta"].get(_RATE_KEY, 0))
        if (now - last) < RATE_LIMIT_SECONDS:
            return None
        if len(state["meta"]["pending"]) >= MAX_PENDING:
            return None

        code = _new_pairing_code()
        pairing_id = _new_pairing_id()
        state["meta"]["pending"][code] = {
            "pairing_id": pairing_id,
            "device_name": name,
            "created_at": now,
        }
        state["meta"][_RATE_KEY] = now
        _save_state(state)
        return PairingStart(
            pairing_id=pairing_id,
            pairing_code=code,
            expires_at=now + CODE_TTL_SECONDS,
        )


def confirm_pairing(
    pairing_code: str, pairing_id: str | None = None
) -> Optional[PairingConfirm]:
    """Exchange a valid, unexpired pairing code for a fresh per-device token.

    On success a new ``device_id`` is created, a token is generated via
    :func:`cockpit_token.generate_token`, and **only its hash** is stored
    (:func:`cockpit_token.hash_token`). The raw token is returned exactly
    once in :class:`PairingConfirm` and never persisted or logged.

    Returns ``None`` when the code is unknown/expired or the store is locked
    out; a bad/expired code counts toward the lockout (brute-force defense).
    """
    code = (pairing_code or "").strip().upper()
    with _LOCK:
        state = _load_state()
        now = _now()
        _prune_expired_pending(state, now)

        # Lockout is checked before the lookup so an attacker cannot keep
        # guessing a code once the failure threshold trips.
        if _is_locked_out(state, now):
            return None

        pending = state["meta"]["pending"]
        info = pending.get(code)
        expected_pairing_id = str((info or {}).get("pairing_id") or "")
        if (
            info is None
            or not pairing_id
            or not secrets.compare_digest(str(pairing_id), expected_pairing_id)
        ):
            _record_failed_confirm(state, now)
            _save_state(state)
            return None

        # Valid code — consume it and clear the failure counter.
        del pending[code]
        state["meta"][_FAILURES_KEY] = 0

        raw_token = cockpit_token.generate_token()
        device_id = _new_device_id()
        state["devices"][device_id] = {
            "device_id": device_id,
            "device_name": str(info.get("device_name", "")) or "unnamed-device",
            "token_hash": cockpit_token.hash_token(raw_token),
            "created_at": now,
            "revoked": False,
        }
        _save_state(state)
        return PairingConfirm(device_id=device_id, token=raw_token)


def verify_device_token(raw: str) -> Optional[str]:
    """Return the ``device_id`` a raw token authenticates as, else ``None``.

    Constant-time per stored hash via :func:`cockpit_token.is_authorized`,
    honoring each device's ``revoked`` flag (a revoked device's hash is
    placed in the revocation set, so even a hash match is rejected).
    """
    if not raw:
        return None
    with _LOCK:
        state = _load_state()
    for device_id, rec in state["devices"].items():
        stored_hash = str(rec.get("token_hash", ""))
        if not stored_hash:
            continue
        revoked = (stored_hash,) if rec.get("revoked") else ()
        if cockpit_token.is_authorized(raw, stored_hash, revoked_hashes=revoked):
            return device_id
    return None


def revoke_device(device_id: str) -> bool:
    """Revoke a paired device by id. Returns ``True`` if it was found+active.

    Revocation is a tombstone (``revoked = True``), not a delete, so the
    record of which device existed survives. A token whose device is
    revoked never authenticates again (see :func:`verify_device_token`).
    """
    if not device_id:
        return False
    with _LOCK:
        state = _load_state()
        rec = state["devices"].get(device_id)
        if rec is None or rec.get("revoked"):
            return False
        rec["revoked"] = True
        rec["revoked_at"] = _now()
        _save_state(state)
        return True


def list_devices() -> list[dict[str, Any]]:
    """Return device metadata (no token material). For status/diagnostics."""
    with _LOCK:
        state = _load_state()
    out: list[dict[str, Any]] = []
    for rec in state["devices"].values():
        out.append(
            {
                "device_id": rec.get("device_id"),
                "device_name": rec.get("device_name"),
                "created_at": rec.get("created_at"),
                "revoked": bool(rec.get("revoked")),
                "revoked_at": rec.get("revoked_at"),
            }
        )
    return out


__all__ = [
    "CODE_TTL_SECONDS",
    "LOCKOUT_SECONDS",
    "MAX_FAILED_CONFIRMS",
    "MAX_PENDING",
    "RATE_LIMIT_SECONDS",
    "PairingConfirm",
    "PairingStart",
    "confirm_pairing",
    "list_devices",
    "revoke_device",
    "start_pairing",
    "verify_device_token",
]
