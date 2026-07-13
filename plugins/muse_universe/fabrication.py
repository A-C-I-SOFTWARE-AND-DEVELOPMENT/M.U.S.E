"""Lease-bounded visual source editing, verification, apply, and rollback."""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence
from uuid import uuid4

from agent.studio.source_map import SourceRef, SourceRegistry

from .preview_signing import PreviewSigner
from .workspaces import WorkspaceBroker, WorkspaceCheckpoint


class FabricationError(RuntimeError):
    pass


class FabricationGateError(FabricationError):
    pass


@dataclass(frozen=True)
class FabricationEdit:
    id: str
    component_id: str
    source: SourceRef
    diff: str
    before_hash: str
    after_hash: str
    affected_files: tuple[str, ...]
    affected_tests: tuple[str, ...]
    state: str = "edited"


@dataclass(frozen=True)
class GateResult:
    name: str
    argv: tuple[str, ...]
    required: bool
    exit_code: int
    stdout: str
    stderr: str
    passed: bool


@dataclass(frozen=True)
class FabricationVerification:
    passed: bool
    results: tuple[GateResult, ...]


@dataclass(frozen=True)
class FabricationApplyResult:
    edit_id: str
    status: str
    checkpoint: WorkspaceCheckpoint | None
    diff: str


Runner = Callable[..., subprocess.CompletedProcess[str]]
ApprovalVerifier = Callable[[str, str], bool]
InstructionExecutor = Callable[[str, Path], Sequence[str]]
EventSink = Callable[[str, Mapping[str, object]], None]


class FabricationSession:
    """A single isolated-workspace edit session; never a public release surface."""

    def __init__(
        self,
        workspace: str | Path,
        source_registry: SourceRegistry,
        *,
        lease_id: str = "",
        actor_id: str = "",
        broker: WorkspaceBroker | None = None,
        commands: Mapping[str, Sequence[str]] | None = None,
        required_gates: Sequence[str] = (
            "lint", "typecheck", "test", "accessibility", "performance"
        ),
        runner: Runner = subprocess.run,
        approval_verifier: ApprovalVerifier | None = None,
        instruction_executor: InstructionExecutor | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        if self.workspace != source_registry.workspace:
            raise ValueError("source registry must be bound to the fabrication workspace")
        self.registry = source_registry
        self.lease_id = lease_id
        self.actor_id = actor_id
        self.broker = broker
        self.commands = {name: tuple(argv) for name, argv in (commands or {}).items()}
        self.required_gates = tuple(required_gates)
        self.runner = runner
        self.approval_verifier = approval_verifier
        self.instruction_executor = instruction_executor
        self.event_sink = event_sink
        self.edits: dict[str, FabricationEdit] = {}
        self._originals: dict[str, str] = {}
        self._latest_verification: FabricationVerification | None = None

    def execute(self, command: str, **payload: object) -> object:
        """Dispatch the stable fabrication command contract."""

        if command == "fabrication.select":
            return self.select(
                str(payload["component_id"]),
                revision=payload.get("revision") if isinstance(payload.get("revision"), str) else None,
            )
        if command == "fabrication.edit":
            return self.edit(
                str(payload["component_id"]),
                payload.get("replacement"),
                expected_text=(
                    payload.get("expected_text")
                    if isinstance(payload.get("expected_text"), str)
                    else None
                ),
                revision=payload.get("revision") if isinstance(payload.get("revision"), str) else None,
            )
        if command == "fabrication.verify":
            return self.verify()
        if command == "fabrication.apply":
            return self.apply(str(payload["edit_id"]))
        if command == "fabrication.rollback":
            return self.rollback(str(payload["edit_id"]))
        if command == "release.stage":
            return self.stage_release(
                str(payload["edit_id"]), approval_id=str(payload.get("approval_id", ""))
            )
        raise FabricationError(f"unsupported fabrication command: {command}")

    def select(self, component_id: str, *, revision: str | None = None) -> SourceRef:
        return self.registry.resolve(component_id, revision=revision)

    def edit(
        self,
        component_id: str,
        replacement: object,
        *,
        expected_text: str | None = None,
        revision: str | None = None,
        affected_tests: Sequence[str] = (),
    ) -> FabricationEdit:
        source = self.select(component_id, revision=revision)
        path = self._source_path(source)
        before = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json" and expected_text is None:
            after = self._edit_json(before, source.property_path, replacement)
        else:
            if expected_text is None or not isinstance(replacement, str):
                raise FabricationError("text edits require expected_text and a string replacement")
            occurrences = before.count(expected_text)
            if occurrences != 1:
                raise FabricationError("expected source text must match exactly once")
            after = before.replace(expected_text, replacement, 1)
        if before == after:
            raise FabricationError("edit produced no source change")
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{source.file}",
                tofile=f"b/{source.file}",
            )
        )
        edit_id = "edit_" + uuid4().hex
        path.write_text(after, encoding="utf-8")
        edit = FabricationEdit(
            id=edit_id,
            component_id=component_id,
            source=source,
            diff=diff,
            before_hash=self._hash(before),
            after_hash=self._hash(after),
            affected_files=(source.file,),
            affected_tests=tuple(affected_tests),
        )
        self.edits[edit_id] = edit
        self._originals[edit_id] = before
        self._latest_verification = None
        self._record(
            "fabrication.edited",
            {"edit_id": edit_id, "diff_hash": self._hash(diff), "files": edit.affected_files},
        )
        return edit

    def edit_by_instruction(self, instruction: str) -> tuple[str, ...]:
        if self.instruction_executor is None:
            raise FabricationError("coding-plan instruction executor is unavailable")
        if not instruction.strip():
            raise ValueError("fabrication instruction is required")
        files = tuple(str(path) for path in self.instruction_executor(instruction, self.workspace))
        for relative in files:
            self._bounded_path(relative)
        self._latest_verification = None
        return files

    def verify(
        self,
        commands: Mapping[str, Sequence[str]] | None = None,
    ) -> FabricationVerification:
        configured = self.commands if commands is None else {
            name: tuple(argv) for name, argv in commands.items()
        }
        results: list[GateResult] = []
        for name, argv in configured.items():
            if not argv:
                raise ValueError(f"{name} gate command cannot be empty")
            completed = self.runner(
                list(argv),
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
            required = name in self.required_gates
            results.append(
                GateResult(
                    name=name,
                    argv=tuple(argv),
                    required=required,
                    exit_code=int(completed.returncode),
                    stdout=completed.stdout or "",
                    stderr=completed.stderr or "",
                    passed=completed.returncode == 0,
                )
            )
        present = {result.name for result in results}
        missing = [name for name in self.required_gates if name not in present]
        results.extend(
            GateResult(name, (), True, -1, "", "gate command is not configured", False)
            for name in missing
        )
        passed = all(result.passed for result in results if result.required)
        self._latest_verification = FabricationVerification(passed, tuple(results))
        self._record(
            "fabrication.verified",
            {
                "passed": passed,
                "gates": {result.name: result.exit_code for result in results},
            },
        )
        return self._latest_verification

    def apply(self, edit_id: str) -> FabricationApplyResult:
        edit = self._edit(edit_id)
        if self._latest_verification is None or not self._latest_verification.passed:
            raise FabricationGateError("all required verification gates must pass before Apply")
        checkpoint: WorkspaceCheckpoint
        if self.broker is not None:
            if not self.lease_id:
                raise FabricationError("broker-backed Apply requires a lease id")
            checkpoint = self.broker.checkpoint(self.lease_id, f"before apply {edit_id}")
        else:
            checkpoint = WorkspaceCheckpoint(
                self.lease_id,
                edit.before_hash,
                f"before apply {edit_id}",
                0.0,
            )
        applied = replace(edit, state="applied")
        self.edits[edit_id] = applied
        self._record(
            "fabrication.applied",
            {"edit_id": edit_id, "checkpoint": checkpoint.commit},
        )
        return FabricationApplyResult(edit_id, "applied", checkpoint, edit.diff)

    def rollback(self, edit_id: str) -> FabricationApplyResult:
        edit = self._edit(edit_id)
        before = self._originals[edit_id]
        self._source_path(edit.source).write_text(before, encoding="utf-8")
        rolled_back = replace(edit, state="rolled_back")
        self.edits[edit_id] = rolled_back
        self._latest_verification = None
        self._record("fabrication.rolled_back", {"edit_id": edit_id})
        return FabricationApplyResult(edit_id, "rolled_back", None, edit.diff)

    def stage_release(self, edit_id: str, *, approval_id: str) -> dict[str, object]:
        edit = self._edit(edit_id)
        if edit.state != "applied":
            raise FabricationGateError("only an applied edit can be staged for release")
        if not approval_id or self.approval_verifier is None or not self.approval_verifier(
            approval_id, self.actor_id
        ):
            raise FabricationGateError("owner approval is required to stage a release")
        payload = {
            "command": "release.stage",
            "edit_id": edit_id,
            "approval_id": approval_id,
            "visibility": "private",
            "public_promotion": False,
            "diff": edit.diff,
        }
        self._record(
            "release.staged",
            {key: value for key, value in payload.items() if key != "diff"},
        )
        return payload

    def issue_preview(
        self,
        signer: PreviewSigner,
        path_prefix: str,
        *,
        origin: str = "muse://desktop",
        ttl_seconds: int = 300,
        health_check: Callable[[Path], bool] | None = None,
    ) -> str:
        if health_check is None or not health_check(self.workspace):
            raise FabricationError("preview health check did not pass")
        if not self.lease_id:
            raise FabricationError("signed previews require a lease id")
        token = signer.issue(
            self.lease_id,
            path_prefix,
            ttl_seconds=ttl_seconds,
            origin=origin,
        )
        self._record(
            "fabrication.preview_issued",
            {"lease_id": self.lease_id, "path_prefix": path_prefix, "private": True},
        )
        return token

    @staticmethod
    def _hash(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _edit_json(source: str, property_path: str, replacement: object) -> str:
        data = json.loads(source)
        target = data
        parts = property_path.split(".")
        for part in parts[:-1]:
            if not isinstance(target, dict) or part not in target:
                raise FabricationError("structured property path does not exist")
            target = target[part]
        if not isinstance(target, dict) or parts[-1] not in target:
            raise FabricationError("structured property path does not exist")
        target[parts[-1]] = replacement
        return json.dumps(data, indent=2, sort_keys=True) + "\n"

    def _source_path(self, source: SourceRef) -> Path:
        path = self._bounded_path(source.file)
        if not path.is_file():
            raise FabricationError("mapped source file does not exist")
        return path

    def _bounded_path(self, value: str | Path) -> Path:
        path = (self.workspace / value).resolve()
        if not path.is_relative_to(self.workspace):
            raise FabricationError("fabrication path escapes the workspace")
        return path

    def _edit(self, edit_id: str) -> FabricationEdit:
        try:
            return self.edits[edit_id]
        except KeyError as exc:
            raise KeyError(f"unknown fabrication edit: {edit_id}") from exc

    def _record(self, event_type: str, payload: Mapping[str, object]) -> None:
        if self.event_sink is not None:
            self.event_sink(event_type, dict(payload))


__all__ = [
    "FabricationApplyResult",
    "FabricationEdit",
    "FabricationError",
    "FabricationGateError",
    "FabricationSession",
    "FabricationVerification",
    "GateResult",
]
