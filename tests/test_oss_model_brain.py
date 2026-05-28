"""Tests for the OSS model brain — hermes_cli.oss_model_brain + the
JARVIS Prime bridge in hermes_cli.jarvis_prime.model_brain.

These are hermetic: they exercise the built-in fallback catalog and the
shipped YAML on disk. No network, no provider credentials.
"""

from __future__ import annotations

import contextlib
import io

from hermes_cli import oss_model_brain as ob


# ---------------------------------------------------------------------------
# Built-in catalog
# ---------------------------------------------------------------------------


def test_builtin_catalog_loads_and_has_no_duplicate_ids() -> None:
    cat = ob.builtin_catalog()
    assert cat.source == "builtin"
    assert len(cat.families) >= 10
    ids = cat.ids()
    assert len(ids) == len(set(ids)), "duplicate ids in built-in catalog"


def test_routing_ids_all_exist_in_builtin() -> None:
    # Integrity: every model id referenced by routing must be a real family.
    cat = ob.builtin_catalog()
    for task, ids in cat.routing:
        for mid in ids:
            assert cat.by_id(mid) is not None, f"routing[{task}] references unknown {mid!r}"


def test_recommend_follows_routing_order() -> None:
    cat = ob.builtin_catalog()
    coding = [m.id for m in cat.recommend("coding")]
    assert coding[0] == "deepseek-v4"
    assert "glm-5" in coding and "qwen3-coder" in coding
    # bug_fix prefers GLM-5 (best real-bug fixer) ahead of deepseek-v4.
    bug = [m.id for m in cat.recommend("bug_fix")]
    assert bug[0] == "glm-5"
    assert bug.index("glm-5") < bug.index("deepseek-v4")


def test_local_only_filters_to_local_variants() -> None:
    cat = ob.builtin_catalog()
    coding_local = cat.recommend("coding", local_only=True)
    assert coding_local, "expected at least one local coder"
    assert all(m.local for m in coding_local)
    assert "qwen3-coder" in [m.id for m in coding_local]
    # A cloud-only frontier model must be excluded.
    assert "deepseek-v4" not in [m.id for m in coding_local]


def test_license_filter_keeps_only_allowed() -> None:
    cat = ob.builtin_catalog()
    mit = cat.recommend("reasoning", license_allow={"MIT"})
    assert mit, "expected MIT reasoning models"
    assert all(m.license_spdx.upper() == "MIT" for m in mit)
    # Apache-only Qwen3-235B must drop out of the MIT-only list.
    assert "qwen3-235b" not in [m.id for m in mit]


def test_available_providers_filters_and_resolves() -> None:
    cat = ob.builtin_catalog()
    # Only deepseek installed → only families reachable via deepseek survive.
    only_ds = cat.recommend("coding", available_providers={"deepseek"})
    assert [m.id for m in only_ds] == ["deepseek-v4"]
    ref = only_ds[0].resolve_provider({"deepseek"})
    assert ref is not None and ref.provider == "deepseek"

    # With ollama-cloud + openrouter, deepseek-v4 resolves to openrouter
    # (deepseek not installed, openrouter is a listed fallback).
    via = cat.recommend("coding", available_providers={"ollama-cloud", "openrouter"})
    dv4 = next(m for m in via if m.id == "deepseek-v4")
    dv4_ref = dv4.resolve_provider({"ollama-cloud", "openrouter"})
    assert dv4_ref is not None and dv4_ref.provider == "openrouter"


def test_resolve_provider_semantics() -> None:
    cat = ob.builtin_catalog()
    m = cat.by_id("deepseek-v4")
    assert m is not None
    # None available → first listed provider (preference order).
    first = m.resolve_provider(None)
    assert first is not None and first.provider == "deepseek"
    # Empty / non-matching set → None.
    assert m.resolve_provider(set()) is None
    assert m.resolve_provider({"not-a-provider"}) is None


def test_best_and_unknown_task() -> None:
    cat = ob.builtin_catalog()
    top = cat.best("agentic_coding")
    assert top is not None and top.id == "glm-5"
    # Unknown task with no best_for match → empty / None.
    assert cat.recommend("interpretive_dance") == []
    assert cat.best("interpretive_dance") is None


def test_fallback_by_best_for_when_task_not_routed() -> None:
    # Build a catalog whose routing omits a task that families still list
    # in best_for, to prove the best_for fallback path orders by tier.
    fams = (
        ob.OssModel(id="big", tier="frontier", best_for=("vision",),
                    benchmarks=(("x", 50.0),), providers=(ob.ProviderRef("p", "m"),)),
        ob.OssModel(id="small", tier="local", best_for=("vision",), local=True,
                    benchmarks=(("x", 90.0),), providers=(ob.ProviderRef("p", "m"),)),
    )
    cat = ob.OssCatalog(families=fams, routing=())
    ranked = [m.id for m in cat.recommend("vision")]
    assert ranked == ["big", "small"], "frontier tier should outrank local in fallback"


def test_duplicate_ids_rejected_at_construction() -> None:
    dup = (ob.OssModel(id="x"), ob.OssModel(id="x"))
    try:
        ob.OssCatalog(families=dup)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError on duplicate ids")


# ---------------------------------------------------------------------------
# Shipped YAML on disk
# ---------------------------------------------------------------------------


def test_shipped_yaml_loads_and_is_internally_consistent() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    assert cat.source == "yaml", "expected to load the shipped YAML, not the fallback"
    assert cat.updated_at, "catalog must carry an updated_at date"
    assert cat.sources, "catalog must cite validation sources"
    assert len(cat.families) >= 10

    for task, ids in cat.routing:
        for mid in ids:
            assert cat.by_id(mid) is not None, f"YAML routing[{task}] -> unknown {mid!r}"

    for fam in cat.families:
        assert fam.providers, f"{fam.id} has no provider mapping"
        assert fam.license_spdx, f"{fam.id} missing license_spdx"
        assert fam.tier in ob.TIERS, f"{fam.id} has unknown tier {fam.tier!r}"
        assert fam.why, f"{fam.id} missing a rationale"
    ob.reset_cache()


def test_yaml_and_builtin_cover_the_same_tasks() -> None:
    ob.reset_cache()
    yaml_cat = ob.load_oss_catalog()
    builtin = ob.builtin_catalog()
    assert set(yaml_cat.tasks()) == set(builtin.tasks()), (
        "built-in fallback routing has drifted from the shipped YAML"
    )
    ob.reset_cache()


# ---------------------------------------------------------------------------
# JARVIS Prime bridge
# ---------------------------------------------------------------------------


def test_bridge_recommend_and_known_tasks() -> None:
    from hermes_cli.jarvis_prime import model_brain as mb

    # only_installed=False so the test never depends on host providers.
    models = mb.recommend_models("coding", only_installed=False)
    assert models and models[0].id == "deepseek-v4"
    for t in mb.KNOWN_TASKS:
        assert mb.recommend_models(t, only_installed=False), f"no models for {t}"


def test_bridge_render_is_human_readable() -> None:
    from hermes_cli.jarvis_prime import model_brain as mb

    text = mb.render_recommendation("reasoning", only_installed=False, limit=3)
    assert "OSS model brain" in text
    assert "deepseek-r1" in text
    assert "Sources" in text  # cited evidence is part of the contract


def test_bridge_render_empty_for_unknown_task() -> None:
    from hermes_cli.jarvis_prime import model_brain as mb

    text = mb.render_recommendation("interpretive_dance", only_installed=False)
    assert "no catalog match" in text


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_cli_models_json_returns_zero_and_valid_payload() -> None:
    import json

    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["models", "coding", "--all-providers", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["task"] == "coding"
    assert payload["results"], "expected at least one result"
    assert payload["results"][0]["id"] == "deepseek-v4"


def test_cli_models_tasks_lists_categories() -> None:
    from hermes_cli.jarvis_prime.__main__ import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["models", "tasks"])
    assert rc == 0
    out = buf.getvalue()
    assert "coding" in out and "local_reasoning" in out
