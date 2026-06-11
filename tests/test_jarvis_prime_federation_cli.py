"""End-to-end tests for the federation CLI (federation/main.py)."""

import json

import pytest

from hermes_cli.jarvis_prime.federation.main import cli_main


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def test_identity_attest_import_round_trip(home, tmp_path, capsys):
    assert cli_main(["identity", "init", "--name", "alpha"]) == 0
    assert cli_main(["identity", "show", "--json"]) == 0
    capsys.readouterr()

    # Seed the ledger so there is a head to attest, then export + import.
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    GuardrailLedger().append("test_seed", "s", {"n": 1})
    bundle_path = tmp_path / "bundle.json"
    assert cli_main(["attest", "--out", str(bundle_path)]) == 0
    assert bundle_path.exists()
    assert cli_main(["import", str(bundle_path), "--json"]) == 0
    assert cli_main(["peers", "--json"]) == 0
    out = capsys.readouterr().out
    assert "node_" in out
    # A re-import of the identical bundle is not divergent.
    assert cli_main(["diverge", str(bundle_path)]) == 0


def test_scale_recommend_default_is_stay_solo(home, capsys):
    assert cli_main(["scale", "recommend"]) == 0
    out = capsys.readouterr().out
    assert "A_solo" in out
    assert "stay solo" in out.lower()
    assert cli_main(["scale", "matrix", "--json"]) == 0


def test_amend_evaluate_refuses_locked_clause(home, tmp_path, capsys):
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps({"clause_ids": ["C35"], "kind": "modify", "scale": "E_enterprise"}),
        encoding="utf-8",
    )
    assert cli_main(["amend", "evaluate", "--proposal", str(proposal), "--json"]) == 1
    out = capsys.readouterr().out
    assert "non-amendable" in out

    allowed = tmp_path / "allowed.json"
    allowed.write_text(
        json.dumps({"clause_ids": ["C38"], "kind": "add", "scale": "A_solo"}),
        encoding="utf-8",
    )
    assert cli_main(["amend", "evaluate", "--proposal", str(allowed), "--json"]) == 0


def test_quorum_file_flow(home, tmp_path, capsys):
    qfile = tmp_path / "quorum.json"
    assert (
        cli_main(
            [
                "quorum",
                "create",
                "--action",
                "force_push",
                "--signers",
                "alice,bob,carol",
                "--threshold",
                "2",
                "--out",
                str(qfile),
            ]
        )
        == 0
    )
    capsys.readouterr()
    data = json.loads(qfile.read_text(encoding="utf-8"))
    # Finalize refuses before the threshold is met.
    assert cli_main(["quorum", "finalize", "--file", str(qfile)]) == 1
    for signer in ("alice", "bob"):
        phrase = data["per_signer"][signer]["required_phrase"]
        assert (
            cli_main(
                ["quorum", "respond", "--file", str(qfile), "--signer", signer, "--phrase", phrase]
            )
            == 0
        )
        data = json.loads(qfile.read_text(encoding="utf-8"))
    assert cli_main(["quorum", "status", "--file", str(qfile), "--json"]) == 0
    assert cli_main(["quorum", "finalize", "--file", str(qfile), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"threshold": 2' in out


def test_sovereignty_and_compliance(home, tmp_path, capsys):
    from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

    GuardrailLedger().append("test_seed", "s", {"n": 1})
    assert cli_main(["sovereignty"]) == 0
    out = capsys.readouterr().out
    assert "sovereignty index: 1.00" in out

    package_path = tmp_path / "evidence.json"
    assert (
        cli_main(["compliance", "export", "--framework", "eu-ai-act", "--out", str(package_path)])
        == 0
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["chain_diagnostics"]["ok"] is True
    assert {c["control_id"] for c in package["controls"]} == {
        "Art9",
        "Art11",
        "Art12",
        "Art14",
        "Art15",
    }


def test_main_module_delegation(home, capsys):
    from hermes_cli.jarvis_prime.__main__ import main

    assert main(["federation", "scale", "recommend"]) == 0
    assert "A_solo" in capsys.readouterr().out
