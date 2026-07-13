"""Metric native-stereo camera models and deterministic QC decisions."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping


def _element_policies() -> dict[str, str]:
    return {
        "transparency": "per_eye_native",
        "particles": "depth_sorted_per_eye",
        "volumetrics": "per_eye_native",
        "reflections": "stereo_correct",
        "refraction": "stereo_correct",
        "depth_of_field": "convergence_reviewed",
        "motion_blur": "temporally_synchronized",
        "lens_effects": "per_eye_reviewed",
        "ui": "zero_parallax_plane",
    }


def _positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or (number < 0 if allow_zero else number <= 0):
        raise ValueError(f"{name} must be {'non-negative' if allow_zero else 'positive'} and finite")
    return number


@dataclass(frozen=True)
class StereoCamera:
    eye: str
    position_m: tuple[float, float, float]
    yaw_degrees: float
    focal_length_mm: float
    sensor_width_mm: float
    near_clip_m: float
    far_clip_m: float


@dataclass(frozen=True)
class StereoCameraRig:
    interaxial_m: float
    convergence_m: float
    zero_parallax_m: float
    focal_length_mm: float
    sensor_width_mm: float
    near_clip_m: float
    far_clip_m: float
    display_width_m: float
    viewing_distance_m: float

    def __post_init__(self) -> None:
        for name in (
            "interaxial_m", "convergence_m", "zero_parallax_m", "focal_length_mm",
            "sensor_width_mm", "near_clip_m", "far_clip_m", "display_width_m",
            "viewing_distance_m",
        ):
            _positive(getattr(self, name), name)
        if self.near_clip_m >= self.far_clip_m:
            raise ValueError("near clip must be closer than far clip")

    def cameras(self) -> tuple[StereoCamera, StereoCamera]:
        half = self.interaxial_m / 2.0
        toe_in = math.degrees(math.atan2(half, self.convergence_m))
        left = StereoCamera(
            "left", (-half, 0.0, 0.0), toe_in, self.focal_length_mm,
            self.sensor_width_mm, self.near_clip_m, self.far_clip_m,
        )
        right = StereoCamera(
            "right", (half, 0.0, 0.0), -toe_in, self.focal_length_mm,
            self.sensor_width_mm, self.near_clip_m, self.far_clip_m,
        )
        return left, right


@dataclass(frozen=True)
class StereoShot:
    shot_id: str = ""
    scene_id: str = ""
    left_camera_id: str = "left"
    right_camera_id: str = "right"
    master_method: str = "native_stereo"
    physical_camera_count: int = 2
    interaxial_m: float = 0.065
    convergence_m: float = 12.0
    zero_parallax_m: float = 12.0
    focal_distance_m: float = 12.0
    aperture_f: float = 4.0
    focal_length_mm: float = 50.0
    sensor_width_mm: float = 36.0
    near_clip_m: float = 0.1
    far_clip_m: float = 5000.0
    display_width_m: float = 22.0
    viewing_distance_m: float = 18.0
    depth_budget_percent: float = 2.0
    safe_composition_190: bool = True
    safe_composition_143: bool = True
    element_policies: Mapping[str, str] = field(default_factory=_element_policies)
    transition_policy: str = "depth_continuity_reviewed"

    def __post_init__(self) -> None:
        if self.master_method != "native_stereo" or self.physical_camera_count != 2:
            raise ValueError("native master requires two physical cameras")
        if self.left_camera_id == self.right_camera_id:
            raise ValueError("left and right cameras must be distinct")
        _positive(self.depth_budget_percent, "depth_budget_percent")


@dataclass(frozen=True)
class StereoFrameMetrics:
    horizontal_disparity_percent: float = 0.0
    vertical_error_px: float = 0.0
    occlusion_conflicts: int = 0
    crosstalk_risk: float = 0.0
    floating_window: bool = False
    temporal_offset_ms: float = 0.0
    comfort_score: float = 1.0
    safe_composition_190: bool = True
    safe_composition_143: bool = True


@dataclass(frozen=True)
class StereoQcLimits:
    max_horizontal_disparity_percent: float = 2.0
    max_vertical_px: float = 0.5
    max_occlusion_conflicts: int = 0
    max_crosstalk_risk: float = 0.2
    max_temporal_offset_ms: float = 0.5
    min_comfort_score: float = 0.8
    require_safe_190: bool = True
    require_safe_143: bool = True


@dataclass(frozen=True)
class StereoQcIssue:
    code: str
    message: str
    measured: float | int | bool
    limit: float | int | bool


@dataclass(frozen=True)
class StereoQcResult:
    passed: bool
    issues: tuple[StereoQcIssue, ...]


def _read(value: object, name: str, default: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def evaluate_stereo_qc(
    frame: StereoFrameMetrics | Mapping[str, object],
    limits: StereoQcLimits | Mapping[str, object],
) -> StereoQcResult:
    """Fail a master when any comfort, sync, or composition gate is exceeded."""

    issues: list[StereoQcIssue] = []

    def maximum(metric: str, limit: str, code: str, message: str) -> None:
        raw = _read(frame, metric, 0.0)
        allowed = _read(limits, limit, 0.0)
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
        ):
            issues.append(StereoQcIssue("invalid_metric", f"{metric} is not finite", False, True))
            return
        measured = abs(raw)
        if measured > allowed:
            issues.append(StereoQcIssue(code, message, measured, allowed))

    maximum(
        "horizontal_disparity_percent", "max_horizontal_disparity_percent",
        "depth_budget", "horizontal disparity exceeds the approved depth budget",
    )
    maximum(
        "vertical_error_px", "max_vertical_px", "vertical_misalignment",
        "vertical alignment exceeds the pixel tolerance",
    )
    maximum(
        "occlusion_conflicts", "max_occlusion_conflicts", "occlusion_conflict",
        "stereo occlusion conflicts require shot repair",
    )
    maximum(
        "crosstalk_risk", "max_crosstalk_risk", "crosstalk_risk",
        "predicted display crosstalk is above tolerance",
    )
    maximum(
        "temporal_offset_ms", "max_temporal_offset_ms", "temporal_sync",
        "left and right eyes are not temporally synchronized",
    )
    comfort = _read(frame, "comfort_score", 0.0)
    comfort_limit = _read(limits, "min_comfort_score", 1.0)
    if (
        isinstance(comfort, bool)
        or not isinstance(comfort, (int, float))
        or not math.isfinite(float(comfort))
    ):
        issues.append(StereoQcIssue("invalid_metric", "comfort score is not finite", False, True))
    elif comfort < comfort_limit:
        issues.append(
            StereoQcIssue("comfort", "stereo comfort score is below the minimum", comfort, comfort_limit)
        )
    if bool(_read(frame, "floating_window", False)):
        issues.append(StereoQcIssue("floating_window", "floating-window violation", True, False))
    for suffix in ("190", "143"):
        required = bool(_read(limits, f"require_safe_{suffix}", True))
        safe = bool(_read(frame, f"safe_composition_{suffix}", False))
        if required and not safe:
            issues.append(
                StereoQcIssue(
                    f"composition_{suffix}",
                    f"composition is unsafe for the {suffix[0]}.{suffix[1:]} extraction",
                    safe,
                    required,
                )
            )
    return StereoQcResult(not issues, tuple(issues))


__all__ = [
    "StereoCamera",
    "StereoCameraRig",
    "StereoFrameMetrics",
    "StereoQcIssue",
    "StereoQcLimits",
    "StereoQcResult",
    "StereoShot",
    "evaluate_stereo_qc",
]
