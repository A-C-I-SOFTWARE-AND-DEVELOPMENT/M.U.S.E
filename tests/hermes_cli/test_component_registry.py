"""Tests for the M.U.S.E component registry.

These tests are the drift guard: they assert the documented architecture in
``docs/architecture/muse-component-registry.yaml`` stays consistent with the
real code — every owner_module path and doc path resolves on disk, every
risk_class is a real work-packet risk class, and every owner-gated action is a
member of the canonical ``owner_auth.OWNER_GATED_ACTIONS`` frozenset (so the
registry references the single source of truth rather than copying it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.component_registry import (
    DEFAULT_REGISTRY_PATH,
    SCHEMA,
    VALID_KINDS,
    Component,
    by_kind,
    get,
    load_registry,
    owner_gated_components,
)
from hermes_cli.jarvis_prime.owner_auth import OWNER_GATED_ACTIONS
from hermes_cli.jarvis_prime.work_packet import VALID_RISK_CLASSES

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def registry() -> list[Component]:
    return load_registry()


# --- registry integrity -----------------------------------------------------


def test_registry_loads_and_ids_are_unique_and_sorted(registry):
    assert registry, "registry should not be empty"
    ids = [c.id for c in registry]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)  # unique ids


def test_every_entry_has_valid_kind_and_risk_class(registry):
    for c in registry:
        assert c.kind in VALID_KINDS, f"{c.id}: bad kind {c.kind!r}"
        assert c.risk_class in VALID_RISK_CLASSES, f"{c.id}: bad risk_class {c.risk_class!r}"
        assert c.name and c.owner_module


def test_default_registry_path_points_at_shipped_yaml():
    assert DEFAULT_REGISTRY_PATH.exists()
    assert DEFAULT_REGISTRY_PATH.name == "muse-component-registry.yaml"


def test_schema_header_is_declared(registry):
    # SCHEMA is exported for consumers; the loader rejects mismatches.
    assert SCHEMA == "muse.component_registry.v1"


# --- the drift guards (registry <-> code) -----------------------------------


def test_owner_gated_actions_subset_of_canonical_set(registry):
    """Constitution C9: the registry references owner_auth, never a copy."""

    for c in registry:
        for action in c.owner_gated_actions:
            assert action in OWNER_GATED_ACTIONS, (
                f"{c.id}: owner_gated_action {action!r} is not in the canonical "
                "owner_auth.OWNER_GATED_ACTIONS frozenset"
            )


def test_every_owner_module_path_resolves(registry):
    for c in registry:
        target = c.owner_module_path(_REPO_ROOT)
        assert target.exists(), f"{c.id}: owner_module {c.owner_module!r} does not exist"


def test_every_doc_path_resolves(registry):
    for c in registry:
        for doc in c.doc_paths(_REPO_ROOT):
            assert doc.exists(), f"{c.id}: doc {doc} does not exist"


# --- partitions + env override ----------------------------------------------


def test_partitions_and_lookup(registry):
    assert get("owner_authorization", components=registry) is not None
    assert get("does-not-exist", components=registry) is None
    assert by_kind("governance", components=registry)
    gated = owner_gated_components(registry)
    assert gated, "at least one component should be owner-gated"
    assert all(c.is_owner_gated for c in gated)


def test_env_override_resolves_registry(tmp_path, monkeypatch):
    from hermes_cli.jarvis_prime import component_registry as cr

    custom = tmp_path / "custom.yaml"
    custom.write_text(
        "schema: muse.component_registry.v1\n"
        "components:\n"
        "  - {id: only, name: Only, kind: runtime, "
        "owner_module: run_agent.py, risk_class: RC0}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(cr.REGISTRY_PATH_ENV, str(custom))
    components = load_registry()  # no explicit path -> uses env
    assert [c.id for c in components] == ["only"]


def test_missing_registry_raises_actionable_error(monkeypatch):
    from hermes_cli.jarvis_prime import component_registry as cr

    monkeypatch.delenv(cr.REGISTRY_PATH_ENV, raising=False)
    monkeypatch.setattr(cr, "_PACKAGED_REGISTRY_PATH", Path("/no/such/packaged.yaml"))
    monkeypatch.setattr(cr, "DEFAULT_REGISTRY_PATH", Path("/no/such/docs.yaml"))
    with pytest.raises(FileNotFoundError, match="muse component registry not found"):
        cr.resolve_registry_path()


def test_invalid_owner_gated_action_raises():
    with pytest.raises(ValueError, match="owner_gated_actions"):
        Component.from_dict(
            {
                "id": "x",
                "name": "X",
                "kind": "runtime",
                "owner_module": "run_agent.py",
                "risk_class": "RC1",
                "owner_gated_actions": ["not_a_real_gate"],
            }
        )


def test_missing_required_field_raises():
    with pytest.raises(ValueError):
        Component.from_dict({"id": "x", "name": "X"})  # missing kind/owner_module/risk_class
