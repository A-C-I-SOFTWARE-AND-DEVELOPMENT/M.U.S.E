"""Cockpit orchestrator-seats endpoint — read-only roster + routing status."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from hermes_cli.orchestrator_trio import FULL_ROSTER, TRIO_ROLES, install_trio


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate Path.home() and HERMES_HOME so profiles/config land in tmp_path."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    default_home = tmp_path / ".hermes"
    default_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(default_home))
    return tmp_path


def test_seats_empty_home_reports_uninstalled(home):
    res = h.seats_status(h.Request(method="GET", path="x"))
    assert res.status == 200
    seats = res.payload["seats"]
    assert [s["profile"] for s in seats] == [r.profile for r in FULL_ROSTER]
    for seat in seats:
        assert seat["installed"] is False
        assert seat["model_pinned"] is None
    # Honest empty routing — nothing installed, nothing fabricated.
    assert res.payload["kanban"] == {
        "orchestrator_profile": "",
        "default_assignee": "",
    }


def test_seats_reflect_installed_trio(home):
    install_trio()

    res = h.seats_status(h.Request(method="GET", path="x"))
    assert res.status == 200
    by_profile = {s["profile"]: s for s in res.payload["seats"]}

    for role in TRIO_ROLES:
        seat = by_profile[role.profile]
        assert seat["installed"] is True
        assert seat["model_pinned"] == role.model
        assert seat["model_preset"] == role.model
        assert seat["provider"] == role.provider
        assert seat["catalog_ref"] == role.catalog_ref
        assert seat["title"] == role.title
        assert seat["description"] == role.description

    # The core preset leaves the extended bench uninstalled — reported honestly.
    for role in FULL_ROSTER[len(TRIO_ROLES):]:
        assert by_profile[role.profile]["installed"] is False
        assert by_profile[role.profile]["model_pinned"] is None

    assert res.payload["kanban"] == {
        "orchestrator_profile": "orchestrator",
        "default_assignee": "executor",
    }


def test_seats_pinned_model_can_diverge_from_preset(home):
    import yaml

    install_trio()
    exec_cfg = home / ".hermes" / "profiles" / "executor" / "config.yaml"
    data = yaml.safe_load(exec_cfg.read_text(encoding="utf-8"))
    data["model"] = {"provider": "custom", "default": "my/model"}
    exec_cfg.write_text(yaml.safe_dump(data), encoding="utf-8")

    res = h.seats_status(h.Request(method="GET", path="x"))
    seat = {s["profile"]: s for s in res.payload["seats"]}["executor"]
    assert seat["model_pinned"] == "my/model"
    assert seat["model_preset"] == "meituan/longcat-2.0"
