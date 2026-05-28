"""Tests for the avatar image-conversion request builder."""

from __future__ import annotations

from tools.avatar_conversion import (
    AvatarConversionStyle,
    AvatarRenderKind,
    build_conversion_request,
)


def test_navy_gold_rive_request():
    req = build_conversion_request(AvatarConversionStyle.NAVY_GOLD, AvatarRenderKind.RIVE)
    assert "navy" in req.prompt.lower()
    assert "rigging" in req.prompt.lower()  # rive render directive
    assert req.aspect_ratio == "1:1"
    assert req.transparent_background is True
    assert req.needs_image_to_3d is False


def test_character_3d_flags_image_to_3d_and_opaque_bg():
    req = build_conversion_request(
        AvatarConversionStyle.REALISTIC, AvatarRenderKind.CHARACTER_3D
    )
    assert req.needs_image_to_3d is True
    # 3D reconstruction wants an opaque, evenly-lit subject, not cutout.
    assert req.transparent_background is False
    assert "t-pose" in req.prompt.lower()


def test_image_tool_kwargs_shape():
    req = build_conversion_request(
        AvatarConversionStyle.CYAN_GLOW, AvatarRenderKind.ANIMATED_PIXEL
    )
    kwargs = req.as_image_tool_kwargs()
    assert set(kwargs) == {"prompt", "aspect_ratio", "transparent_background"}
    assert kwargs["transparent_background"] is True


def test_subject_hint_is_woven_in():
    req = build_conversion_request(
        AvatarConversionStyle.NAVY_GOLD,
        AvatarRenderKind.RIVE,
        subject_hint="a smiling man with glasses",
    )
    assert "smiling man with glasses" in req.prompt


def test_every_style_and_render_combo_builds():
    for style in AvatarConversionStyle:
        for kind in AvatarRenderKind:
            req = build_conversion_request(style, kind)
            assert req.prompt
            assert req.source_note == f"{style.value}/{kind.value}"
