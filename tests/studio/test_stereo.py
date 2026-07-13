from __future__ import annotations

import pytest

from agent.studio.stereo import (
    StereoCameraRig,
    StereoFrameMetrics,
    StereoQcLimits,
    StereoShot,
    evaluate_stereo_qc,
)


def test_stereo_rig_builds_two_metric_cameras() -> None:
    rig = StereoCameraRig(
        interaxial_m=0.065,
        convergence_m=12.0,
        zero_parallax_m=12.0,
        focal_length_mm=50.0,
        sensor_width_mm=36.0,
        near_clip_m=0.1,
        far_clip_m=5000.0,
        display_width_m=22.0,
        viewing_distance_m=18.0,
    )
    left, right = rig.cameras()
    assert left.position_m[0] == pytest.approx(-0.0325)
    assert right.position_m[0] == pytest.approx(0.0325)
    assert left is not right


def test_vertical_misalignment_blocks_master() -> None:
    qc = evaluate_stereo_qc(
        StereoFrameMetrics(vertical_error_px=1.2),
        StereoQcLimits(max_vertical_px=0.5),
    )
    assert qc.passed is False
    assert any(issue.code == "vertical_misalignment" for issue in qc.issues)


def test_flat_card_conversion_cannot_be_native_master() -> None:
    with pytest.raises(ValueError, match="two physical cameras"):
        StereoShot(master_method="depth_post_conversion")


def test_unsafe_extraction_and_floating_window_block_master() -> None:
    qc = evaluate_stereo_qc(
        StereoFrameMetrics(floating_window=True, safe_composition_143=False),
        StereoQcLimits(),
    )
    assert {issue.code for issue in qc.issues} >= {"floating_window", "composition_143"}
