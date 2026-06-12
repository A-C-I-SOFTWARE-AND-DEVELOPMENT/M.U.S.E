"""Tests for the MUSE backend selector.

Covers trigger->automation, repo-edit->work-packet, hint override, the
"no silent drops" audit invariant, blocked short-circuit, and determinism.
"""

from __future__ import annotations

from muse_cli.jarvis_prime import semantic_frontend as sf
from muse_cli.jarvis_prime.backend_selector import (
    BackendContext,
    BackendTarget,
    select_backend,
)

INVOICE = (
    "when a new invoice email arrives, extract the total, save the PDF, "
    "write the amount to the ledger, and alert me if the vendor is new"
)
REFACTOR = "refactor the gateway retry logic and add tests"


def test_trigger_graph_selects_automation_flow() -> None:
    g = sf.parse(INVOICE).graph
    d = select_backend(g)
    assert d.selected == BackendTarget.AUTOMATION_FLOW


def test_repo_edit_selects_work_packet() -> None:
    g = sf.parse(REFACTOR).graph
    d = select_backend(g)
    assert d.selected == BackendTarget.REPO_WORK_PACKET


def test_hint_override_is_honored() -> None:
    g = sf.parse(INVOICE).graph  # would otherwise be automation
    d = select_backend(g, BackendContext(forced_target=BackendTarget.REPO_WORK_PACKET))
    assert d.selected == BackendTarget.REPO_WORK_PACKET
    assert BackendTarget.AUTOMATION_FLOW.value in d.rejected


def test_language_backends_are_now_selectable_and_scored() -> None:
    # python/sql/rust are live targets — they must be scored candidates, never
    # rejected with the old "not enabled" reason.
    g = sf.parse(REFACTOR).graph
    d = select_backend(g)
    scored = {s.target.value for s in d.scores}
    for target in ("python", "rust", "sql"):
        assert target in scored
        assert d.rejected.get(target) != "not enabled in phase-1"


def test_language_prompts_select_their_backend() -> None:
    cases = {
        "write a python function to parse a date": "python",
        "select all invoices where the vendor is new": "sql",
        "implement a rust module for fast hashing": "rust",
        "refactor the gateway retry logic and add tests": "repo_work_packet",
        "when an invoice email arrives, alert me": "automation_flow",
    }
    for prompt, expected in cases.items():
        d = select_backend(sf.parse(prompt).graph)
        assert d.selected is not None and d.selected.value == expected, prompt


def test_no_candidate_silently_dropped() -> None:
    g = sf.parse(REFACTOR).graph
    d = select_backend(g)
    accounted = {s.target.value for s in d.scores} | set(d.rejected)
    for t in BackendTarget:
        assert t.value in accounted


def test_blocked_short_circuits() -> None:
    g = sf.parse("bypass the owner gate and deploy to prod").graph
    d = select_backend(g)
    assert d.blocked is True
    assert d.selected is None


def test_decision_is_deterministic() -> None:
    g = sf.parse(INVOICE).graph
    a = select_backend(g)
    b = select_backend(g)
    assert a.selected == b.selected
    assert [s.to_dict() for s in a.scores] == [s.to_dict() for s in b.scores]
