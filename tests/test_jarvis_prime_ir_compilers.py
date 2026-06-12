"""Tests for the MUSE IR backend compilers.

Covers: the repo backend reuses build_work_packet and emits a gate-compatible
packet; the automation backend builds a validatable AutomationFlow; flow
validation flags a missing trigger and an ungated external alert; round-trips.
"""

from __future__ import annotations

from muse_cli.jarvis_prime import semantic_frontend as sf
from muse_cli.jarvis_prime.backend_selector import BackendTarget
from muse_cli.jarvis_prime.gates import GateOutcome, run_gate_summary
from muse_cli.jarvis_prime.ir_compilers import get_compiler
from muse_cli.jarvis_prime.ir_compilers.automation_flow import (
    AutomationFlow,
    FlowOutput,
    FlowStep,
    FlowTrigger,
)
from muse_cli.jarvis_prime.natural_language_coder import (
    CodingWorkPacket,
    build_work_packet,
)

INVOICE = (
    "when a new invoice email arrives, extract the total, save the PDF, "
    "write the amount to the ledger, and alert me if the vendor is new"
)
REFACTOR = "refactor the gateway retry logic and add tests"


# --- repo work-packet backend ---------------------------------------------


def test_repo_compiler_reuses_build_work_packet() -> None:
    g = sf.parse(REFACTOR).graph
    result = get_compiler(BackendTarget.REPO_WORK_PACKET).compile(g)
    baseline = build_work_packet(REFACTOR)
    packet = result.artifact
    assert isinstance(packet, CodingWorkPacket)
    # Same spine: identical mission, intent, risk as the established path.
    assert packet.mission == baseline.mission
    assert packet.intent == baseline.intent
    assert packet.risk_class == baseline.risk_class


def test_repo_compiler_emits_gate_compatible_packet() -> None:
    g = sf.parse(REFACTOR).graph
    result = get_compiler(BackendTarget.REPO_WORK_PACKET).compile(g)
    assert result.gate_packet is not None
    summary = run_gate_summary(result.gate_packet)
    planning = next(r for r in summary.results if r.name == "planning")
    assert planning.outcome == GateOutcome.PASS


def test_repo_compiler_never_narrows_allowed_files() -> None:
    g = sf.parse("refactor gateway/retry.py and add tests").graph
    result = get_compiler(BackendTarget.REPO_WORK_PACKET).compile(g)
    from muse_cli.jarvis_prime.natural_language_coder import _allowed_files_for
    packet = result.artifact
    assert isinstance(packet, CodingWorkPacket)
    default = set(_allowed_files_for(g.intent))
    assert default <= set(packet.allowed_files)


# --- automation-flow backend ----------------------------------------------


def test_automation_compiler_builds_valid_flow() -> None:
    g = sf.parse(INVOICE).graph
    result = get_compiler(BackendTarget.AUTOMATION_FLOW).compile(g)
    flow = result.artifact
    assert isinstance(flow, AutomationFlow)
    assert flow.triggers and flow.steps
    # "email"/"alert" implies the external-message owner gate upstream.
    assert flow.owner_gated_actions
    assert flow.validate().ok


def test_flow_validation_flags_missing_trigger() -> None:
    flow = AutomationFlow(steps=(FlowStep(id="s1", op="write"),))
    result = flow.validate()
    assert not result.ok
    assert any(f.field == "triggers" for f in result.errors)


def test_flow_validation_flags_ungated_external_alert() -> None:
    flow = AutomationFlow(
        triggers=(FlowTrigger(kind="event", event="x"),),
        steps=(FlowStep(id="s1", op="alert"),),
        outputs=(FlowOutput(kind="alert"),),
        owner_gated_actions=(),  # no gate -> error
    )
    result = flow.validate()
    assert not result.ok
    assert any(f.field == "outputs" for f in result.errors)


def test_flow_round_trip() -> None:
    g = sf.parse(INVOICE).graph
    flow = get_compiler(BackendTarget.AUTOMATION_FLOW).compile(g).artifact
    assert isinstance(flow, AutomationFlow)
    restored = AutomationFlow.from_dict(flow.to_dict())
    assert restored.flow_id == flow.flow_id


def test_compile_result_to_dict_round_trips() -> None:
    g = sf.parse(INVOICE).graph
    result = get_compiler(BackendTarget.AUTOMATION_FLOW).compile(g)
    d = result.to_dict()
    assert d["target"] == BackendTarget.AUTOMATION_FLOW.value
    assert "artifact" in d
