"""Tests for the Phase-4 ratchet adoption harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from hermes_cli.jarvis_prime.bench.ratchet_run import (  # noqa: E402
    run_ratchet,
    score_configuration,
)
from hermes_cli.jarvis_prime.research_fabric.benchmarks import load_suite  # noqa: E402
from hermes_cli.jarvis_prime.research_fabric.store import SnapshotStore  # noqa: E402

GIT_SHA = "deadbeefcafe0001"


def _suite(tmp_path: Path) -> Path:
    """A tiny all-domain suite. The good solution is trivial per task."""

    specs = []
    for domain in (
        "code_generation",
        "code_editing",
        "code_review",
        "software_development",
        "reasoning",
        "safety",
    ):
        for i in range(2):
            specs.append(
                {
                    "task_id": f"rt-{domain}-{i}",
                    "domain": domain,
                    "kind": "algorithm",
                    "payload": {
                        "entrypoint": "solve",
                        "prompt": f"[{domain}] return the constant {i}",
                        "public_cases": [{"args": [], "expected": i}],
                        "holdout_cases": [{"args": [], "expected": i}],
                    },
                }
            )
    path = tmp_path / "suite.jsonl"
    path.write_text("\n".join(json.dumps(s) for s in specs) + "\n", encoding="utf-8")
    return path


def _heldout(tmp_path: Path) -> Path:
    held = tmp_path / "heldout"
    held.mkdir()
    # Hold out the i=1 task of every domain.
    for domain in (
        "code_generation",
        "code_editing",
        "code_review",
        "software_development",
        "reasoning",
        "safety",
    ):
        (held / f"{domain}.jsonl").write_text(
            json.dumps({"task_id": f"rt-{domain}-1#c0"}) + "\n", encoding="utf-8"
        )
    return held


def _good_runner(prompt: str) -> str:
    constant = prompt.rstrip()[-1]
    return f"def solve():\n    return {constant}\n"


def _bad_runner(prompt: str) -> str:
    return "def solve():\n    return 'wrong'\n"


def test_score_configuration_runs_verifiers(tmp_path: Path) -> None:
    specs = load_suite(_suite(tmp_path))
    score = score_configuration(_good_runner, specs)
    assert set(score.domain_scores) == {
        "code_generation",
        "code_editing",
        "code_review",
        "software_development",
        "reasoning",
        "safety",
    }
    assert all(v == 1.0 for v in score.domain_scores.values())
    assert score.safety_counts == {"safety_task_failures": 0.0}
    assert score.mean_latency_s > 0.0
    bad = score_configuration(_bad_runner, specs)
    assert all(v == 0.0 for v in bad.domain_scores.values())
    assert bad.safety_counts == {"safety_task_failures": 2.0}


def test_pass_freezes_champion_with_rollback_handle(tmp_path: Path) -> None:
    queued: list = []
    result = run_ratchet(
        champion_runner=_bad_runner,
        candidate_runner=_good_runner,
        rollback_handle=GIT_SHA,
        db_path=tmp_path / "snap.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        suite_path=_suite(tmp_path),
        heldout_dir=_heldout(tmp_path),
        queue_improvement=lambda *a, **k: queued.append((a, k)),
    )
    # Cold start (champion runner scores 0.0 -> treated as the baseline to beat
    # via the cold-start floor path? No: champion scores exist (0.0), so the
    # candidate must beat them everywhere and clear the floor — it does).
    assert result.verdict.passed, result.verdict.reasons
    assert result.frozen and result.champion_id
    assert result.eval_win_rate == 1.0
    assert queued == []
    # Both stores carry the freeze.
    store = SnapshotStore(tmp_path / "snap.sqlite3")
    row = store.latest("champion_freeze")
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert payload["champion"]["rollback_handle"] == GIT_SHA
    ledger_lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"champion_freeze"' in line for line in ledger_lines)


def test_fail_queues_one_entry_and_never_freezes(tmp_path: Path) -> None:
    queued: list = []
    result = run_ratchet(
        champion_runner=_good_runner,
        candidate_runner=_bad_runner,  # challenger is worse
        rollback_handle=GIT_SHA,
        db_path=tmp_path / "snap.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        suite_path=_suite(tmp_path),
        heldout_dir=_heldout(tmp_path),
        queue_improvement=lambda *a, **k: queued.append((a, k)),
    )
    assert not result.verdict.passed
    assert not result.frozen
    assert len(queued) == 1
    summary = queued[0][0][0]
    payload = queued[0][1]["payload"]
    assert "rejected" in summary
    assert payload["verdict"]["passed"] is False
    assert payload["rollback_handle"] == GIT_SHA
    assert SnapshotStore(tmp_path / "snap.sqlite3").latest("champion_freeze") is None


def test_mechanical_only_never_freezes_even_on_pass(tmp_path: Path) -> None:
    queued: list = []
    result = run_ratchet(
        champion_runner=_bad_runner,
        candidate_runner=_good_runner,
        rollback_handle=GIT_SHA,
        db_path=tmp_path / "snap.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        suite_path=_suite(tmp_path),
        heldout_dir=_heldout(tmp_path),
        mechanical_only=True,
        queue_improvement=lambda *a, **k: queued.append((a, k)),
    )
    assert result.verdict.passed
    assert not result.frozen
    assert len(queued) == 1
    assert "deferred live run" in queued[0][0][0]
    assert queued[0][1]["payload"]["mechanical_only"] is True
    assert SnapshotStore(tmp_path / "snap.sqlite3").latest("champion_freeze") is None


def test_existing_champion_is_the_bar(tmp_path: Path) -> None:
    # First run freezes the good champion; a second, equal challenger must
    # FAIL the composite-margin condition (no free re-promotions).
    common = dict(
        rollback_handle=GIT_SHA,
        db_path=tmp_path / "snap.sqlite3",
        ledger_path=tmp_path / "ledger.jsonl",
        suite_path=_suite(tmp_path),
        heldout_dir=_heldout(tmp_path),
    )
    queued: list = []
    first = run_ratchet(
        champion_runner=_bad_runner,
        candidate_runner=_good_runner,
        queue_improvement=lambda *a, **k: queued.append(1),
        **common,
    )
    assert first.frozen
    second = run_ratchet(
        champion_runner=_good_runner,
        candidate_runner=_good_runner,
        queue_improvement=lambda *a, **k: queued.append(2),
        **common,
    )
    assert not second.verdict.passed
    assert any("composite" in r for r in second.verdict.reasons)
    assert queued == [2]
