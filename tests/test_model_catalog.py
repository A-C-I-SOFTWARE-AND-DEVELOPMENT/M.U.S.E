"""Tests for the pre-wired model catalog loader (``hermes_model_catalog``)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hermes_model_catalog import load_catalog


def test_real_catalog_loads_and_validates():
    """The shipped config/model-catalog.yaml is well-formed."""
    catalog = load_catalog()
    assert catalog.version >= 1
    assert len(catalog.models) > 0
    # Every default resolves (enforced by the loader, asserted here too).
    for tier, refs in catalog.defaults.items():
        for ref in refs:
            assert catalog.by_ref(ref) is not None, f"{tier} -> {ref}"


def test_local_models_are_always_ready():
    catalog = load_catalog()
    local = [m for m in catalog.models if m.requires_env is None]
    assert local, "expected at least one keyless local model"
    for m in local:
        assert m.is_ready(env={})  # no key needed


def test_readiness_tracks_env_keys():
    catalog = load_catalog()
    # With only OpenRouter set, openrouter models are ready; novita aren't.
    env = {"OPENROUTER_API_KEY": "sk-test"}
    ready_refs = {m.ref for m in catalog.ready_models(env)}
    assert any(r.startswith("openrouter/") for r in ready_refs)
    assert not any(r.startswith("novita/") for r in ready_refs)
    # Local models are ready regardless.
    assert any(r.startswith("ollama-local/") for r in ready_refs)


def test_default_for_picks_first_ready_in_tier():
    catalog = load_catalog()
    # No cloud keys → frontier falls through to nothing (all cloud),
    # but local tier still resolves to a keyless model.
    local_default = catalog.default_for("local", env={})
    assert local_default is not None
    assert local_default.requires_env is None


def test_media_readiness():
    catalog = load_catalog()
    env = {"FAL_KEY": "fal-test"}
    image = {mp.provider for mp in catalog.ready_media("image", env)}
    assert "fal" in image
    assert "openai" not in image  # no OPENAI_API_KEY set


def test_duplicate_ref_is_rejected(tmp_path: Path):
    bad = tmp_path / "dupe.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            providers:
              openrouter:
                requires_env: OPENROUTER_API_KEY
                plugin: model-providers/openrouter
                models:
                  - {id: dup, model: a/b, family: llama}
                  - {id: dup, model: a/c, family: llama}
            """
        ).strip()
    )
    with pytest.raises(ValueError, match="Duplicate model ref"):
        load_catalog(bad)


def test_unknown_default_ref_is_rejected(tmp_path: Path):
    bad = tmp_path / "baddefault.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            defaults:
              fast: [openrouter/does-not-exist]
            providers:
              openrouter:
                requires_env: OPENROUTER_API_KEY
                plugin: model-providers/openrouter
                models:
                  - {id: real, model: a/b, family: llama}
            """
        ).strip()
    )
    with pytest.raises(ValueError, match="unknown model"):
        load_catalog(bad)


def test_missing_required_field_is_rejected(tmp_path: Path):
    bad = tmp_path / "missing.yaml"
    bad.write_text(
        textwrap.dedent(
            """
            version: 1
            providers:
              openrouter:
                requires_env: OPENROUTER_API_KEY
                plugin: model-providers/openrouter
                models:
                  - {id: nomodel, family: llama}
            """
        ).strip()
    )
    with pytest.raises(ValueError, match="missing fields"):
        load_catalog(bad)
