"""Tests for the richer behavioral-risk sources (trajectory + decision ledger)."""

import json

from muse_cli.jarvis_prime import behavioral_risk as br
from muse_cli.jarvis_prime.monitor_collectors import (
    collect_context,
    collect_worker_actions_from_decision_ledger,
    collect_worker_actions_from_trajectory,
)


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_trajectory_collector_surfaces_workaround(tmp_path):
    path = tmp_path / "traj.jsonl"
    _write_jsonl(
        path,
        [
            {
                "model": "codex",
                "completed": True,
                "conversations": [
                    {"from": "human", "value": "make it pass"},
                    {"from": "assistant", "value": "I'll run pytest --no-verify to skip it"},
                ],
            }
        ],
    )
    actions = collect_worker_actions_from_trajectory(path)
    assert actions and actions[0]["worker_id"] == "codex"
    cats = {f.category.value for f in br.classify(actions)}
    assert "destructive_workaround" in cats


def test_trajectory_collector_blind_when_missing(tmp_path):
    assert collect_worker_actions_from_trajectory(tmp_path / "nope.jsonl") is None


def test_decision_ledger_collector_is_shape_tolerant(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_jsonl(
        path,
        [
            {"payload": {"worker": "claude-code", "command": "git push --force"}},
            {
                "worker": "claude-code",
                "changed_files": ["README.md", "auth.py"],
                "out_of_scope_files": ["auth.py"],
            },
            {"payload": {"requested_owner_action": "production_deploy"}},
            {"payload": {"requested_owner_action": "production_deploy"}},
        ],
    )
    actions = collect_worker_actions_from_decision_ledger(path)
    assert actions is not None
    cats = {f.category.value for f in br.classify(actions)}
    assert "destructive_cleanup" in cats  # git push --force
    assert "scope_expansion" in cats  # auth.py out of scope
    assert "privilege_escalation" in cats  # repeated production_deploy request


def test_decision_ledger_blind_when_missing(tmp_path):
    assert collect_worker_actions_from_decision_ledger(tmp_path / "nope.jsonl") is None


def test_collect_context_merges_all_sources(tmp_path):
    traj = tmp_path / "t.jsonl"
    _write_jsonl(
        traj,
        [
            {
                "model": "m",
                "completed": False,
                "conversations": [{"from": "assistant", "value": "git reset --hard"}],
            }
        ],
    )
    decision = tmp_path / "d.jsonl"
    _write_jsonl(decision, [{"payload": {"requested_owner_action": "production_deploy"}}])
    ctx = collect_context(
        trajectory_path=traj,
        decision_ledger_path=decision,
        guardrail_ledger_path=tmp_path / "absent.jsonl",
    )
    assert "worker_actions" in ctx
    assert len(ctx["worker_actions"]) >= 2  # merged from trajectory + decision ledger
    cats = {f.category.value for f in br.classify(ctx["worker_actions"])}
    assert "destructive_cleanup" in cats
