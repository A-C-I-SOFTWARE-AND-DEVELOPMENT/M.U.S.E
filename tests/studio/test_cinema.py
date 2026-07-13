from __future__ import annotations

from pathlib import Path

from agent.studio.cinema import CinemaPackager
from agent.studio.render_manifest import RenderFrameRecord, RenderManifest
from agent.studio.stereo import StereoFrameMetrics, StereoQcLimits, StereoShot, evaluate_stereo_qc


def _frame(tmp_path: Path, eye: str, output_hash: str) -> RenderFrameRecord:
    output = tmp_path / f"0001_{eye}.exr"
    output.write_bytes((eye + "-exr").encode())
    return RenderFrameRecord(
        shot_id="shot_1",
        frame=1,
        eye=eye,
        scene_revision="rev_1",
        seed=42,
        renderer="Unreal MRQ",
        renderer_version="5.6",
        settings_hash="sha256:settings",
        input_asset_hashes=("sha256:asset",),
        output_hash=output_hash,
        attempt=1,
        worker="render_1",
        started_at="2026-07-12T00:00:00Z",
        completed_at="2026-07-12T00:00:01Z",
        status="completed",
        output_path=str(output),
        timecode_seconds=1.0,
    )


def test_render_manifest_requires_two_synchronized_eyes(tmp_path: Path) -> None:
    manifest = RenderManifest.from_records([_frame(tmp_path, "left", "sha256:left")])
    assert "missing_eye" in manifest.validate().failures


def test_retry_preserves_determinism_and_increments_attempt(tmp_path: Path) -> None:
    frame = _frame(tmp_path, "left", "sha256:left")
    retry = frame.retry(worker="render_2")
    assert retry.seed == frame.seed
    assert retry.settings_hash == frame.settings_hash
    assert retry.attempt == 2
    assert retry.status == "queued"


def test_cinema_package_contains_aces_stereo_qc_and_external_imax_gate(tmp_path: Path) -> None:
    renders = RenderManifest.from_records([
        _frame(tmp_path, "left", "sha256:left"),
        _frame(tmp_path, "right", "sha256:right"),
    ])
    qc = evaluate_stereo_qc(StereoFrameMetrics(), StereoQcLimits())
    package = CinemaPackager(tmp_path / "packages").create(
        StereoShot(shot_id="shot_1", scene_id="scene_1"),
        renders,
        qc,
        audio_manifest={"format": "spatial_mix"},
        editorial_manifest={"timebase": 24},
        rights_manifest={"status": "passed"},
    )
    assert package.passed is True
    assert package.imax_certified is False
    assert package.external_certification == "required"
    assert (package.root / "aces.json").is_file()
    assert (package.root / "checksums.sha256").is_file()
