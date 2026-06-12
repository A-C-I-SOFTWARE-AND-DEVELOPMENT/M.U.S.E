"""CLI wiring for the audit-lane modules: presence, packet, memory-tree.

These three clean-room modules (``companion_presence``, ``memory_tree``,
``natural_language_coder``) ship as policy/state layers; this exercises the
``python -m muse_cli.jarvis_prime`` subcommands that surface them, plus the
package-level exports that make them first-class API. Invocation is in-process
through ``main()`` so the argparse + handler path runs without a subprocess.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from typing import Any

from muse_cli.jarvis_prime.__main__ import main as cli_main


def _run(argv: list[str]) -> tuple[int, Any]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else {})


# ---------------------------------------------------------------------------
# packet — natural_language_coder
# ---------------------------------------------------------------------------


def test_packet_device_action_is_owner_gated() -> None:
    code, body = _run(["packet", "open Facebook and tap the latest post", "--json"])
    assert code == 0
    assert body["intent"] == "device_action"
    assert body["risk_class"] == "RC3"
    assert "owner_approval" in body["owner_gated_actions"]
    # builder and reviewer must be different workers
    assert body["primary_worker"] != body["reviewer_worker"]


def test_packet_plain_implement_is_low_risk_and_ungated() -> None:
    code, body = _run(["packet", "add a helper to format dates", "--json"])
    assert code == 0
    assert body["intent"] == "implement"
    assert body["risk_class"] == "RC1"
    assert body["owner_gated_actions"] == []


def test_packet_branch_prefix_is_honored() -> None:
    code, body = _run([
        "packet",
        "write the onboarding guide",
        "--branch-prefix",
        "docs",
        "--json",
    ])
    assert code == 0
    assert body["intent"] == "document"
    assert body["branch"].startswith("docs/")


def test_packet_text_output_is_human_readable() -> None:
    # The default (non-JSON) path prints plain text, not JSON.
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(["packet", "review the gateway module"])
    out = buf.getvalue()
    assert code == 0
    assert "intent: review" in out
    assert "branch: jarvis/" in out


# ---------------------------------------------------------------------------
# presence — companion_presence
# ---------------------------------------------------------------------------


def test_presence_real_device_action_requires_owner_gate() -> None:
    code, body = _run([
        "presence",
        "--mission",
        "open Facebook",
        "--target-app",
        "Facebook",
        "--real-action",
        "--json",
    ])
    assert code == 0
    assert body["plan"]["owner_gate_required"] is True
    assert body["plan"]["risk"] == "accessibility_gesture"
    assert any(step["requires_real_action"] for step in body["plan"]["steps"])


def test_presence_animation_only_plan_is_not_gated() -> None:
    code, body = _run(["presence", "--mission", "summarize my inbox", "--json"])
    assert code == 0
    assert body["plan"]["owner_gate_required"] is False
    assert body["plan"]["risk"] == "animation_only"


def test_presence_emergency_stop_overrides_everything() -> None:
    code, body = _run(["presence", "--emergency-stop", "--working", "--json"])
    assert code == 0
    assert body["state"] == "emergency_stop"


def test_presence_attention_needs_opt_in_and_threshold() -> None:
    # High confidence but no opt-in → not watching.
    code, body = _run(["presence", "--attention-confidence", "0.99", "--json"])
    assert code == 0
    assert body["state"] == "idle"

    # Opt-in plus confidence over threshold → watching.
    code, body = _run([
        "presence",
        "--attention-opt-in",
        "--attention-confidence",
        "0.99",
        "--json",
    ])
    assert code == 0
    assert body["state"] == "watching"


# ---------------------------------------------------------------------------
# memory-tree — memory_tree
# ---------------------------------------------------------------------------


def test_memory_tree_search_matches_on_topic() -> None:
    code, body = _run([
        "memory-tree",
        "--add",
        "ops::Deploy::ship the cockpit on friday",
        "--add",
        "ops::Avatar::living avatar presence policy",
        "--search",
        "avatar",
        "--json",
    ])
    assert code == 0
    assert len(body) == 1
    assert body[0]["title"] == "Avatar"
    assert body[0]["namespace"] == "ops"


def test_memory_tree_outline_groups_by_namespace() -> None:
    code, body = _run([
        "memory-tree",
        "--add",
        "work::A::first note here",
        "--add",
        "home::B::second note here",
        "--json",
    ])
    assert code == 0
    assert {chunk["namespace"] for chunk in body} == {"work", "home"}


def test_memory_tree_rejects_malformed_add() -> None:
    code, body = _run(["memory-tree", "--add", "missing-separators"])
    assert code == 2
    assert body == {}


# ---------------------------------------------------------------------------
# package exports — the three modules are first-class API
# ---------------------------------------------------------------------------


def test_audit_lane_types_are_exported_from_package() -> None:
    import muse_cli.jarvis_prime as jp

    for name in (
        "CompanionPresencePolicy",
        "PresenceSignals",
        "PresenceState",
        "MemoryTree",
        "MemoryChunk",
        "build_work_packet",
        "CodingIntent",
        "CodingWorkPacket",
    ):
        assert name in jp.__all__, f"{name} missing from __all__"
        assert hasattr(jp, name), f"{name} not importable from package"
