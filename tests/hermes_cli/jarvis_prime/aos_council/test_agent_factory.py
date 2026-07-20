"""Tests for hermes_cli.jarvis_prime.aos_council.agent_factory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.aos_council.agent_factory import (
    AgentSpec,
    create_agent,
    delete_agent,
    get_agent,
    list_agents,
)


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return tmp_path / "registry.json"


def test_create_and_get_roundtrip(registry: Path) -> None:
    spec = AgentSpec(
        name="rust-fixer",
        capabilities=["rust", "cargo", "ffi"],
        model="kimi-k3",
        system_prompt="You fix Rust code.",
        tools=["terminal", "patch"],
    )
    agent_id = create_agent(spec, registry_path=registry)
    assert agent_id == spec.agent_id

    loaded = get_agent(agent_id, registry_path=registry)
    assert loaded is not None
    assert loaded.name == "rust-fixer"
    assert loaded.capabilities == ["rust", "cargo", "ffi"]
    assert loaded.model == "kimi-k3"


def test_create_persists_to_disk(registry: Path) -> None:
    spec = AgentSpec(name="a", capabilities=["python"], model="m")
    create_agent(spec, registry_path=registry)
    data = json.loads(registry.read_text(encoding="utf-8"))
    assert "dynamic_agents" in data
    assert len(data["dynamic_agents"]) == 1
    assert data["dynamic_agents"][0]["name"] == "a"


def test_create_with_same_id_replaces(registry: Path) -> None:
    spec1 = AgentSpec(name="v1", capabilities=["python"], model="m1")
    create_agent(spec1, registry_path=registry)
    spec2 = AgentSpec(
        name="v2", capabilities=["rust"], model="m2", agent_id=spec1.agent_id
    )
    create_agent(spec2, registry_path=registry)
    agents = list_agents(registry_path=registry)
    assert len(agents) == 1
    assert agents[0].name == "v2"
    assert agents[0].capabilities == ["rust"]


def test_list_agents_returns_all(registry: Path) -> None:
    for i in range(3):
        create_agent(
            AgentSpec(name=f"a{i}", capabilities=["x"], model="m"),
            registry_path=registry,
        )
    agents = list_agents(registry_path=registry)
    assert len(agents) == 3
    assert {a.name for a in agents} == {"a0", "a1", "a2"}


def test_delete_agent(registry: Path) -> None:
    spec = AgentSpec(name="gone", capabilities=["x"], model="m")
    agent_id = create_agent(spec, registry_path=registry)
    assert delete_agent(agent_id, registry_path=registry) is True
    assert get_agent(agent_id, registry_path=registry) is None
    assert delete_agent(agent_id, registry_path=registry) is False  # already gone


def test_get_missing_returns_none(registry: Path) -> None:
    assert get_agent("no-such-id", registry_path=registry) is None


def test_list_agents_empty_when_no_file(tmp_path: Path) -> None:
    assert list_agents(registry_path=tmp_path / "nope.json") == []


def test_agent_spec_from_dict_tolerates_missing_keys() -> None:
    spec = AgentSpec.from_dict({"name": "minimal"})
    assert spec.name == "minimal"
    assert spec.capabilities == []
    assert spec.reputation == 0.5
    assert spec.agent_id  # auto-generated
