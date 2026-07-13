"""Isolated fabrication workspaces with explicit provider authority and evidence."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from hermes_constants import get_hermes_home

from .authorization import AuthorizationError


class WorkspaceError(RuntimeError):
    pass


class WorkspaceAuthorizationError(AuthorizationError):
    pass


class WorkspaceUnavailable(WorkspaceError):
    pass


@dataclass(frozen=True)
class WorkspaceLease:
    id: str
    provider: str
    actor_id: str
    project_root: str
    workspace: str
    workload: str
    status: str
    created_at: float
    updated_at: float
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    checkpoint: str = ""
    provider_ref: str = ""
    unavailable_reason: str = ""


@dataclass(frozen=True)
class WorkspaceCheckpoint:
    lease_id: str
    commit: str
    label: str
    created_at: float


class WorkspaceProvider(Protocol):
    paid: bool

    def create(self, lease: WorkspaceLease) -> Mapping[str, Any]: ...
    def status(self, lease: WorkspaceLease) -> str: ...
    def checkpoint(self, lease: WorkspaceLease, label: str) -> str: ...
    def sleep(self, lease: WorkspaceLease) -> None: ...
    def resume(self, lease: WorkspaceLease) -> None: ...
    def destroy(self, lease: WorkspaceLease) -> None: ...
    def preview(self, lease: WorkspaceLease) -> str: ...
    def cost(self, lease: WorkspaceLease) -> float: ...


class DelegatingWorkspaceProvider:
    """Small adapter around Daytona/Modal/Vercel SDK-shaped backends."""

    paid = True

    def __init__(self, backend: object) -> None:
        self.backend = backend

    def create(self, lease: WorkspaceLease) -> Mapping[str, Any]:
        return self._mapping("create", lease)

    def status(self, lease: WorkspaceLease) -> str:
        return str(getattr(self.backend, "status")(lease))

    def checkpoint(self, lease: WorkspaceLease, label: str) -> str:
        return str(getattr(self.backend, "checkpoint")(lease, label))

    def sleep(self, lease: WorkspaceLease) -> None:
        getattr(self.backend, "sleep")(lease)

    def resume(self, lease: WorkspaceLease) -> None:
        getattr(self.backend, "resume")(lease)

    def destroy(self, lease: WorkspaceLease) -> None:
        getattr(self.backend, "destroy")(lease)

    def preview(self, lease: WorkspaceLease) -> str:
        return str(getattr(self.backend, "preview")(lease))

    def cost(self, lease: WorkspaceLease) -> float:
        return float(getattr(self.backend, "cost")(lease))

    def _mapping(self, name: str, *args: object) -> Mapping[str, Any]:
        value = getattr(self.backend, name)(*args)
        if not isinstance(value, Mapping):
            raise WorkspaceUnavailable(f"{name} provider response is invalid")
        return value


class DaytonaWorkspaceProvider(DelegatingWorkspaceProvider):
    pass


class ModalWorkspaceProvider(DelegatingWorkspaceProvider):
    pass


class VercelWorkspaceProvider(DelegatingWorkspaceProvider):
    pass


ApprovalVerifier = Callable[[str, str, str, float], bool]
EventSink = Callable[[str, Mapping[str, Any]], None]


class WorkspaceBroker:
    PROVIDERS = frozenset({"local", "daytona", "modal", "vercel"})

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        providers: Mapping[str, WorkspaceProvider] | None = None,
        approval_verifier: ApprovalVerifier | None = None,
        event_sink: EventSink | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = Path(root) if root else Path(get_hermes_home()) / "universe/workspaces"
        self.root.mkdir(parents=True, exist_ok=True)
        self._state_path = self.root / "leases.json"
        self._events_path = self.root / "workspace-events.jsonl"
        self._providers = dict(providers or {})
        self._approval_verifier = approval_verifier
        self._event_sink = event_sink
        self._clock = clock
        self._lock = threading.RLock()

    def create(
        self,
        provider: str,
        project_root: str | Path,
        actor_id: str,
        *,
        workload: str = "web",
        approval_id: str | None = None,
        estimated_cost_usd: float = 0.0,
    ) -> WorkspaceLease:
        if provider not in self.PROVIDERS:
            raise WorkspaceUnavailable(f"unsupported workspace provider: {provider}")
        if not actor_id.strip():
            raise WorkspaceAuthorizationError("actor_id is required")
        if (
            isinstance(estimated_cost_usd, bool)
            or not isinstance(estimated_cost_usd, (int, float))
            or not math.isfinite(float(estimated_cost_usd))
            or estimated_cost_usd < 0
        ):
            raise ValueError("estimated cost must be non-negative")
        if provider == "modal" and workload not in {"gpu", "render"}:
            raise WorkspaceUnavailable("Modal requires an explicit gpu or render workload")
        if provider != "local":
            if not approval_id or self._approval_verifier is None or not self._approval_verifier(
                approval_id, actor_id, provider, float(estimated_cost_usd)
            ):
                raise WorkspaceAuthorizationError("external workspace requires bound owner approval")

        source = Path(project_root).resolve()
        if not source.is_dir():
            raise WorkspaceUnavailable("project root does not exist")
        lease_id = "lease_" + uuid4().hex
        workspace = (self.root / lease_id).resolve()
        if not workspace.is_relative_to(self.root.resolve()):
            raise WorkspaceError("workspace escaped the broker root")
        now = self._clock()
        lease = WorkspaceLease(
            id=lease_id,
            provider=provider,
            actor_id=actor_id,
            project_root=str(source),
            workspace=str(workspace),
            workload=workload,
            status="creating",
            created_at=now,
            updated_at=now,
            estimated_cost_usd=float(estimated_cost_usd),
        )
        with self._lock:
            self._save(lease)
            try:
                if provider == "local":
                    self._create_local(source, workspace)
                    ready = replace(lease, status="ready", updated_at=self._clock())
                else:
                    adapter = self._providers.get(provider)
                    if adapter is None:
                        ready = replace(
                            lease,
                            status="unavailable",
                            updated_at=self._clock(),
                            unavailable_reason=f"{provider} adapter or credentials unavailable",
                        )
                    else:
                        result = dict(adapter.create(lease))
                        ready = replace(
                            lease,
                            status=str(result.get("status", "ready")),
                            provider_ref=str(result.get("provider_ref", "")),
                            updated_at=self._clock(),
                        )
                self._save(ready)
                self._record("workspace.created", ready, {"rollback": "destroy"})
                return ready
            except Exception:
                failed = replace(lease, status="failed", updated_at=self._clock())
                self._save(failed)
                self._record("workspace.create_failed", failed, {"rollback": "destroy"})
                raise

    def get(self, lease_id: str) -> WorkspaceLease:
        with self._lock:
            record = self._records().get(lease_id)
        if not isinstance(record, dict):
            raise KeyError(lease_id)
        return WorkspaceLease(**record)

    def status(self, lease_id: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        if lease.status in {"unavailable", "destroyed", "failed"}:
            return lease
        if lease.provider == "local":
            observed = lease.status if Path(lease.workspace).exists() else "unavailable"
        else:
            observed = self._provider(lease).status(lease)
        if observed == lease.status:
            return lease
        updated = replace(lease, status=observed, updated_at=self._clock())
        with self._lock:
            self._save(updated)
            self._record("workspace.status_observed", updated, {})
        return updated

    def cost(self, lease_id: str) -> float:
        lease = self.get(lease_id)
        return 0.0 if lease.provider == "local" else self._provider(lease).cost(lease)

    def checkpoint(self, lease_id: str, label: str) -> WorkspaceCheckpoint:
        lease = self.get(lease_id)
        if lease.status not in {"ready", "running"}:
            raise WorkspaceError("workspace is not checkpointable")
        if lease.provider == "local":
            commit = self._git_checkpoint(Path(lease.workspace), label)
        else:
            adapter = self._provider(lease)
            commit = adapter.checkpoint(lease, label)
        updated = replace(lease, checkpoint=commit, updated_at=self._clock())
        with self._lock:
            self._save(updated)
            self._record("workspace.checkpointed", updated, {"checkpoint": commit, "label": label})
        return WorkspaceCheckpoint(lease.id, commit, label, self._clock())

    def sleep(self, lease_id: str) -> WorkspaceLease:
        return self._transition(lease_id, "sleeping", "workspace.slept", "sleep")

    def resume(self, lease_id: str) -> WorkspaceLease:
        return self._transition(lease_id, "ready", "workspace.resumed", "resume")

    def preview(self, lease_id: str) -> str:
        lease = self.get(lease_id)
        if lease.status != "ready":
            raise WorkspaceError("workspace is not ready for preview")
        if lease.provider == "local":
            target = Path(lease.workspace).as_uri()
        else:
            target = self._provider(lease).preview(lease)
        self._record("workspace.previewed", lease, {"private": True, "target_kind": "local" if lease.provider == "local" else "provider"})
        return target

    def signed_preview(
        self,
        lease_id: str,
        signer: object,
        path_prefix: str,
        *,
        ttl_seconds: int = 300,
        origin: str = "muse://desktop",
    ) -> str:
        lease = self.get(lease_id)
        if lease.status != "ready":
            raise WorkspaceError("workspace is not ready for preview")
        issue = getattr(signer, "issue", None)
        if not callable(issue):
            raise TypeError("preview signer must provide issue()")
        token = str(
            issue(
                lease.id,
                path_prefix,
                ttl_seconds=ttl_seconds,
                origin=origin,
            )
        )
        self._record(
            "workspace.preview_signed",
            lease,
            {"private": True, "path_prefix": path_prefix, "expires_in_seconds": ttl_seconds},
        )
        return token

    def destroy(self, lease_id: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        workspace = Path(lease.workspace).resolve()
        if not workspace.is_relative_to(self.root.resolve()):
            raise WorkspaceError("refusing to destroy outside workspace root")
        if lease.provider == "local":
            subprocess.run(
                ["git", "-C", lease.project_root, "worktree", "remove", "--force", str(workspace)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if workspace.exists():
                shutil.rmtree(workspace)
        else:
            self._provider(lease).destroy(lease)
        updated = replace(lease, status="destroyed", updated_at=self._clock())
        with self._lock:
            self._save(updated)
            self._record("workspace.destroyed", updated, {"rollback": "restore_checkpoint", "checkpoint": lease.checkpoint})
        return updated

    def _transition(self, lease_id: str, status: str, event: str, action: str) -> WorkspaceLease:
        lease = self.get(lease_id)
        if lease.status in {"destroyed", "failed", "unavailable"}:
            raise WorkspaceError(f"cannot {action} workspace in {lease.status} state")
        if lease.provider != "local":
            getattr(self._provider(lease), action)(lease)
        updated = replace(
            lease,
            status=status,
            updated_at=self._clock(),
            actual_cost_usd=(self._provider(lease).cost(lease) if lease.provider != "local" else 0.0),
        )
        with self._lock:
            self._save(updated)
            self._record(event, updated, {"rollback": "resume" if status == "sleeping" else "sleep"})
        return updated

    def _provider(self, lease: WorkspaceLease) -> WorkspaceProvider:
        provider = self._providers.get(lease.provider)
        if provider is None:
            raise WorkspaceUnavailable(lease.unavailable_reason or "provider unavailable")
        return provider

    @staticmethod
    def _create_local(source: Path, workspace: Path) -> None:
        result = subprocess.run(
            ["git", "-C", str(source), "worktree", "add", "--detach", str(workspace), "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise WorkspaceUnavailable("local Git worktree creation failed")

    @staticmethod
    def _git_checkpoint(workspace: Path, label: str) -> str:
        subprocess.run(["git", "-C", str(workspace), "add", "-A"], capture_output=True, timeout=60, check=True)
        result = subprocess.run(
            [
                "git", "-C", str(workspace),
                "-c", "user.name=MUSE Fabrication",
                "-c", "user.email=muse-fabrication@localhost",
                "commit", "--allow-empty", "-m", f"checkpoint: {label[:120]}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        del result
        head = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return head.stdout.strip()

    def _records(self) -> dict[str, dict[str, Any]]:
        if not self._state_path.exists():
            return {}
        value = json.loads(self._state_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    def _save(self, lease: WorkspaceLease) -> None:
        records = self._records()
        records[lease.id] = asdict(lease)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)

    def _record(self, event_type: str, lease: WorkspaceLease, details: Mapping[str, Any]) -> None:
        payload = {
            "event_type": event_type,
            "occurred_at": self._clock(),
            "lease_id": lease.id,
            "provider": lease.provider,
            "status": lease.status,
            "estimated_cost_usd": lease.estimated_cost_usd,
            "actual_cost_usd": lease.actual_cost_usd,
            **dict(details),
        }
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
        if self._event_sink is not None:
            self._event_sink(event_type, payload)


__all__ = [
    "DaytonaWorkspaceProvider",
    "DelegatingWorkspaceProvider",
    "ModalWorkspaceProvider",
    "VercelWorkspaceProvider",
    "WorkspaceAuthorizationError",
    "WorkspaceBroker",
    "WorkspaceCheckpoint",
    "WorkspaceError",
    "WorkspaceLease",
    "WorkspaceUnavailable",
]
