from __future__ import annotations

from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    build_work_packet,
    classify_intent,
)


def test_avatar_request_becomes_owner_gated_avatar_packet() -> None:
    packet = build_work_packet("make the mini avatar living and floating on screen")

    assert packet.intent is CodingIntent.AVATAR_PRESENCE
    assert packet.owner_gated_actions == ("owner_approval",)
    assert packet.primary_worker != packet.reviewer_worker
    assert "hermes_cli/jarvis_prime/companion_presence.py" in packet.allowed_files


def test_facebook_click_is_device_action() -> None:
    packet = build_work_packet("click on Facebook when I ask")

    assert packet.intent is CodingIntent.DEVICE_ACTION
    assert packet.risk_class == "RC3"
    assert packet.owner_gated_actions == ("owner_approval",)


def test_research_request_is_read_only_research() -> None:
    assert classify_intent("audit and deep search Hermes") is CodingIntent.RESEARCH
    packet = build_work_packet("audit and deep search Hermes")
    assert packet.allowed_files == ("docs/jarvis_research/**",)
    assert packet.owner_gated_actions == ()


def test_generic_implementation_packet_has_branch_and_verification() -> None:
    packet = build_work_packet("add memory tree support")

    assert packet.intent is CodingIntent.IMPLEMENT
    assert packet.branch.startswith("jarvis/")
    assert packet.verification_plan
