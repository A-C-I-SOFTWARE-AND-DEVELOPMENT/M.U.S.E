"""Tests for the OSS model brain — hermes_cli.oss_model_brain + the
muse bridge in hermes_cli.jarvis_prime.model_brain.

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
            assert cat.by_id(mid) is not None, (
                f"routing[{task}] references unknown {mid!r}"
            )


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
        ob.OssModel(
            id="big",
            tier="frontier",
            best_for=("vision",),
            benchmarks=(("x", 50.0),),
            providers=(ob.ProviderRef("p", "m"),),
        ),
        ob.OssModel(
            id="small",
            tier="local",
            best_for=("vision",),
            local=True,
            benchmarks=(("x", 90.0),),
            providers=(ob.ProviderRef("p", "m"),),
        ),
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
            assert cat.by_id(mid) is not None, (
                f"YAML routing[{task}] -> unknown {mid!r}"
            )

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
# Candidate (unverified-slug) tagging — the "no fake certainty" rule (FU-23)
# ---------------------------------------------------------------------------

# Families whose provider model-ids are a just-released variant whose slugs +
# benchmark numbers aren't yet verified against each provider's live model list.
# Mirrors the rows tagged ``candidate`` in config/model-catalog.yaml.
_EXPECTED_CANDIDATES = {
    "deepseek-v4",
    "glm-5",
    "kimi-k2",
    "minimax-m2",
    "qwen3-coder",
    "qwen3-235b",
    "qwen3-vl",
}


def test_candidate_defaults_false() -> None:
    # The flag is opt-in: a bare model (and any model without the field) is
    # verified by default, so older catalogs/tests keep their meaning.
    assert ob.OssModel(id="x").candidate is False


def test_unverified_slugs_carry_candidate_after_yaml_load() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    assert cat.source == "yaml", "expected the shipped YAML, not the fallback"
    flagged = {f.id for f in cat.families if f.candidate}
    assert flagged == _EXPECTED_CANDIDATES, (
        "candidate flags drifted from the unverified just-released variants"
    )
    # And the verified families must NOT be flagged (no false positives) —
    # spot-check the stable, locally-grounded ones the disclaimer excludes.
    for verified in ("deepseek-r1", "gpt-oss-20b", "gemma4", "bge-m3"):
        fam = cat.by_id(verified)
        assert fam is not None and fam.candidate is False, (
            f"{verified} is verified and must not be candidate-tagged"
        )
    ob.reset_cache()


def test_candidate_flag_survives_to_dict_roundtrip() -> None:
    ob.reset_cache()
    cat = ob.load_oss_catalog()
    payload = cat.to_dict()
    by_id = {f["id"]: f for f in payload["families"]}
    assert by_id["glm-5"]["candidate"] is True
    assert by_id["deepseek-r1"]["candidate"] is False
    ob.reset_cache()


def test_yaml_and_builtin_agree_on_candidate_set() -> None:
    # Fourth sync point: the built-in fallback's candidate flags must match the
    # shipped YAML exactly, the same way the routing/tasks parity test guards
    # drift. A new candidate in one place must be mirrored in the other.
    ob.reset_cache()
    yaml_cat = ob.load_oss_catalog()
    builtin = ob.builtin_catalog()
    yaml_flagged = {f.id for f in yaml_cat.families if f.candidate}
    builtin_flagged = {f.id for f in builtin.families if f.candidate}
    assert yaml_flagged == builtin_flagged, (
        "built-in candidate flags have drifted from the shipped YAML"
    )
    assert yaml_flagged == _EXPECTED_CANDIDATES
    ob.reset_cache()


# ---------------------------------------------------------------------------
# task_router._hosted_candidates orders verified slugs before candidates
# ---------------------------------------------------------------------------


def test_hosted_candidates_orders_verified_before_candidate() -> None:
    """A mixed lane sinks candidate-tagged slugs below verified ones, stably,
    and never drops a candidate."""
    from hermes_cli.jarvis_prime import task_router as tr

    ob.reset_cache()
    # ``reasoning`` mixes verified (deepseek-r1, gpt-oss-120b) with candidates
    # (qwen3-235b, glm-5, deepseek-v4). With every provider configured, the
    # verified slugs must precede the candidate ones; deepseek-r1 (already first
    # + verified) stays first, and gpt-oss-120b (verified) jumps ahead of the
    # candidate qwen3-235b/glm-5 that the raw catalog order had before it.
    providers = [
        "openrouter", "novita", "nvidia", "deepseek", "zai",
        "minimax", "kimi-coding", "qwen-oauth", "ollama-cloud", "huggingface",
    ]
    route = {"providers": providers}
    # A lane that genuinely mixes verified + candidate families at the hosted tier.
    reasoning_profile = tr.TaskProfile(
        risk_class="RC2", catalog_task="reasoning", local_first=False,
        paid_allowed=True,
    )
    out = tr._hosted_candidates(route, reasoning_profile)

    cat = ob.load_oss_catalog()
    # Map each emitted "provider/model" slug back to its family's candidate flag.
    # Bare provider ids (no "/") are the pre-existing never-shrink tail fallback
    # and are orthogonal to the verified/candidate partition, so the ordering
    # contract is checked over the *mapped* slugs only.
    def _flag(slug: str) -> bool:
        prov, model = slug.split("/", 1)
        for fam in cat.families:
            for ref in fam.providers:
                if ref.provider == prov and ref.model == model:
                    return fam.candidate
        return False  # unmatched expansion → treat as verified

    mapped = [c for c in out if "/" in c]
    flags = [_flag(c) for c in mapped]
    # Among mapped slugs: every verified (False) precedes every candidate (True).
    first_candidate = next((i for i, f in enumerate(flags) if f), len(flags))
    assert not any(flags[:first_candidate]), "a candidate leaked ahead of verified"
    assert all(flags[first_candidate:]), (
        f"verified slug appears after a candidate: {list(zip(mapped, flags))}"
    )
    assert first_candidate > 0, "this lane should have at least one verified slug"
    assert first_candidate < len(flags), "this lane should have at least one candidate"
    # Concretely: the verified deepseek-r1 family (slug deepseek/deepseek-reasoner)
    # leads, and the verified gpt-oss slug precedes the candidate qwen3-235b /
    # glm-5 that the raw catalog order had ahead of it.
    assert mapped[0] == "deepseek/deepseek-reasoner"
    gpt_idx = next(i for i, c in enumerate(mapped) if "gpt-oss" in c)
    glm_idx = next(i for i, c in enumerate(mapped) if "glm-5" in c)
    q235_idx = next(i for i, c in enumerate(mapped) if "qwen3-235b" in c)
    assert gpt_idx < glm_idx and gpt_idx < q235_idx
    # No candidate was DROPPED: both candidate slugs survive in the output.
    assert any("glm-5" in c for c in out) and any("qwen3-235b" in c for c in out)
    ob.reset_cache()


def test_hosted_candidates_all_candidate_lane_unchanged() -> None:
    """An all-candidate lane (every coding family is a candidate) keeps the
    catalog's order byte-for-byte — verified-first only re-orders *mixed* lanes."""
    from hermes_cli.jarvis_prime import task_router as tr

    ob.reset_cache()
    route = {"providers": ["openrouter"]}
    profile = tr.TASK_PROFILES[tr.TaskClass.CODING_BUILD]  # agentic_coding
    out = tr._hosted_candidates(route, profile)
    # agentic_coding leads with GLM (all families candidate-tagged → no shuffle).
    assert out and out[0] == "openrouter/z-ai/glm-5"
    assert out == [
        "openrouter/z-ai/glm-5",
        "openrouter/deepseek/deepseek-v4",
        "openrouter/moonshotai/kimi-k2",
        "openrouter/minimax/minimax-m2",
        "openrouter/qwen/qwen3-coder",
    ]
    ob.reset_cache()


def test_hosted_candidates_disabled_flag_is_byte_for_byte_bare(monkeypatch) -> None:
    """The owner escape hatch and the empty-provider path are untouched by the
    verified-first partition (no candidate logic runs)."""
    from hermes_cli.jarvis_prime import task_router as tr

    monkeypatch.setenv("HERMES_JARVIS_HOSTED_TASKCLASS", "off")
    profile = tr.TASK_PROFILES[tr.TaskClass.CODING_BUILD]
    assert tr._hosted_candidates({"providers": ["openrouter"]}, profile) == ["openrouter"]
    assert tr._hosted_candidates({"providers": []}, profile) == []


# ---------------------------------------------------------------------------
# muse bridge
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
