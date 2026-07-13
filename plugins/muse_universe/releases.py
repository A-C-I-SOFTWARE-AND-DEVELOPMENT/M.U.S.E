"""Verified release promotion, durable provider evidence, and rollback."""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from hermes_constants import get_hermes_home


RELEASE_STATES = (
    "draft", "verified", "staged", "awaiting_owner", "publishing",
    "live", "failed", "rolled_back",
)
REQUIRED_GATES = (
    "verification", "provenance", "rights", "security", "performance", "accessibility"
)


class ReleaseError(RuntimeError):
    pass


class ReleaseBlocked(ReleaseError):
    def __init__(self, failed_gates: tuple[str, ...]) -> None:
        self.failed_gates = failed_gates
        super().__init__("release blocked by gates: " + ", ".join(failed_gates))


class ReleaseAdapter(Protocol):
    def publish(self, candidate: object) -> Mapping[str, Any]: ...
    def rollback(self, release: object) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PrivatePreview:
    id: str
    project_id: str
    version: str
    visibility: str
    created_at: float
    production_eligible: bool = False


@dataclass(frozen=True)
class ReleaseRecord:
    id: str
    project_id: str
    version: str
    status: str
    gates: Mapping[str, str]
    artifact_ref: str
    rollback_source: str
    created_at: float
    updated_at: float
    approval_id: str = ""
    provider: str = ""
    deployment_id: str = ""
    public_url: str = ""
    previous_release_id: str = ""
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0
    partial_success: bool = False
    failure_reason: str = ""
    recovery_instruction: str = ""
    transition_history: tuple[str, ...] = ("draft",)

    @property
    def state(self) -> str:
        return self.status


ApprovalVerifier = Callable[[str, str, str], bool]
EventSink = Callable[[str, Mapping[str, Any]], None]


def _value(subject: object, name: str, default: Any = None) -> Any:
    if isinstance(subject, Mapping):
        return subject.get(name, default)
    return getattr(subject, name, default)


def _gate_passed(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() in {"passed", "pass", "verified", "approved", "complete"}
    return False


def _cost(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


class ReleaseManager:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        approval_verifier: ApprovalVerifier | None = None,
        event_sink: EventSink | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = Path(root) if root else Path(get_hermes_home()) / "universe/releases"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "release-state.json"
        self.events_path = self.root / "release-events.jsonl"
        self.approval_verifier = approval_verifier
        self.event_sink = event_sink
        self.clock = clock
        self._releases: dict[str, ReleaseRecord] = {}
        self._public: dict[str, str] = {}
        self._load()

    def create_preview(self, artifact: object) -> PrivatePreview:
        project_id = str(_value(artifact, "project_id", ""))
        if not project_id:
            raise ValueError("preview artifact requires project_id")
        preview = PrivatePreview(
            id="preview_" + uuid4().hex,
            project_id=project_id,
            version=str(_value(artifact, "version", "preview")),
            visibility="private",
            created_at=self.clock(),
        )
        self._event("release.preview_created", asdict(preview))
        return preview

    def stage(self, bundle: object) -> ReleaseRecord:
        project_id = str(_value(bundle, "project_id", ""))
        version = str(_value(bundle, "version", ""))
        if not project_id or not version:
            raise ValueError("release bundle requires project_id and version")
        gates_value = _value(bundle, "gates", {})
        gates = dict(gates_value) if isinstance(gates_value, Mapping) else {}
        for name in REQUIRED_GATES:
            direct = _value(bundle, name, None)
            if name not in gates and direct is not None:
                gates[name] = direct
        failed = tuple(name for name in REQUIRED_GATES if not _gate_passed(gates.get(name)))
        if failed:
            raise ReleaseBlocked(failed)
        existing = self._find(project_id, version, statuses={"staged", "awaiting_owner", "publishing", "live"})
        if existing is not None:
            return existing
        now = self.clock()
        record = ReleaseRecord(
            id="release_" + uuid4().hex,
            project_id=project_id,
            version=version,
            status="staged",
            gates={name: "passed" for name in REQUIRED_GATES},
            artifact_ref=str(_value(bundle, "artifact_ref", _value(bundle, "id", ""))),
            rollback_source=str(_value(bundle, "rollback_source", "")),
            created_at=now,
            updated_at=now,
            estimated_cost_usd=_cost(
                _value(bundle, "estimated_cost_usd", 0.0) or 0.0,
                "estimated release cost",
            ),
            transition_history=("draft", "verified", "staged"),
        )
        if not record.rollback_source:
            raise ReleaseBlocked(("rollback_source",))
        self._store(record, "release.staged")
        return record

    def promote(
        self,
        candidate: object,
        *,
        approval_id: str,
        adapter: ReleaseAdapter,
    ) -> ReleaseRecord:
        staged = candidate if isinstance(candidate, ReleaseRecord) else self.stage(candidate)
        if staged.status == "live":
            return staged
        if staged.status not in {"staged", "awaiting_owner", "failed"}:
            raise ReleaseError(f"release cannot promote from {staged.status}")
        if not approval_id:
            raise ReleaseBlocked(("owner_approval",))
        if self.approval_verifier is not None and not self.approval_verifier(
            approval_id, staged.project_id, staged.version
        ):
            raise ReleaseBlocked(("owner_approval",))
        current = self.current_public(staged.project_id)
        awaiting = self._transition(staged, "awaiting_owner", approval_id=approval_id)
        publishing = self._transition(
            awaiting,
            "publishing",
            previous_release_id=current.id if current else "",
        )
        try:
            response = dict(adapter.publish(publishing))
            success = response.get("success", True) is True
            if not success:
                raise ReleaseError(str(response.get("error", "provider publish failed")))
            deployment_id = str(response.get("deployment_id", ""))
            public_url = str(response.get("url", response.get("public_url", "")))
            if not deployment_id or not public_url:
                raise ReleaseError("provider publish omitted deployment id or public URL")
            parsed_url = urlparse(public_url)
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                raise ReleaseError("provider public URL must be absolute HTTPS")
            live = self._transition(
                publishing,
                "live",
                provider=str(response.get("provider", type(adapter).__name__)),
                deployment_id=deployment_id,
                public_url=public_url,
                actual_cost_usd=_cost(
                    response.get("actual_cost_usd", 0.0) or 0.0,
                    "actual release cost",
                ),
                partial_success=False,
                failure_reason="",
            )
            self._public[live.project_id] = live.id
            self._persist()
            return live
        except Exception as exc:  # provider failures are durable evidence
            failed = self._transition(
                publishing,
                "failed",
                partial_success=False,
                failure_reason=f"{type(exc).__name__}: {exc}",
                recovery_instruction="Inspect provider evidence, correct the failure, and retry the same version.",
            )
            return failed

    def rollback(
        self,
        project_id: str,
        *,
        reason: str,
        adapter: ReleaseAdapter,
    ) -> ReleaseRecord:
        current = self.current_public(project_id)
        if current is None:
            raise ReleaseError("project has no live release")
        if not reason.strip():
            raise ValueError("rollback reason is required")
        previous = self._releases.get(current.previous_release_id)
        if previous is None:
            failed = self._transition(
                current,
                "failed",
                failure_reason="no prior durable release is available",
                recovery_instruction="Restore the provider deployment identified by rollback_source manually.",
            )
            return failed
        try:
            response = dict(adapter.rollback(previous))
            if response.get("success", True) is not True:
                raise ReleaseError(str(response.get("error", "provider rollback failed")))
            rolled_back = self._transition(
                current,
                "rolled_back",
                failure_reason=reason,
                recovery_instruction="",
            )
            self._public[project_id] = previous.id
            self._persist()
            return rolled_back
        except Exception as exc:
            return self._transition(
                current,
                "failed",
                failure_reason=f"{type(exc).__name__}: {exc}",
                recovery_instruction="Use the prior deployment id and rollback source for provider recovery.",
            )

    def current_public(self, project_id: str) -> ReleaseRecord | None:
        release_id = self._public.get(project_id)
        return self._releases.get(release_id) if release_id else None

    def _transition(self, record: ReleaseRecord, status: str, **changes: Any) -> ReleaseRecord:
        if status not in RELEASE_STATES:
            raise ValueError("invalid release state")
        updated = replace(
            record,
            status=status,
            updated_at=self.clock(),
            transition_history=record.transition_history + (status,),
            **changes,
        )
        self._store(updated, f"release.{status}")
        return updated

    def _store(self, record: ReleaseRecord, event_type: str) -> None:
        self._releases[record.id] = record
        self._persist()
        payload = asdict(record)
        payload["event_type"] = event_type
        self._event(event_type, payload)

    def _find(
        self, project_id: str, version: str, *, statuses: set[str]
    ) -> ReleaseRecord | None:
        matches = [
            record for record in self._releases.values()
            if record.project_id == project_id and record.version == version and record.status in statuses
        ]
        return max(matches, key=lambda item: item.updated_at) if matches else None

    def _persist(self) -> None:
        payload = {
            "releases": {key: asdict(value) for key, value in self._releases.items()},
            "public": self._public,
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_path)

    def _load(self) -> None:
        if not self.state_path.is_file():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        for key, value in payload.get("releases", {}).items():
            value["transition_history"] = tuple(value.get("transition_history", ()))
            self._releases[key] = ReleaseRecord(**value)
        self._public = dict(payload.get("public", {}))

    def _event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        safe = {key: value for key, value in payload.items() if "token" not in key.lower() and "secret" not in key.lower()}
        safe["event_type"] = event_type
        safe["occurred_at"] = self.clock()
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, sort_keys=True) + "\n")
        if self.event_sink is not None:
            self.event_sink(event_type, safe)


__all__ = [
    "PrivatePreview",
    "RELEASE_STATES",
    "REQUIRED_GATES",
    "ReleaseBlocked",
    "ReleaseError",
    "ReleaseManager",
    "ReleaseRecord",
]
