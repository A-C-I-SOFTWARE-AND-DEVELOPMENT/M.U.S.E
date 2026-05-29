"""Branch lease/lock semantics for JARVIS Prime worker lanes.

Claude Code and Codex are *external* worker lanes (subscription-backed
official tools). When JARVIS hands a branch to one of them, the other
must not edit that same branch concurrently — otherwise two agents race
on the same working tree and produce conflicting commits.

This module gives that a small, file-based lease. A lease is a JSON file
under ``${HERMES_HOME}/jarvis_prime/locks/<branch>.lock`` recording which
worker holds the branch, when it was acquired, and when the lease
expires. Leases are time-boxed (TTL) so a crashed worker can't wedge a
branch forever — an expired lease is treated as free and can be stolen.

Design constraints (same spirit as the rest of ``jarvis_prime``):

* Stdlib-only at import time (Termux / slim-CI friendly).
* No network. The only IO is reading/writing the lease file.
* Deterministic + testable: ``now`` and ``locks_dir`` are injectable so
  tests never touch the real home directory or wall clock.
* Re-acquiring your own live lease is idempotent (refreshes the TTL).
* Acquiring a branch held by a *different* live worker raises
  :class:`BranchLockedError` — it never silently steals.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional


DEFAULT_TTL_SECONDS = (
    3600  # one hour — long enough for a build, short enough to self-heal
)

_SAFE_BRANCH = re.compile(r"[^A-Za-z0-9._-]+")


class BranchLockedError(RuntimeError):
    """Raised when a branch is already leased by a different live worker."""

    def __init__(self, branch: str, holder: "BranchLease") -> None:
        self.branch = branch
        self.holder = holder
        super().__init__(
            f"branch {branch!r} is leased by worker {holder.worker!r} "
            f"until {holder.expires_at_iso} — refuse concurrent edit"
        )


@dataclass
class BranchLease:
    """One branch lease record."""

    branch: str
    worker: str
    acquired_at: float
    expires_at: float
    pid: int = 0
    note: str = ""

    @property
    def expires_at_iso(self) -> str:
        import datetime as _dt

        return _dt.datetime.fromtimestamp(
            self.expires_at, tz=_dt.timezone.utc
        ).isoformat()

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BranchLease":
        return cls(
            branch=str(data.get("branch", "")),
            worker=str(data.get("worker", "")),
            acquired_at=_as_float(data.get("acquired_at")),
            expires_at=_as_float(data.get("expires_at")),
            pid=int(_as_float(data.get("pid"))),
            note=str(data.get("note", "")),
        )


def _as_float(value: object) -> float:
    """Best-effort float coercion for values read back from JSON."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def default_locks_dir() -> Path:
    """``${HERMES_HOME:-~/.hermes}/jarvis_prime/locks`` — the lease store."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "locks"


def _sanitize(branch: str) -> str:
    """Map an arbitrary branch name to a safe single-file basename."""
    cleaned = _SAFE_BRANCH.sub("-", branch.strip()) or "unnamed"
    return cleaned.strip("-") or "unnamed"


def _lease_path(branch: str, locks_dir: Path) -> Path:
    return locks_dir / f"{_sanitize(branch)}.lock"


def _tighten(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent
        pass


def read_lease(
    branch: str, *, locks_dir: Optional[Path] = None
) -> Optional[BranchLease]:
    """Return the lease on ``branch`` if a lease file exists and parses."""
    path = _lease_path(branch, locks_dir or default_locks_dir())
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return BranchLease.from_dict(data)


def is_branch_locked(
    branch: str,
    *,
    worker: Optional[str] = None,
    locks_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> bool:
    """True if ``branch`` is held by a live lease.

    When ``worker`` is given, a lease held by that same worker does not
    count as locked (you never block yourself).
    """
    lease = read_lease(branch, locks_dir=locks_dir)
    if lease is None or lease.is_expired(now):
        return False
    if worker is not None and lease.worker == worker:
        return False
    return True


def acquire_branch_lease(
    branch: str,
    worker: str,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    locks_dir: Optional[Path] = None,
    now: Optional[Callable[[], float]] = None,
    note: str = "",
) -> BranchLease:
    """Acquire (or refresh) a lease on ``branch`` for ``worker``.

    Raises :class:`BranchLockedError` when a *different* worker holds a
    live (non-expired) lease. Re-acquiring your own lease refreshes the
    TTL. Expired leases (crashed/abandoned workers) are silently stolen.

    ``now`` is an injectable clock (a callable returning epoch seconds)
    used by tests; production passes ``None`` and uses ``time.time()``.
    """
    if not branch.strip():
        raise ValueError("branch must be non-empty")
    if not worker.strip():
        raise ValueError("worker must be non-empty")

    now_ts = now() if now is not None else time.time()
    locks_dir = locks_dir or default_locks_dir()
    locks_dir.mkdir(parents=True, exist_ok=True)
    path = _lease_path(branch, locks_dir)

    existing = read_lease(branch, locks_dir=locks_dir)
    if existing is not None and not existing.is_expired(now_ts):
        if existing.worker != worker:
            raise BranchLockedError(branch, existing)
        # Same worker → refresh.

    lease = BranchLease(
        branch=branch,
        worker=worker,
        acquired_at=now_ts,
        expires_at=now_ts + max(1, int(ttl_seconds)),
        pid=os.getpid(),
        note=note,
    )
    _write_lease(path, lease)
    return lease


def _write_lease(path: Path, lease: BranchLease) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(lease.to_dict(), indent=2), encoding="utf-8")
    _tighten(tmp)
    os.replace(tmp, path)
    _tighten(path)


def release_branch_lease(
    branch: str,
    worker: str,
    *,
    locks_dir: Optional[Path] = None,
    force: bool = False,
) -> bool:
    """Release a lease. Returns True if a lease was removed.

    Only the holding ``worker`` may release its lease unless ``force`` is
    set (used by emergency stop, which must be able to clear everything).
    """
    locks_dir = locks_dir or default_locks_dir()
    lease = read_lease(branch, locks_dir=locks_dir)
    if lease is None:
        return False
    if not force and lease.worker != worker:
        return False
    try:
        _lease_path(branch, locks_dir).unlink()
        return True
    except OSError:  # pragma: no cover - defensive
        return False


def list_leases(*, locks_dir: Optional[Path] = None) -> list[BranchLease]:
    """Return every parseable lease in the store (live or expired)."""
    locks_dir = locks_dir or default_locks_dir()
    if not locks_dir.is_dir():
        return []
    out: list[BranchLease] = []
    for path in sorted(locks_dir.glob("*.lock")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            out.append(BranchLease.from_dict(data))
    return out


def clear_all_leases(*, locks_dir: Optional[Path] = None) -> int:
    """Remove every lease file. Returns count removed. Used by emergency stop."""
    locks_dir = locks_dir or default_locks_dir()
    if not locks_dir.is_dir():
        return 0
    removed = 0
    for path in locks_dir.glob("*.lock"):
        try:
            path.unlink()
            removed += 1
        except OSError:  # pragma: no cover - defensive
            pass
    return removed


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "BranchLease",
    "BranchLockedError",
    "acquire_branch_lease",
    "clear_all_leases",
    "default_locks_dir",
    "is_branch_locked",
    "list_leases",
    "read_lease",
    "release_branch_lease",
]
