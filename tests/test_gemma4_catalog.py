"""Gemma 4 — catalog + OSS-brain wiring tests.

Hermetic: exercises the shipped YAML/catalog + built-in fallback. No network,
no Ollama, no downloads.
"""

from __future__ import annotations

from hermes_model_catalog import load_catalog
from hermes_cli.local_models.catalog import load_open_weight_catalog
from hermes_cli import oss_model_brain as ob


def test_provider_catalog_has_gemma_and_keeps_llama_fallback() -> None:
    catalog = load_catalog()
    gemma = {m.id for m in catalog.models if m.family == "gemma"}
    assert {"gemma4-e2b", "gemma4-e4b", "gemma4-12b"} <= gemma
    # Local/fast defaults lead with the qwen3.5 fast generalist (see
    # MODEL_SPECIALISTS), include Gemma, and keep a llama as a fallback.
    assert catalog.defaults["local"][0] == "ollama-local/qwen3_5-9b"
    assert "ollama-local/gemma4-12b" in catalog.defaults["local"]
    assert "ollama-local/gemma4-12b" in catalog.defaults["fast"]
    assert any("llama" in ref for ref in catalog.defaults["fast"])
    # Every default still resolves (loader invariant).
    for refs in catalog.defaults.values():
        for ref in refs:
            assert catalog.by_ref(ref) is not None, ref
    # Gemma locals need no API key. (Cloud gemma — e.g. cerebras/gemma-4-31b-it
    # — is keyed, so only the local providers are held to this.)
    for m in catalog.models:
        if m.family == "gemma" and m.provider in ("ollama-local", "llamacpp-local"):
            assert m.is_ready(env={})


def test_open_weight_candidates_validate_and_are_tier_gated() -> None:
    cat = load_open_weight_catalog()
    gemma = {m.name for m in cat.models if "gemma" in m.name}
    assert {"gemma4-e2b", "gemma4-e4b", "gemma4-26b-a4b", "gemma4-31b"} <= gemma
    for m in cat.models:
        if "gemma" in m.name:
            assert m.license == "Apache-2.0"
            assert m.runtime == "ollama"
            assert set(m.tiers) <= {"laptop", "desktop", "workstation", "server"}
    # Small variants fit a laptop; large ones are workstation/server only.
    laptop = {m.name for m in cat.for_tier("laptop")}
    assert {"gemma4-e2b", "gemma4-e4b"} <= laptop
    assert "gemma4-26b-a4b" not in laptop and "gemma4-31b" not in laptop
    e2b = cat.get("gemma4-e2b")
    big = cat.get("gemma4-31b")
    assert e2b is not None and big is not None
    assert e2b.fits(ram_gb=16.0, vram_gb=0.0)
    assert not big.fits(ram_gb=16.0, vram_gb=0.0)


def test_oss_brain_recommends_gemma_for_local_memory_voice() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    for lane in ("memory_curator", "mobile_chat", "voice_reply", "local_reasoning"):
        recs = cat.recommend(lane)
        assert recs and recs[0].id == "gemma4", lane
    ob.reset_cache()


def test_oss_brain_does_not_put_gemma_first_for_coding() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    assert cat.recommend("coding")[0].id != "gemma4"
    assert cat.recommend("agentic_coding")[0].id != "gemma4"
    # On review, Gemma is only a trailing fallback (present, never first).
    review = [m.id for m in cat.recommend("coding_review")]
    assert review[0] != "gemma4"
    assert "gemma4" in review
    ob.reset_cache()


def test_gemma_family_is_local_apache_and_cited() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    fam = cat.by_id("gemma4")
    assert fam is not None
    assert fam.local and fam.local_runner == "ollama"
    assert fam.license_spdx == "Apache-2.0"
    assert fam.providers and any("ollama" in p.provider for p in fam.providers)
    assert fam.sources, "vendor sources must be cited"
    # Built-in fallback covers the same family + lanes (stripped-install parity).
    builtin = ob.builtin_catalog()
    assert builtin.by_id("gemma4") is not None
    assert set(builtin.tasks()) == set(cat.tasks())
    ob.reset_cache()
