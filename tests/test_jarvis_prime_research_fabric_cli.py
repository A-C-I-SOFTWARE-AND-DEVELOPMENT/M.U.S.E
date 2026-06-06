"""Smoke tests for the research-fabric CLI wiring."""

from __future__ import annotations

import json

import pytest

from hermes_cli.jarvis_prime.research_fabric.main import build_parser, cli_main


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_home"))
    yield


def test_parser_builds() -> None:
    parser = build_parser()
    assert parser.prog == "research-fabric"


def test_inventory_runs(capsys) -> None:
    rc = cli_main(["inventory"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "models" in out and "benchmarks" in out


def test_validate_cold_start_json(tmp_path, capsys) -> None:
    scores = {
        "code_generation": 0.9,
        "code_editing": 0.9,
        "code_review": 0.9,
        "software_development": 0.9,
        "reasoning": 0.9,
        "safety": 0.9,
    }
    rc = cli_main(["--repo-root", str(tmp_path), "validate", "--scores", json.dumps(scores)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["cold_start"] is True
    assert out["passed"] is True


def test_report_chain_ok(tmp_path, capsys) -> None:
    rc = cli_main(["--repo-root", str(tmp_path), "report"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ledger_chain"]["ok"] is True
    assert out["store_chain"]["ok"] is True


def test_champion_show_empty(tmp_path, capsys) -> None:
    rc = cli_main(["--repo-root", str(tmp_path), "champion", "show"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["champion"] is None


def test_charter_challenge_then_status(tmp_path, capsys) -> None:
    rc = cli_main(["charter", "challenge", "--allowed-kinds", "skill_update"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["required_phrase"].startswith("Yes, with authorization. Code:")
    # Status reflects no charter granted yet.
    rc2 = cli_main(["charter", "status"])
    assert rc2 == 0
    status = json.loads(capsys.readouterr().out)
    assert status["active_charter"] is None


def test_selfplay_run_accepts_seed_tasks(tmp_path, capsys) -> None:
    rc = cli_main(["--repo-root", str(tmp_path), "selfplay", "run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["accepted_count"] == out["attempted"]
    assert out["acceptance_rate"] == 1.0


def test_selfplay_evolve_improves(tmp_path, capsys) -> None:
    rc = cli_main(["--repo-root", str(tmp_path), "selfplay", "evolve", "--generations", "3"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["improved"] is True
    assert out["best_opcount"] < out["baseline_opcount"]


def test_archive_list_empty(tmp_path, capsys) -> None:
    rc = cli_main(["--repo-root", str(tmp_path), "archive", "list"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 0


def test_run_dry_run_no_charter_proposes(tmp_path, capsys) -> None:
    spec = {
        "candidate_id": "c1",
        "kind": "skill_update",
        "target_path": "skills/foo/SKILL.md",
        "risk_class": "RC1",
        "domain_scores": {d: 0.92 for d in (
            "code_generation", "code_editing", "code_review",
            "software_development", "reasoning", "safety",
        )},
        "holdout_scores": {"software_development": 0.92},
        "eval_win_rate": 0.6,
    }
    spec_path = tmp_path / "cand.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    rc = cli_main(["--repo-root", str(tmp_path), "run", "--candidate-json", str(spec_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # No charter -> the dry-run still routes to a proposal decision.
    assert out["applied"] is False
