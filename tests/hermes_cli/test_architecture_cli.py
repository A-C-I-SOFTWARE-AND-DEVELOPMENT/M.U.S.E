"""Tests for the ``jarvis_prime architecture`` CLI subcommand.

Exercises the read-only surface over the component registry — list (plain +
JSON + filters), show (plain + JSON), and the unknown-id error path — by
invoking the CLI entrypoint, which is the coverage the parallel
``data-sources`` command currently lacks.
"""

from __future__ import annotations

import json

from hermes_cli.jarvis_prime.__main__ import main


def test_architecture_list_plain(capsys):
    rc = main(["architecture", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "owner_authorization" in out
    assert "GATED" in out  # at least one owner-gated component is flagged


def test_architecture_list_json_roundtrips(capsys):
    rc = main(["architecture", "list", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    ids = {c["id"] for c in data}
    assert {"owner_authorization", "verification_gates", "orchestrator"} <= ids


def test_architecture_list_filters(capsys):
    rc = main(["architecture", "list", "--owner-gated", "--risk", "RC4", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    ids = {c["id"] for c in data}
    assert "owner_authorization" in ids  # the canonical RC4 owner-gated component
    assert all(c["is_owner_gated"] and c["risk_class"] == "RC4" for c in data)


def test_architecture_list_kind_filter(capsys):
    rc = main(["architecture", "list", "--kind", "governance", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data and all(c["kind"] == "governance" for c in data)


def test_architecture_show_plain(capsys):
    rc = main(["architecture", "show", "verification_gates"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Eight-gate verification chain" in out
    assert "hermes_cli/jarvis_prime/gates.py" in out


def test_architecture_show_json(capsys):
    rc = main(["architecture", "show", "graphrag", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    comp = json.loads(out)
    assert comp["id"] == "graphrag"
    assert comp["kind"] == "cognition"


def test_architecture_show_unknown_id_errors(capsys):
    rc = main(["architecture", "show", "does-not-exist"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "unknown component" in err


def test_architecture_list_kind_filter_json(capsys):
    rc = main(["architecture", "list", "--kind", "governance", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data and all(c["kind"] == "governance" for c in data)


def test_architecture_list_empty_result(capsys):
    # An impossible filter combo returns cleanly, not a crash.
    rc = main(["architecture", "list", "--kind", "surface", "--risk", "RC4"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no matching components" in out


def test_architecture_registry_override(capsys, tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        "schema: muse.component_registry.v1\n"
        "components:\n"
        "  - {id: solo, name: Solo, kind: runtime, "
        "owner_module: run_agent.py, risk_class: RC0}\n",
        encoding="utf-8",
    )
    rc = main(["architecture", "list", "--registry", str(custom), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert [c["id"] for c in data] == ["solo"]
