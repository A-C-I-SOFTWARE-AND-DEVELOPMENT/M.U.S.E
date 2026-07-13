"""Tests for natural-language coding task routing."""

from __future__ import annotations

from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    build_work_packet,
    classify_coding_request,
)


def test_avatar_overlay_request_routes_high_risk_and_owner_gated() -> None:
    route = classify_coding_request("make the avatar float on screen and tap Facebook")
    assert route.intent is CodingIntent.AVATAR_PRESENCE
    assert route.risk_class == "RC3"
    assert route.requires_owner_approval is True


def test_work_packet_contains_builder_reviewer_and_safety_notes() -> None:
    packet = build_work_packet("fix the memory bug in Jarvis")
    assert packet.primary_worker == "claude-code-windows"
    assert packet.reviewer_worker == "codex"
    assert packet.branch.startswith("jarvis/")
    assert any("localization" in note.lower() for note in packet.notes)
    assert ".env" in packet.forbidden_files


def test_research_request_is_read_only_docs_lane() -> None:
    packet = build_work_packet("deep search oss coding agents")
    assert packet.intent is CodingIntent.RESEARCH
    assert packet.risk_class == "RC1"
    assert packet.allowed_files == ("docs/jarvis_research/**",)
