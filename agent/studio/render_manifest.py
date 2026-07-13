"""Deterministic two-eye render records and completeness validation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Iterable


@dataclass(frozen=True)
class RenderFrameRecord:
    shot_id: str
    frame: int
    eye: str
    scene_revision: str
    seed: int
    renderer: str
    renderer_version: str
    settings_hash: str
    input_asset_hashes: tuple[str, ...]
    output_hash: str
    attempt: int
    worker: str
    started_at: str
    completed_at: str
    status: str
    output_path: str = ""
    timecode_seconds: float = 0.0
    error: str = ""

    def __post_init__(self) -> None:
        if self.eye not in {"left", "right"}:
            raise ValueError("render eye must be left or right")
        if type(self.frame) is not int or self.frame < 0:
            raise ValueError("frame must be a non-negative integer")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")
        if self.status not in {"queued", "rendering", "completed", "failed"}:
            raise ValueError("render status is invalid")
        if not math.isfinite(float(self.timecode_seconds)):
            raise ValueError("timecode must be finite")
        if self.status == "completed" and not self.output_hash:
            raise ValueError("completed render frames require an output hash")

    def retry(self, *, worker: str = "", started_at: str = "") -> RenderFrameRecord:
        return replace(
            self,
            output_hash="",
            attempt=self.attempt + 1,
            worker=worker or self.worker,
            started_at=started_at,
            completed_at="",
            status="queued",
            error="",
        )


@dataclass(frozen=True)
class RenderValidation:
    passed: bool
    failures: tuple[str, ...]


@dataclass
class RenderManifest:
    records: list[RenderFrameRecord] = field(default_factory=list)
    max_time_mismatch_seconds: float = 0.0005

    def add(self, record: RenderFrameRecord) -> None:
        key = (record.shot_id, record.frame, record.eye, record.attempt)
        if any((item.shot_id, item.frame, item.eye, item.attempt) == key for item in self.records):
            raise ValueError("duplicate render attempt")
        self.records.append(record)

    def latest(self) -> tuple[RenderFrameRecord, ...]:
        latest: dict[tuple[str, int, str], RenderFrameRecord] = {}
        for record in self.records:
            key = (record.shot_id, record.frame, record.eye)
            current = latest.get(key)
            if current is None or record.attempt > current.attempt:
                latest[key] = record
        return tuple(latest[key] for key in sorted(latest))

    def validate(self) -> RenderValidation:
        failures: list[str] = []
        latest = self.latest()
        by_frame: dict[tuple[str, int], dict[str, RenderFrameRecord]] = {}
        hashes: dict[str, tuple[str, int, str]] = {}
        for record in latest:
            if record.status != "completed":
                failures.append("incomplete_frame")
            frame_key = (record.shot_id, record.frame)
            by_frame.setdefault(frame_key, {})[record.eye] = record
            prior = hashes.get(record.output_hash) if record.output_hash else None
            record_key = (record.shot_id, record.frame, record.eye)
            if prior is not None and prior != record_key:
                failures.append("output_hash_collision")
            elif record.output_hash:
                hashes[record.output_hash] = record_key
        for eyes in by_frame.values():
            if set(eyes) != {"left", "right"}:
                failures.append("missing_eye")
                continue
            left, right = eyes["left"], eyes["right"]
            if left.scene_revision != right.scene_revision:
                failures.append("scene_revision_mismatch")
            if left.seed != right.seed or left.settings_hash != right.settings_hash:
                failures.append("determinism_mismatch")
            if abs(left.timecode_seconds - right.timecode_seconds) > self.max_time_mismatch_seconds:
                failures.append("time_mismatch")
        shots: dict[str, dict[str, set[int]]] = {}
        for record in latest:
            shots.setdefault(record.shot_id, {"left": set(), "right": set()})[record.eye].add(record.frame)
        for eyes in shots.values():
            if eyes["left"] != eyes["right"]:
                failures.append("frame_count_mismatch")
        unique = tuple(dict.fromkeys(failures))
        return RenderValidation(not unique and bool(latest), unique or (() if latest else ("empty_manifest",)))

    @classmethod
    def from_records(cls, records: Iterable[RenderFrameRecord]) -> RenderManifest:
        manifest = cls()
        for record in records:
            manifest.add(record)
        return manifest


__all__ = ["RenderFrameRecord", "RenderManifest", "RenderValidation"]
