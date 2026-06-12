"""Behavior-preserving extraction test for the ``route`` subcommand.

Grain ``g-jpmain-extract`` physically relocated the ``route`` subcommand
(parser setup + handler) out of ``muse_cli/jarvis_prime/__main__.py`` into
the sibling module ``muse_cli/jarvis_prime/cli_route.py``. These tests pin
the seam: ``route`` still parses, dispatches, and exits exactly as before, and
``--help`` still advertises it. They drive the public CLI entry point
(``main([...])``) so they exercise the real ``__main__`` → ``cli_route``
wiring rather than the extracted module in isolation.
"""

from __future__ import annotations

import json

import pytest

from muse_cli.jarvis_prime.__main__ import main


def test_route_single_task_class_json_dispatches(capsys) -> None:
    """``route --task coding_build --json`` parses, dispatches, exits 0."""
    rc = main(["route", "--task", "coding_build", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["task_class"] == "coding_build"
    # Decision dicts carry the routing fields the handler serializes.
    assert "chosen" in payload
    assert "fallback_chain" in payload


def test_route_all_task_classes_json_dispatches(capsys) -> None:
    """``route --json`` (no task) emits the full list of routes, exit 0."""
    rc = main(["route", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload, "expected at least one task-class route"
    assert all("task_class" in d for d in payload)


def test_route_unknown_task_class_exit_2(capsys) -> None:
    """Unknown task class → exit code 2 and an error naming known classes."""
    rc = main(["route", "--task", "definitely_not_a_task_class"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error:" in err
    assert "Known task classes:" in err
    # A real task class is listed in the guidance.
    assert "coding_build" in err


def test_route_listed_in_top_level_help(capsys) -> None:
    """``--help`` still advertises the ``route`` subcommand."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    # argparse prints help then exits 0.
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "route" in out
    assert "Explain the evidence-backed model route" in out


def test_route_subcommand_help_exits_0(capsys) -> None:
    """``route --help`` parses and exits 0, mentioning the --task flag."""
    with pytest.raises(SystemExit) as exc:
        main(["route", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--task" in out
    assert "--json" in out
