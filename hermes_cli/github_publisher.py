"""GitHub publisher for Hermes orchestration artifacts.

The publisher's contract: take a validated :class:`MergeArtifact` and emit
an artifact descriptor (PR or Issue) that an operator — or a GitHub
Actions workflow with the right permissions — can hand off to GitHub.

By default the publisher runs in **dry-run** mode: it writes the
descriptor JSON to ``.hermes/publish/`` and never contacts the network.
Network mode is opt-in via the ``HERMES_PUBLISH_LIVE=1`` env var AND a
caller-supplied transport. There is no embedded credential path.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Callable, Literal

from hermes_cli.merge_engine import MergeArtifact
from hermes_cli.validation_gates import ValidationReport


PublishKind = Literal["pull_request", "issue"]


@dataclasses.dataclass
class PublishDescriptor:
    kind: PublishKind
    repo: str
    title: str
    body: str
    labels: list[str]
    head_branch: str | None = None
    base_branch: str | None = "main"
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class PublishResult:
    descriptor: PublishDescriptor
    dry_run_path: Path | None
    transport_response: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.to_dict(),
            "dry_run_path": str(self.dry_run_path) if self.dry_run_path else None,
            "transport_response": self.transport_response,
        }


class PublishRejected(RuntimeError):
    """Raised when validation gates did not pass and publishing was attempted."""


def _force_dry_run() -> bool:
    return os.environ.get("HERMES_PUBLISH_LIVE", "").strip() != "1"


def build_descriptor(
    artifact: MergeArtifact,
    *,
    repo: str,
    kind: PublishKind = "pull_request",
    labels: list[str] | None = None,
    head_branch: str | None = None,
    base_branch: str | None = "main",
    dry_run: bool | None = None,
) -> PublishDescriptor:
    resolved_dry = _force_dry_run() if dry_run is None else dry_run
    return PublishDescriptor(
        kind=kind,
        repo=repo,
        title=artifact.title,
        body=artifact.body,
        labels=list(labels or ["hermes-orchestration"]),
        head_branch=head_branch,
        base_branch=base_branch,
        dry_run=resolved_dry,
    )


def publish(
    artifact: MergeArtifact,
    validation: ValidationReport,
    *,
    repo: str,
    out_dir: Path,
    kind: PublishKind = "pull_request",
    labels: list[str] | None = None,
    head_branch: str | None = None,
    base_branch: str | None = "main",
    dry_run: bool | None = None,
    transport: Callable[[PublishDescriptor], dict[str, Any]] | None = None,
) -> PublishResult:
    if not validation.passed:
        failed = [g.name for g in validation.gates if not g.passed]
        raise PublishRejected(f"validation gates failed: {failed}")

    descriptor = build_descriptor(
        artifact,
        repo=repo,
        kind=kind,
        labels=labels,
        head_branch=head_branch,
        base_branch=base_branch,
        dry_run=dry_run,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sanitized_title = "".join(c if c.isalnum() else "_" for c in descriptor.title)[:60]
    dry_path = out_dir / f"{descriptor.kind}_{sanitized_title}.json"
    dry_path.write_text(json.dumps(descriptor.to_dict(), indent=2, sort_keys=True))

    if descriptor.dry_run or transport is None:
        return PublishResult(descriptor=descriptor, dry_run_path=dry_path, transport_response=None)

    response = transport(descriptor)
    return PublishResult(descriptor=descriptor, dry_run_path=dry_path, transport_response=response)
