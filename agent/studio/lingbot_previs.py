"""Typed LingBot/Reactor previsualization contract for Game Studio.

LingBot is deliberately non-authoritative: it emits RGB reference video only.
The UE camera keyframes remain the source of truth for the game build.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable


ROUTER = (
    Path.home()
    / "models"
    / "lingbot-world-v2"
    / "muse"
    / "world_vision_router.py"
)


@dataclass(frozen=True)
class CameraKeyframe:
    location_cm: tuple[float, float, float]
    rotation_deg: tuple[float, float, float]  # pitch, yaw, roll
    fov_degrees: float = 60.0


@dataclass(frozen=True)
class PrevisRequest:
    prompt: str
    source_image: Path
    camera_keyframes: tuple[CameraKeyframe, ...]
    output_dir: Path
    trajectory_id: str
    width: int = 832
    height: int = 480
    requested_frames: int = 81
    seed: int = 42
    force_backend: str = "auto"  # auto | lingbot | reactor

    def __post_init__(self) -> None:
        if len(self.prompt.strip()) < 10:
            raise ValueError("previs prompt is too short")
        if len(self.camera_keyframes) < 2:
            raise ValueError("previs needs at least two UE camera keyframes")
        if self.force_backend not in {"auto", "lingbot", "reactor"}:
            raise ValueError("force_backend must be auto, lingbot, or reactor")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("video dimensions must be positive")
        if self.requested_frames < 5:
            raise ValueError("requested_frames must be at least 5")


@dataclass(frozen=True)
class PrevisResult:
    ok: bool
    status: str
    backend: str
    video_path: str = ""
    artifact_type: str = "rgb_video_only"
    metadata: dict[str, object] = field(default_factory=dict)
    license: dict[str, object] = field(default_factory=dict)
    conditioning_dir: str = ""
    error: str = ""


def _rotation_basis(rotation: tuple[float, float, float]) -> tuple[tuple[float, ...], ...]:
    pitch, yaw, roll = (math.radians(value) for value in rotation)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cr, sr = math.cos(roll), math.sin(roll)
    forward = (cp * cy, cp * sy, sp)
    right = (
        cy * sp * sr - cr * sy,
        sy * sp * sr + cr * cy,
        -cp * sr,
    )
    up = (
        -cr * cy * sp - sr * sy,
        -cr * sy * sp + sr * cy,
        cp * cr,
    )
    return forward, right, up


def write_camera_conditioning(request: PrevisRequest) -> Path:
    """Write OpenCV c2w arrays and preserve the original UE trajectory."""

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment failure
        raise RuntimeError("numpy is required for LingBot camera conditioning") from exc

    destination = request.output_dir / "conditioning"
    destination.mkdir(parents=True, exist_ok=True)
    poses: list[list[list[float]]] = []
    intrinsics: list[list[float]] = []
    for frame in request.camera_keyframes:
        forward, right, up = _rotation_basis(frame.rotation_deg)
        x, y, z = (value / 100.0 for value in frame.location_cm)
        # OpenCV camera c2w columns: right, down, forward, translation.
        pose = [
            [right[0], -up[0], forward[0], x],
            [right[1], -up[1], forward[1], y],
            [right[2], -up[2], forward[2], z],
            [0.0, 0.0, 0.0, 1.0],
        ]
        poses.append(pose)
        focal = 0.5 * request.width / math.tan(math.radians(frame.fov_degrees) / 2)
        intrinsics.append(
            [focal, focal, request.width / 2.0, request.height / 2.0]
        )
    np.save(destination / "poses.npy", np.asarray(poses, dtype=np.float32))
    np.save(destination / "intrinsics.npy", np.asarray(intrinsics, dtype=np.float32))
    (destination / "ue-camera-trajectory.json").write_text(
        json.dumps(
            {
                "trajectory_id": request.trajectory_id,
                "coordinate_system": "UE left-handed Z-up, centimeters",
                "authoritative": True,
                "keyframes": [asdict(frame) for frame in request.camera_keyframes],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def inspect_video(path: str | Path) -> dict[str, object]:
    video = Path(path)
    if not video.is_file() or video.stat().st_size <= 0:
        return {"ok": False, "error": "missing_or_empty"}
    try:
        import av

        with av.open(str(video)) as container:
            stream = next((item for item in container.streams if item.type == "video"), None)
            if stream is None:
                return {"ok": False, "error": "no_video_stream"}
            frame = next(container.decode(stream), None)
            fps = float(stream.average_rate) if stream.average_rate else 0.0
            frames = int(stream.frames or 0)
            return {
                "ok": frame is not None,
                "width": int(stream.width),
                "height": int(stream.height),
                "actual_frames": frames,
                "fps": round(fps, 3),
                "duration_seconds": round(frames / fps, 3) if frames and fps else 0,
                "bytes": video.stat().st_size,
            }
    except Exception as exc:
        return {"ok": False, "error": f"decode_failed:{exc}"}


def run_previs(
    request: PrevisRequest,
    *,
    router: Path = ROUTER,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PrevisResult:
    if not request.source_image.is_file():
        return PrevisResult(False, "failed", "", error="source_image_missing")
    if not router.is_file():
        return PrevisResult(False, "blocked", "", error="world_vision_router_missing")

    conditioning = write_camera_conditioning(request)
    command = [
        sys.executable,
        str(router),
        "generate",
        "--prompt",
        request.prompt,
        "--image",
        str(request.source_image),
        "--action-path",
        str(conditioning),
        "--frames",
        str(request.requested_frames),
        "--seed",
        str(request.seed),
    ]
    if request.force_backend == "lingbot":
        command.append("--force-local")
    elif request.force_backend == "reactor":
        command.append("--force-reactor")

    completed = runner(
        command,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    payload: dict[str, object] | None = None
    for line in reversed((completed.stdout or "").splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        return PrevisResult(
            False,
            "failed",
            "",
            conditioning_dir=str(conditioning),
            error=f"router_no_json:{(completed.stderr or '')[-300:]}",
        )

    backend = str(payload.get("backend") or "")
    path = str(payload.get("video_path") or "")
    metadata = inspect_video(path) if path else {"ok": False, "error": "no_video_path"}
    ok = completed.returncode == 0 and payload.get("ok") is True and metadata.get("ok") is True
    if not ok:
        blocked_errors = {"vram_insufficient", "no_backend", "ready_timeout"}
        error = str(payload.get("error") or metadata.get("error") or "previs_failed")
        return PrevisResult(
            False,
            "blocked" if error in blocked_errors else "failed",
            backend,
            metadata=metadata,
            license=dict(payload.get("license") or {}),
            conditioning_dir=str(conditioning),
            error=error,
        )
    return PrevisResult(
        True,
        "passed",
        backend,
        video_path=path,
        metadata=metadata,
        license=dict(payload.get("license") or {}),
        conditioning_dir=str(conditioning),
    )


__all__ = [
    "CameraKeyframe",
    "PrevisRequest",
    "PrevisResult",
    "inspect_video",
    "run_previs",
    "write_camera_conditioning",
]
