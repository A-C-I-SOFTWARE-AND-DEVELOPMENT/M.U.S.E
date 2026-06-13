"""Tests for the Linear skill's label/assignee name→id resolution.

Loads the standalone script by path (it is a skill script, not a package) and
mocks ``gql`` so no network call is made. Covers the create/update wiring that
previously had a ``TODO`` instead of resolving ``--label`` / ``--assignee``.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "productivity"
    / "linear"
    / "scripts"
    / "linear_api.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("linear_api_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)  # ty: ignore[invalid-argument-type]  # script-by-path test fixture
    assert spec.loader is not None  # ty: ignore[unresolved-attribute]  # script-by-path test fixture
    sys.modules[spec.name] = module  # ty: ignore[unresolved-attribute]  # script-by-path test fixture
    spec.loader.exec_module(module)  # ty: ignore[unresolved-attribute]  # script-by-path test fixture
    return module


# Canned GraphQL responses keyed on a substring of the query text.
def _fake_gql_factory(captured):
    def fake_gql(query, variables=None):
        captured.append((query, variables))
        if "teams(first: 100)" in query:
            return {"teams": {"nodes": [{"id": "team-uuid", "key": "ENG", "name": "Eng"}]}}
        if "team(id: $id)" in query and "labels" in query:
            return {"team": {"labels": {"nodes": [{"id": "lab-uuid", "name": "Bug"}]}}}
        if "issueLabels(first: 250)" in query:
            return {"issueLabels": {"nodes": [{"id": "wlab-uuid", "name": "Bug"}]}}
        if "users(first: 250)" in query:
            return {
                "users": {
                    "nodes": [
                        {
                            "id": "user-uuid",
                            "name": "jane",
                            "displayName": "Jane Doe",
                            "email": "jane@example.com",
                        }
                    ]
                }
            }
        if "issueCreate" in query:
            captured.append(("CREATE_INPUT", variables["input"]))
            return {"issueCreate": {"success": True, "issue": {"identifier": "ENG-1"}}}
        if "issueUpdate" in query:
            captured.append(("UPDATE_INPUT", variables["input"]))
            return {"issueUpdate": {"success": True, "issue": {"identifier": "ENG-1"}}}
        return {}

    return fake_gql


def test_create_issue_resolves_label_and_assignee(monkeypatch, capsys):
    mod = load_module()
    captured: list = []
    monkeypatch.setattr(mod, "gql", _fake_gql_factory(captured))

    args = argparse.Namespace(
        title="Boom",
        team="ENG",
        description=None,
        priority=None,
        parent=None,
        label="Bug",
        assignee="Jane Doe",
    )
    mod.cmd_create_issue(args)

    create_input = next(v for k, v in captured if k == "CREATE_INPUT")
    assert create_input["teamId"] == "team-uuid"
    assert create_input["labelIds"] == ["lab-uuid"]  # team-scoped label
    assert create_input["assigneeId"] == "user-uuid"  # matched on displayName


def test_create_issue_unknown_label_exits(monkeypatch):
    mod = load_module()
    monkeypatch.setattr(mod, "gql", _fake_gql_factory([]))
    args = argparse.Namespace(
        title="Boom",
        team="ENG",
        description=None,
        priority=None,
        parent=None,
        label="Nonexistent",
        assignee=None,
    )
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create_issue(args)
    assert exc.value.code == 1


def test_update_issue_resolves_workspace_label_and_assignee(monkeypatch):
    mod = load_module()
    captured: list = []
    monkeypatch.setattr(mod, "gql", _fake_gql_factory(captured))

    args = argparse.Namespace(
        identifier="ENG-1",
        title=None,
        description=None,
        priority=None,
        label="Bug",
        assignee="jane@example.com",
    )
    mod.cmd_update_issue(args)

    update_input = next(v for k, v in captured if k == "UPDATE_INPUT")
    assert update_input["labelIds"] == ["wlab-uuid"]  # workspace-scoped (no team)
    assert update_input["assigneeId"] == "user-uuid"  # matched on email
