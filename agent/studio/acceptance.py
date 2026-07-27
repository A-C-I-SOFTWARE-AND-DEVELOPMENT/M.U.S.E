"""Render-comparison and performance acceptance reports."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RenderComparisonFrame:
    frame_id: str
    scene: str
    reference_path: str
    candidate_path: str
    ssim_score: float | None
    psnr_db: float | None
    perceptual_delta: str
    previs_source: bool


@dataclass(frozen=True)
class PerformanceSample:
    sample_id: str
    zone_id: str
    frame_ms: float
    draw_calls: int
    gpu_memory_mb: float
    cpu_ms: float
    streaming_loads: int
    actor_count: int


@dataclass(frozen=True)
class AcceptanceReport:
    project_id: str
    profile: str
    render_comparisons: tuple[RenderComparisonFrame, ...]
    performance_samples: tuple[PerformanceSample, ...]
    quality_gate_passed: bool
    performance_gate_passed: bool
    license_gate_passed: bool
    evidence_complete: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    benchmark_claim: str
    version: str = "1.0"

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> AcceptanceReport:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            project_id=data["project_id"],
            profile=data["profile"],
            render_comparisons=tuple(
                RenderComparisonFrame(**f) for f in data.get("render_comparisons", [])
            ),
            performance_samples=tuple(
                PerformanceSample(**s) for s in data.get("performance_samples", [])
            ),
            quality_gate_passed=data.get("quality_gate_passed", False),
            performance_gate_passed=data.get("performance_gate_passed", False),
            license_gate_passed=data.get("license_gate_passed", True),
            evidence_complete=data.get("evidence_complete", False),
            failures=tuple(data.get("failures", [])),
            warnings=tuple(data.get("warnings", [])),
            benchmark_claim=data.get("benchmark_claim", ""),
        )

    @property
    def passed(self) -> bool:
        return (
            self.quality_gate_passed
            and self.performance_gate_passed
            and self.license_gate_passed
            and self.evidence_complete
            and not self.failures
        )


def evaluate_acceptance(
    project_id: str,
    profile_name: str,
    *,
    performance_metrics: Mapping[str, Any] | None = None,
    render_evidence_paths: Sequence[str] | None = None,
    license_failures: Sequence[str] | None = None,
    offline: bool = False,
) -> AcceptanceReport:
    from agent.studio.quality_profiles import load_quality_profile

    profile = load_quality_profile(profile_name)
    metrics = dict(performance_metrics or {})
    failures: list[str] = []
    warnings: list[str] = []

    quality_passed, quality_failures = profile.validate_metrics(metrics)
    failures.extend(quality_failures)

    perf_passed = True
    if profile.requires_ue_render_evidence:
        if not render_evidence_paths:
            failures.append("missing_ue_render_evidence")
            perf_passed = False
        if offline:
            warnings.append("offline_mode: render evidence not produced")
            perf_passed = False
    elif not metrics:
        perf_passed = True
    else:
        perf_passed = quality_passed

    license_passed = not license_failures
    if license_failures:
        failures.extend(license_failures)

    evidence_complete = bool(render_evidence_paths) or not profile.requires_ue_render_evidence
    if offline and profile.requires_ue_render_evidence:
        evidence_complete = False

    render_comparisons: list[RenderComparisonFrame] = []
    for i, path in enumerate(render_evidence_paths or ()):
        render_comparisons.append(
            RenderComparisonFrame(
                frame_id=f"frame_{i:04d}",
                scene="benchmark_biome",
                reference_path="",
                candidate_path=path,
                ssim_score=None,
                psnr_db=None,
                perceptual_delta="not_measured" if offline else "pending",
                previs_source="lingbot" in path.lower() or "reactor" in path.lower(),
            )
        )

    perf_samples: list[PerformanceSample] = []
    if metrics:
        perf_samples.append(
            PerformanceSample(
                sample_id="sample_000",
                zone_id=metrics.get("zone_id", "zone_00"),
                frame_ms=float(metrics.get("frame_ms", 0)),
                draw_calls=int(metrics.get("draw_calls", 0)),
                gpu_memory_mb=float(metrics.get("gpu_memory_mb", 0)),
                cpu_ms=float(metrics.get("cpu_ms", 0)),
                streaming_loads=int(metrics.get("streaming_loads", 0)),
                actor_count=int(metrics.get("actor_count", 0)),
            )
        )

    benchmark_claim = ""
    if profile.benchmark_reference:
        benchmark_claim = (
            f"Quality benchmark reference: {profile.benchmark_reference}. "
            "No equivalent visuals claimed without measured UE render evidence."
        )

    return AcceptanceReport(
        project_id=project_id,
        profile=profile_name,
        render_comparisons=tuple(render_comparisons),
        performance_samples=tuple(perf_samples),
        quality_gate_passed=quality_passed,
        performance_gate_passed=perf_passed,
        license_gate_passed=license_passed,
        evidence_complete=evidence_complete,
        failures=tuple(dict.fromkeys(failures)),
        warnings=tuple(dict.fromkeys(warnings)),
        benchmark_claim=benchmark_claim,
    )


__all__ = [
    "AcceptanceReport",
    "PerformanceSample",
    "RenderComparisonFrame",
    "evaluate_acceptance",
]
