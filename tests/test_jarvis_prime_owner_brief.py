from __future__ import annotations

from muse_cli.jarvis_prime.monitors import MonitorBoard
from muse_cli.jarvis_prime.owner_brief import build_owner_brief


def _results():
    board = MonitorBoard.default()
    context = {
        "repo": {"dirty": True, "branch": "feature", "changed_files": ["a.py"]},
        "open_prs": [{"number": 1, "stale": True}],
        "tests": {"passed": 5, "failed": ["test_broken"]},
        "open_contradictions": ["deploy-day"],
        "pending_proposals": [{"kind": "skill_update"}],
        # docs, model_failures, android omitted → blind spots
    }
    return board, board.run(context)


def test_brief_surfaces_matters_and_approvals() -> None:
    board, results = _results()
    brief = build_owner_brief(
        results,
        board=board,
        learned=["routing missed a lane"],
        changed=["edited router.py"],
        blocked=["deploy gated on owner"],
    )
    assert any("failing_tests" in m for m in brief.what_matters)
    assert brief.needs_approval  # contradictions + proposals need approval
    assert brief.blocked == ["deploy gated on owner"]
    assert brief.learned == ["routing missed a lane"]


def test_brief_attests_coverage_and_blind_spots() -> None:
    board, results = _results()
    brief = build_owner_brief(results, board=board)
    assert brief.coverage["total"] == 9
    assert brief.coverage["blind_spots"]
    text = brief.render()
    assert "Monitor coverage attestation" in text
    assert "BLIND SPOTS" in text


def test_brief_to_dict_has_all_sections() -> None:
    board, results = _results()
    d = build_owner_brief(results, board=board).to_dict()
    for key in (
        "what_changed",
        "what_matters",
        "needs_approval",
        "blocked",
        "learned",
        "coverage",
    ):
        assert key in d
