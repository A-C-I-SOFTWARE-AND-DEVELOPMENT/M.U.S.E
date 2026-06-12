"""Tests for the Plane 4 domain registry + fail-closed autonomy admission."""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime.research_fabric.domains import (
    DomainNotAutonomous,
    admit_for_autonomy,
    domains,
    get_domain,
)


def test_registry_has_core_domains() -> None:
    keys = {d.key for d in domains()}
    assert {"algorithms", "swe_local", "prose"} <= keys


def test_executable_domains_are_autonomy_eligible() -> None:
    assert get_domain("algorithms").autonomy_eligible is True  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    assert get_domain("swe_local").autonomy_eligible is True  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_verifierless_domain_is_not_autonomy_eligible() -> None:
    assert get_domain("prose").autonomy_eligible is False  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_admit_for_autonomy_allows_verifier_domain() -> None:
    assert admit_for_autonomy("algorithms").key == "algorithms"


def test_admit_for_autonomy_refuses_verifierless() -> None:
    with pytest.raises(DomainNotAutonomous):
        admit_for_autonomy("prose")


def test_admit_for_autonomy_refuses_unknown() -> None:
    with pytest.raises(DomainNotAutonomous):
        admit_for_autonomy("does_not_exist")
