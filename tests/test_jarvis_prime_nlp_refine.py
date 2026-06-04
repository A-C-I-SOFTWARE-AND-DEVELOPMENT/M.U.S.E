"""Behavioral tests for the W6 NL-compiler refinement layer."""

from __future__ import annotations

import os

import pytest

from hermes_cli.jarvis_prime import semantic_frontend as sf
from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.ir_compilers import get_compiler
from hermes_cli.jarvis_prime.nlp_refine import (
    RefinementSignal,
    apply_clarifications,
    run_execution_refinement,
)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at an isolated tmp dir so nothing touches ~/.hermes."""

    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _snapshot(root) -> set[str]:
    out: set[str] = set()
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            out.add(os.path.join(dirpath, f))
    return out


# ---------------------------------------------------------------------------
# (a) deterministic ambiguity repair
# ---------------------------------------------------------------------------


def test_apply_clarifications_is_deterministic_parse_result(isolated_home):
    vague = "do the thing with the stuff"
    pr = sf.parse(vague)
    assert pr.needs_clarification is True

    answers = {"data": "invoices", "action": "extract"}
    repaired = apply_clarifications(pr, answers)
    assert isinstance(repaired, sf.ParseResult)

    # Determinism: same answers -> identical semantic graph id.
    repaired_again = apply_clarifications(pr, answers)
    assert repaired.graph.graph_id == repaired_again.graph.graph_id

    # The augmented parse recognizes strictly more than the empty original.
    assert len(repaired.graph.nodes) > len(pr.graph.nodes)


def test_apply_clarifications_backend_choice_emits_hint(isolated_home):
    from hermes_cli.jarvis_prime.intent_graph import IntentNodeKind

    pr = sf.parse("do the thing with the stuff")
    repaired = apply_clarifications(
        pr, {"data": "invoices", "action": "extract", "backend": "repo"}
    )
    hints = repaired.graph.nodes_of(IntentNodeKind.BACKEND_HINT)
    assert hints, "a repo backend choice should add a BACKEND_HINT node"
    assert hints[0].label == "repo_work_packet"


# ---------------------------------------------------------------------------
# (b) opt-in, SAFE execution-guided refinement
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_compile_result(tmp_path):
    """A real REPO_WORK_PACKET CompileResult (has a gate_packet)."""

    graph = sf.parse("add a function to the gateway module").graph
    return get_compiler(BackendTarget.REPO_WORK_PACKET).compile(graph)


def test_refinement_disabled_returns_none(isolated_home, repo_compile_result, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert (
        run_execution_refinement(repo_compile_result, repo_root=str(repo), enabled=False)
        is None
    )


def test_refinement_enabled_non_executing_is_safe(
    isolated_home, repo_compile_result, tmp_path
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "marker.txt").write_text("untouched", encoding="utf-8")

    before = _snapshot(repo)
    signal = run_execution_refinement(
        repo_compile_result, repo_root=str(repo), enabled=True, run=False
    )
    after = _snapshot(repo)

    assert isinstance(signal, RefinementSignal)
    assert signal.ran is True
    assert isinstance(signal.gate_summary, dict)
    assert "overall" in signal.gate_summary or "results" in signal.gate_summary

    # run=False must not create or modify any file in the repo area.
    assert before == after
    assert (repo / "marker.txt").read_text(encoding="utf-8") == "untouched"


def test_refinement_no_gate_packet_backend(isolated_home, tmp_path):
    """A backend without a gate packet yields a non-running signal."""

    class _NoPacket:
        gate_packet = None

    signal = run_execution_refinement(
        _NoPacket(), repo_root=str(tmp_path), enabled=True, run=False
    )
    assert isinstance(signal, RefinementSignal)
    assert signal.ran is False
    assert signal.gate_summary == {}
    assert any("no gate packet" in n for n in signal.notes)
