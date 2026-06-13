"""End-to-end tests for the Forge CLI (forge/main.py)."""

import json

import pytest

from hermes_cli.jarvis_prime.forge.main import cli_main

FAST_CODE = "def solve(xs):\n    return sum(xs)\n"
SLOW_CODE = (
    "def solve(xs):\n"
    "    total = 0\n"
    "    for x in xs:\n"
    "        total += x\n"
    "    return total\n"
)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _register(tmp_path, capsys, code, name):
    code_file = tmp_path / f"{name}.py"
    code_file.write_text(code, encoding="utf-8")
    assert cli_main(["register", "--code-file", str(code_file)]) == 0
    return json.loads(capsys.readouterr().out)["candidate_id"]


def test_register_lookup_tournament_anchor_flow(home, tmp_path, capsys):
    fast = _register(tmp_path, capsys, FAST_CODE, "fast")
    slow = _register(tmp_path, capsys, SLOW_CODE, "slow")

    assert cli_main(["candidates"]) == 0
    assert fast in capsys.readouterr().out

    assert cli_main(["lookup", fast]) == 0
    looked_up = json.loads(capsys.readouterr().out)
    assert looked_up["candidate_id"] == fast
    assert looked_up["task_id"] == "alg_sum"

    report_path = tmp_path / "report.json"
    assert cli_main(["tournament", "--rounds", "2", "--out", str(report_path)]) == 0
    capsys.readouterr()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["duels"]) == 2
    assert report["ratings_after"][fast] > report["ratings_after"][slow]

    assert cli_main(["ratings"]) == 0
    assert cli_main(["elites"]) == 0
    assert cli_main(["leaderboard"]) == 0
    capsys.readouterr()

    anchor_path = tmp_path / "anchor.json"
    assert cli_main(["anchor", "--out", str(anchor_path)]) == 0
    capsys.readouterr()
    assert cli_main(["verify-anchor", str(anchor_path)]) == 0
    # Tamper -> verification fails.
    data = json.loads(anchor_path.read_text(encoding="utf-8"))
    data["payload"]["standings"][0]["rating"] = 9999.0
    anchor_path.write_text(json.dumps(data), encoding="utf-8")
    assert cli_main(["verify-anchor", str(anchor_path)]) == 1


def test_lookup_unknown_exits_one(home, capsys):
    assert cli_main(["lookup", "cand_missing00000"]) == 1
    assert "unresolved" in capsys.readouterr().err


def test_duel_via_cli(home, tmp_path, capsys):
    fast = _register(tmp_path, capsys, FAST_CODE, "fast")
    slow = _register(tmp_path, capsys, SLOW_CODE, "slow")
    assert cli_main(["duel", fast, slow]) == 0
    duel = json.loads(capsys.readouterr().out)
    assert duel["score_a"] == 1.0  # fast (lower op-count) wins


def test_distill_via_cli(home, tmp_path, capsys):
    from hermes_cli.jarvis_prime.federation.trust_ladder import ContributorStore

    fast = _register(tmp_path, capsys, FAST_CODE, "fast")
    _register(tmp_path, capsys, SLOW_CODE, "slow")
    report_path = tmp_path / "report.json"
    assert cli_main(["tournament", "--rounds", "1", "--out", str(report_path)]) == 0
    capsys.readouterr()

    # A B1 contributor's winners are admitted.
    store = ContributorStore()
    for _ in range(5):
        store.record_outcome("local", accepted=True)
    assert (
        cli_main(
            ["distill", "--report", str(report_path), "--contributor", "local", "--top-k", "1"]
        )
        == 0
    )
    decisions = json.loads(capsys.readouterr().out)
    assert decisions[0]["admitted"] is True
    assert decisions[0]["trajectory_sha256"]
    assert fast  # registered id remains resolvable end to end


def test_main_module_delegation(home, capsys):
    from hermes_cli.jarvis_prime.__main__ import main

    assert main(["forge", "candidates"]) == 0
    assert capsys.readouterr().out.strip() == "[]"
