"""Phase 7 — ship it: the `python -m axiom` CLI, packaging metadata,
and the final audit path. CLI tests run main() in-process and assert
on real stdout.
"""

from __future__ import annotations

import json

import pytest

import axiom
from axiom.__main__ import main

UNIT_FORM = {
    "name": "double", "doc": "Double a number.",
    "params": {"x": "float"},
    "intent": "THE unit SHALL return two times x.",
    "contracts": ["result == x * 2.0"],
    "effects": [], "refs": {},
    "body": [
        {"op": "mul", "in": ["x", 2.0], "into": "y"},
        {"op": "return", "in": ["y"]},
    ],
}


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "data")


def _write_unit(tmp_path) -> str:
    p = tmp_path / "double.json"
    p.write_text(json.dumps(UNIT_FORM))
    return str(p)


def test_version_is_1_0_0():
    assert axiom.__version__ == "1.0.0"


def test_cli_verify_then_run_then_audit(tmp_path, data_dir, capsys):
    unit_path = _write_unit(tmp_path)

    rc = main(["--data-dir", data_dir, "verify", unit_path])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["ok"] is True
    unit_hash = out["unit_hash"]

    rc = main(["--data-dir", data_dir, "run", unit_hash,
               "--args", '{"x": 21.0}'])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out == {"ok": True, "result": 42.0}

    rc = main(["--data-dir", data_dir, "audit"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["chain_valid"] is True and out["events"] >= 2


def test_cli_verify_rejection_exits_nonzero(tmp_path, data_dir, capsys):
    bad = dict(UNIT_FORM, intent="just do it")
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    rc = main(["--data-dir", data_dir, "verify", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert any(e["check"] == "intent:EARS" for e in out["errors"])


def test_cli_mind_observe_and_recall(data_dir, capsys):
    rc = main(["--data-dir", data_dir, "mind", "observe",
               "the gateway port is 8088", "--source-grade", "verified"])
    assert rc == 0
    capsys.readouterr()
    rc = main(["--data-dir", data_dir, "mind", "recall",
               "what is the gateway port?", "-k", "3"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out and "gateway" in out[0]["content"]


def test_cli_forge(tmp_path, data_dir, capsys):
    cheat = dict(UNIT_FORM, name="cheat",
                 body=[{"op": "add", "in": ["x", 2.0], "into": "y"},
                       {"op": "return", "in": ["y"]}])
    spec = {"units": {"honest": UNIT_FORM, "cheat": cheat},
            "probes": [{"x": 3.0}]}
    p = tmp_path / "tournament.json"
    p.write_text(json.dumps(spec))
    rc = main(["--data-dir", data_dir, "forge", str(p)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["champion"] == "honest"
    assert out["gate_failed"] == ["cheat"]
