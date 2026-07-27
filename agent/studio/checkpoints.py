"""Resumable checkpoints for AAA pipeline stages."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


class PipelineStage(str, Enum):
    DECOMPOSE = "decompose"
    PREVIS = "previs"
    ASSET_GENERATION = "asset_generation"
    BLENDER_POST = "blender_post"
    CREATURE_RIG = "creature_rig"
    WORLD_SYSTEMS = "world_systems"
    UE5_SOURCE = "ue5_source"
    PROVENANCE = "provenance"
    VALIDATION = "validation"
    ACCEPTANCE = "acceptance"
    COMPLETE = "complete"


STAGE_ORDER: tuple[PipelineStage, ...] = tuple(PipelineStage)


@dataclass
class StageCheckpoint:
    stage: str
    status: str
    started_at: float
    completed_at: float | None
    artifacts: list[str]
    error: str = ""
    metadata: dict[str, Any] | None = None


@dataclass
class PipelineCheckpoint:
    project_id: str
    profile: str
    current_stage: str
    stages: list[StageCheckpoint]
    version: str = "1.0"

    def path_for(self, root: Path) -> Path:
        return root / "checkpoints" / "pipeline_checkpoint.json"

    def write(self, root: Path) -> Path:
        path = self.path_for(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, root: Path) -> PipelineCheckpoint | None:
        path = root / "checkpoints" / "pipeline_checkpoint.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        stages = [StageCheckpoint(**s) for s in data.get("stages", [])]
        return cls(
            project_id=data["project_id"],
            profile=data["profile"],
            current_stage=data["current_stage"],
            stages=stages,
            version=data.get("version", "1.0"),
        )

    def stage_record(self, stage: PipelineStage) -> StageCheckpoint | None:
        for record in self.stages:
            if record.stage == stage.value:
                return record
        return None

    def is_stage_complete(self, stage: PipelineStage) -> bool:
        record = self.stage_record(stage)
        return record is not None and record.status == "complete"

    def next_pending_stage(self) -> PipelineStage | None:
        for stage in STAGE_ORDER:
            if not self.is_stage_complete(stage):
                return stage
        return None

    def completed_stages(self) -> tuple[str, ...]:
        return tuple(s.stage for s in self.stages if s.status == "complete")


def create_checkpoint(project_id: str, profile: str) -> PipelineCheckpoint:
    return PipelineCheckpoint(
        project_id=project_id,
        profile=profile,
        current_stage=PipelineStage.DECOMPOSE.value,
        stages=[],
    )


def begin_stage(checkpoint: PipelineCheckpoint, stage: PipelineStage) -> StageCheckpoint:
    record = StageCheckpoint(
        stage=stage.value,
        status="in_progress",
        started_at=time.time(),
        completed_at=None,
        artifacts=[],
    )
    checkpoint.stages.append(record)
    checkpoint.current_stage = stage.value
    return record


def complete_stage(
    checkpoint: PipelineCheckpoint,
    stage: PipelineStage,
    artifacts: Sequence[str],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    record = checkpoint.stage_record(stage)
    if record is None:
        record = begin_stage(checkpoint, stage)
    record.status = "complete"
    record.completed_at = time.time()
    record.artifacts = list(artifacts)
    if metadata:
        record.metadata = dict(metadata)


def fail_stage(
    checkpoint: PipelineCheckpoint,
    stage: PipelineStage,
    error: str,
) -> None:
    record = checkpoint.stage_record(stage)
    if record is None:
        record = begin_stage(checkpoint, stage)
    record.status = "failed"
    record.completed_at = time.time()
    record.error = error


__all__ = [
    "PipelineCheckpoint",
    "PipelineStage",
    "STAGE_ORDER",
    "StageCheckpoint",
    "begin_stage",
    "complete_stage",
    "create_checkpoint",
    "fail_stage",
]
