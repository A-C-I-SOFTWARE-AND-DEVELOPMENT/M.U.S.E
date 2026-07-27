"""Tests for niche schema, loader, forge, and pool indexing."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.niches.schema import NicheSpec, validate_niche_dict, slugify_capability
from hermes_cli.jarvis_prime.niches.forge import forge_niche
from hermes_cli.jarvis_prime.niches import loader as niche_loader


def test_validate_niche_id():
    with pytest.raises(ValueError):
        validate_niche_dict({"id": "Bad", "domain": "x", "system": "y", "keywords": ["a"]})
    validate_niche_dict(
        {
            "id": "security.owasp.injection",
            "domain": "security",
            "system": "You are a specialist.",
            "keywords": ["owasp", "injection"],
        }
    )


def test_slugify_capability():
    assert "security" in slugify_capability("security oauth oidc")


def test_forge_niche_creates_and_reuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(niche_loader, "SPECS_DIR", tmp_path)
    monkeypatch.setattr(niche_loader, "RUNTIME_REGISTRY", tmp_path / "runtime_registry.json")

    r1 = forge_niche("security oauth oidc flows", domain="security")
    assert r1.ok and r1.created and r1.spec is not None
    assert (tmp_path / f"{r1.spec.id}.yaml").exists()

    r2 = forge_niche("security oauth oidc flows", domain="security")
    assert r2.ok and not r2.created
    assert r2.spec and r2.spec.id == r1.spec.id


def test_seeded_niches_load():
    niches = niche_loader.load_all_niches()
    assert len(niches) >= 100
    ids = {n.id for n in niches}
    assert any(i.startswith("security.") for i in ids)


def test_forge_niche_tool_registers_and_routes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(niche_loader, "SPECS_DIR", tmp_path)
    monkeypatch.setattr(niche_loader, "RUNTIME_REGISTRY", tmp_path / "runtime_registry.json")

    from tools.forge_niche_tool import forge_niche_tool
    from hermes_cli.jarvis_prime.agent_pool import invalidate_pool, route, CAT_NICHE

    out = forge_niche_tool(
        capability="widget frobulator tuning",
        domain="widgets",
        toolsets=["filesystem", "codebase"],
    )
    assert "forge_niche" in out
    assert "widgets." in out or "frobulator" in out.lower()
    assert (tmp_path / "runtime_registry.json").exists()

    invalidate_pool()
    matches = route("widget frobulator tuning", limit=8, min_score=0.3)
    assert any(m.entry.category == CAT_NICHE for m in matches)


def test_agent_pool_indexes_niches():
    from hermes_cli.jarvis_prime.agent_pool import get_pool, invalidate_pool, CAT_NICHE, route

    invalidate_pool()
    pool = get_pool()
    niches = pool.by_category(CAT_NICHE)
    assert len(niches) >= 100
    matches = route("49 CFR placarding hazmat", limit=5)
    assert matches
    assert any(m.entry.category == CAT_NICHE for m in matches)

