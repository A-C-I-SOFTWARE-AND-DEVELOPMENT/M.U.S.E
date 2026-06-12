"""Durable persistence for the worker-lease state machine (Sprint 13 wiring).

:mod:`muse_cli.worker_lease` is a pure, clock-injected state kernel: it
decides *what* a lease transition produces but never records it. This module
is the durable side of that contract — it persists each :class:`WorkerLease`
to a JSONL log and folds the kernel's ``expire_if_stale`` over the running
leases on demand. It also keeps a tiny host registry so a future multi-host
scheduler knows which execution hosts exist.

Design constraints (same spirit as ``jarvis_prime`` and the orchestrator):

* Stdlib-only at import time (Termux / slim-CI friendly), no network.
* ``${HERMES_HOME}/orchestration/leases.jsonl`` keyed by ``lease_id``; the
  host registry lives in the sibling ``hosts.jsonl``.
* Atomic writes (write a temp file, ``os.replace``), guarded by an
  :class:`threading.RLock` so concurrent worker threads can record safely.
* Tolerant load: a corrupt/garbage line is skipped (and noted in
  ``load_diagnostics``) rather than wedging the whole store.
* The store *records*; it never drives the kernel into a state the kernel
  itself would reject. ``expire_stale`` only applies the kernel's own
  ``expire_if_stale`` to ``RUNNING`` leases.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from muse_cli.worker_lease import LeaseStatus, WorkerLease, expire_if_stale

__all__ = [
    "DEFAULT_HOST_ID",
    "HostRecord",
    "WorkerLeaseStore",
    "lease_to_dict",
    "lease_from_dict",
    "default_store_dir",
]

#: The host every install has by default — the machine running Hermes itself.
DEFAULT_HOST_ID = "local"

LEASES_FILENAME = "leases.jsonl"
HOSTS_FILENAME = "hosts.jsonl"


# ─── serialization ────────────────────────────────────────────────────


def lease_to_dict(lease: WorkerLease) -> dict[str, object]:
    """Serialize a :class:`WorkerLease` to a JSON-safe dict.

    The ``status`` enum is stored as its string value; the rest of the
    dataclass is already JSON-native.
    """

    return {
        "lease_id": lease.lease_id,
        "job_id": lease.job_id,
        "worker_id": lease.worker_id,
        "host_id": lease.host_id,
        "status": lease.status.value,
        "acquired_at": lease.acquired_at,
        "heartbeat_at": lease.heartbeat_at,
        "expires_at": lease.expires_at,
        "idempotent": lease.idempotent,
    }


def lease_from_dict(data: dict[str, object]) -> WorkerLease:
    """Rebuild a :class:`WorkerLease` from a stored dict.

    Raises ``ValueError`` / ``KeyError`` on a malformed record so the
    tolerant loader can skip the offending line.
    """

    return WorkerLease(
        lease_id=str(data["lease_id"]),
        job_id=str(data["job_id"]),
        worker_id=str(data["worker_id"]),
        host_id=str(data["host_id"]),
        status=LeaseStatus(str(data["status"])),
        acquired_at=_as_opt_float(data.get("acquired_at")),
        heartbeat_at=_as_opt_float(data.get("heartbeat_at")),
        expires_at=_as_opt_float(data.get("expires_at")),
        idempotent=bool(data.get("idempotent", True)),
    )


def _as_opt_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bool is an int subclass
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


# ─── host registry record ─────────────────────────────────────────────


@dataclass(frozen=True)
class HostRecord:
    """One execution host the scheduler may place workers on."""

    host_id: str
    kind: str = "local"

    def to_dict(self) -> dict[str, object]:
        return {"host_id": self.host_id, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "HostRecord":
        return cls(host_id=str(data["host_id"]), kind=str(data.get("kind", "local")))


# ─── paths ────────────────────────────────────────────────────────────


def default_store_dir() -> Path:
    """``${HERMES_HOME:-~/.hermes}/orchestration`` — the lease store dir.

    Honors ``HERMES_HOME`` like the rest of the stack so tests stay
    isolated from the real home directory.
    """

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "orchestration"


# ─── store ────────────────────────────────────────────────────────────


@dataclass
class WorkerLeaseStore:
    """Durable JSONL store for :class:`WorkerLease` records + a host registry.

    Construct with an explicit ``directory`` (tests) or let it default to
    :func:`default_store_dir`. The in-memory maps are the working copy;
    every mutation rewrites the backing JSONL atomically.
    """

    directory: Optional[Path] = None
    leases: dict[str, WorkerLease] = field(default_factory=dict)
    _hosts: dict[str, HostRecord] = field(default_factory=dict)
    load_diagnostics: list[str] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- construction -------------------------------------------------------

    @classmethod
    def load(cls, directory: Optional[Path] = None) -> "WorkerLeaseStore":
        """Load (or initialize) the store, tolerating corrupt lines.

        Always guarantees the :data:`DEFAULT_HOST_ID` host exists so a
        fresh install can place ``local`` workers without explicit setup.
        """

        store = cls(directory=directory)
        store._load_leases()
        store._load_hosts()
        # Guarantee the default host without forcing a write if it's there.
        if DEFAULT_HOST_ID not in store._hosts:
            store.register_host(DEFAULT_HOST_ID, kind="local")
        return store

    # -- resolved paths -----------------------------------------------------

    def _dir(self) -> Path:
        return Path(self.directory) if self.directory else default_store_dir()

    def _leases_path(self) -> Path:
        return self._dir() / LEASES_FILENAME

    def _hosts_path(self) -> Path:
        return self._dir() / HOSTS_FILENAME

    # -- lease API ----------------------------------------------------------

    def upsert(self, lease: WorkerLease) -> WorkerLease:
        """Insert or replace a lease (keyed by ``lease_id``) and persist."""

        with self._lock:
            self.leases[lease.lease_id] = lease
            self._save_leases()
        return lease

    def get(self, lease_id: str) -> Optional[WorkerLease]:
        """Return the lease for ``lease_id`` or ``None``."""

        with self._lock:
            return self.leases.get(lease_id)

    def for_job(self, job_id: str) -> list[WorkerLease]:
        """Return every lease belonging to ``job_id`` (stable order)."""

        with self._lock:
            return [
                lease
                for lease in self.leases.values()
                if lease.job_id == job_id
            ]

    def active(self) -> list[WorkerLease]:
        """Return the currently ``RUNNING`` leases (non-terminal, in flight)."""

        with self._lock:
            return [
                lease
                for lease in self.leases.values()
                if lease.status is LeaseStatus.RUNNING
            ]

    def all_leases(self) -> list[WorkerLease]:
        """Return every stored lease, terminal or not."""

        with self._lock:
            return list(self.leases.values())

    def expire_stale(self, now: float) -> list[WorkerLease]:
        """Fold the kernel's ``expire_if_stale`` over running leases.

        Any ``RUNNING`` lease past its deadline transitions to ``EXPIRED``
        and the change is persisted. Returns the leases that flipped. This
        only applies the frozen kernel's own rule — it never invents a
        transition the kernel would reject.
        """

        with self._lock:
            expired: list[WorkerLease] = []
            for lease_id, lease in list(self.leases.items()):
                if lease.status is not LeaseStatus.RUNNING:
                    continue
                updated = expire_if_stale(lease, now=now)
                if updated is not lease and updated.status != lease.status:
                    self.leases[lease_id] = updated
                    expired.append(updated)
            if expired:
                self._save_leases()
            return expired

    # -- host registry ------------------------------------------------------

    def register_host(self, host_id: str, *, kind: str = "local") -> HostRecord:
        """Register (or update) an execution host and persist."""

        host_id = (host_id or "").strip()
        if not host_id:
            raise ValueError("host_id must be non-empty")
        record = HostRecord(host_id=host_id, kind=kind)
        with self._lock:
            self._hosts[host_id] = record
            self._save_hosts()
        return record

    def hosts(self) -> list[HostRecord]:
        """Return every registered host (stable order)."""

        with self._lock:
            return list(self._hosts.values())

    def get_host(self, host_id: str) -> Optional[HostRecord]:
        """Return the host record for ``host_id`` or ``None``."""

        with self._lock:
            return self._hosts.get(host_id)

    # -- persistence --------------------------------------------------------

    def _load_leases(self) -> None:
        target = self._leases_path()
        if not target.exists():
            return
        with self._lock:
            with open(target, "r", encoding="utf-8") as fh:
                for lineno, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        lease = lease_from_dict(json.loads(raw))
                        self.leases[lease.lease_id] = lease
                    except (json.JSONDecodeError, KeyError, ValueError) as exc:
                        self.load_diagnostics.append(f"leases line {lineno}: {exc}")

    def _load_hosts(self) -> None:
        target = self._hosts_path()
        if not target.exists():
            return
        with self._lock:
            with open(target, "r", encoding="utf-8") as fh:
                for lineno, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        host = HostRecord.from_dict(json.loads(raw))
                        self._hosts[host.host_id] = host
                    except (json.JSONDecodeError, KeyError, ValueError) as exc:
                        self.load_diagnostics.append(f"hosts line {lineno}: {exc}")

    def _save_leases(self) -> Path:
        payload = "".join(
            json.dumps(lease_to_dict(lease), sort_keys=True) + "\n"
            for lease in self.leases.values()
        )
        return _atomic_write(self._leases_path(), payload, prefix=".leases-")

    def _save_hosts(self) -> Path:
        payload = "".join(
            json.dumps(host.to_dict(), sort_keys=True) + "\n"
            for host in self._hosts.values()
        )
        return _atomic_write(self._hosts_path(), payload, prefix=".hosts-")


def _atomic_write(target: Path, payload: str, *, prefix: str) -> Path:
    """Write ``payload`` to ``target`` atomically with ``0o600`` perms."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        os.chmod(target, 0o600)
    except OSError:  # pragma: no cover - platform-dependent
        pass
    return target
