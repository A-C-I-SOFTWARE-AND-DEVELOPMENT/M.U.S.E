from __future__ import annotations

from hermes_cli.jarvis_prime.model_scorecard import ModelScorecard, ScorecardBook
from hermes_cli.jarvis_prime.task_router import (
    TaskClass,
    all_routes,
    explain,
    load_overrides,
    route_for_task,
    set_paid_enabled,
    set_task_override,
)


def _policy(
    *,
    local=True,
    local_models=("qwen3-coder",),
    claude=False,
    codex=False,
    hosted=(),
    paid=False,
    paid_providers=(),
):
    return {
        "route_order": [
            "local_oss",
            "hosted_free_or_user_configured_oss",
            "claude_code_worker",
            "codex_worker",
            "paid_api_explicit_only",
        ],
        "routes": {
            "local_oss": {
                "enabled": local,
                "recommended_local_models": list(local_models),
            },
            "hosted_free_or_user_configured_oss": {
                "enabled": bool(hosted),
                "providers": list(hosted),
            },
            "claude_code_worker": {"enabled": claude},
            "codex_worker": {"enabled": codex},
            "paid_api_explicit_only": {
                "enabled": bool(paid_providers),
                "providers_detected": list(paid_providers),
            },
        },
        "paid": {"enabled": paid},
        "local_defaults": [],
    }


def _empty_book(tmp_path):
    return ScorecardBook(path=tmp_path / "s.jsonl")


def test_local_first_with_no_evidence(tmp_path):
    """Fresh install with only a local runtime routes local-first, deterministically."""
    d = route_for_task(
        TaskClass.MOBILE_CHAT,
        policy=_policy(local_models=("qwen3:8b",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "qwen3:8b"
    assert d.route_tier == "local_oss"
    assert d.local_first is True
    assert "policy preference" in d.why


def test_coding_build_prefers_worker_lane(tmp_path):
    """coding_build profile prefers the Claude worker lane over local when enabled."""
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local_models=("qwen3-coder",), claude=True, codex=True),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "claude"
    assert "codex" in d.fallback_chain
    assert "qwen3-coder" in d.fallback_chain  # local stays as a fallback


def test_fallback_when_preferred_route_disabled(tmp_path):
    """With the worker lanes off, coding_build falls back to the next enabled tier."""
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local_models=("qwen3-coder",), claude=False, codex=False),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "qwen3-coder"
    assert d.route_tier == "local_oss"


def test_evidence_changes_ranking(tmp_path):
    """A measured-strong model overtakes the local-first prior (scorecards move it)."""
    book = _empty_book(tmp_path)
    policy = _policy(local_models=("weak-local",), claude=True)
    # Before evidence: local-first prior would pick... coding tasks prefer claude.
    before = route_for_task(
        TaskClass.CODING_BUILD, policy=policy, book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert before.chosen == "claude"  # by tier preference (no samples)

    # Record strong evidence for the local model on coding_build.
    book.record(
        ModelScorecard(
            "weak-local", "ollama", "coding_build",
            risk_class="RC3", tests_passed=19, tests_failed=1,
            accepted_diff_rate=0.95, tool_reliability=0.95,
        ),
        persist=False,
    )
    after = route_for_task(
        TaskClass.CODING_BUILD, policy=policy, book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert after.chosen == "weak-local"
    assert after.evidence and after.evidence[0]["model"] == "weak-local"


def test_weak_evidence_does_not_beat_local_prior(tmp_path):
    """A measured-weak model must NOT be chosen over the unmeasured local prior."""
    book = _empty_book(tmp_path)
    book.record(
        ModelScorecard(
            "cloud-bad", "hosted", "mobile_chat",
            tests_passed=1, tests_failed=9, owner_corrections=3,
        ),
        persist=False,
    )
    d = route_for_task(
        TaskClass.MOBILE_CHAT,
        policy=_policy(local_models=("qwen3:8b",), hosted=("cloud-bad",)),
        book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "qwen3:8b"


def test_paid_excluded_unless_enabled_and_allowed(tmp_path):
    book = _empty_book(tmp_path)
    # research allows paid, but it's disabled → paid provider not a candidate.
    off = route_for_task(
        TaskClass.RESEARCH,
        policy=_policy(local_models=("qwen3:8b",), paid=False, paid_providers=("openai",)),
        book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert "openai" not in off.fallback_chain

    on = route_for_task(
        TaskClass.RESEARCH,
        policy=_policy(local_models=("qwen3:8b",), paid=True, paid_providers=("openai",)),
        book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert "openai" in on.fallback_chain

    # mobile_chat never allows paid, even when enabled.
    chat = route_for_task(
        TaskClass.MOBILE_CHAT,
        policy=_policy(local_models=("qwen3:8b",), paid=True, paid_providers=("openai",)),
        book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert "openai" not in chat.fallback_chain


def test_owner_override_pins_model(tmp_path):
    d = route_for_task(
        TaskClass.SUMMARIZATION,
        policy=_policy(local_models=("qwen3:8b",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {"summarization": "my-model"}},
    )
    assert d.chosen == "my-model"
    assert d.route_tier == "owner_override"
    assert d.owner_override == "my-model"


def test_all_routes_covers_every_task_class(tmp_path):
    routes = all_routes(
        policy=_policy(local_models=("qwen3:8b",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert {r.task_class for r in routes} == {tc.value for tc in TaskClass}
    assert all(isinstance(explain(r), str) for r in routes)


def test_override_store_round_trip(tmp_path):
    path = tmp_path / "ov.json"
    set_task_override("coding_build", "claude", path=path)
    data = load_overrides(path)
    assert data["task_overrides"]["coding_build"] == "claude"
    set_task_override("coding_build", None, path=path)
    assert "coding_build" not in load_overrides(path)["task_overrides"]


def test_paid_toggle_requires_authorization(tmp_path):
    path = tmp_path / "ov.json"
    try:
        set_paid_enabled(True, authorized=False, path=path)
        assert False, "expected PermissionError"
    except PermissionError:
        pass
    set_paid_enabled(True, authorized=True, path=path)
    assert load_overrides(path)["paid_enabled"] is True


# ---------------------------------------------------------------------------
# Hosted-tier task-class routing (default ON; OSS-catalog-ordered; reversible)
# ---------------------------------------------------------------------------


def test_hosted_taskclass_expands_for_coding(tmp_path):
    """coding_build hosted candidates expand to coding families (GLM leads agentic)."""
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("openrouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.route_tier == "hosted_free_or_user_configured_oss"
    chosen = d.chosen
    assert chosen is not None
    assert chosen.startswith("openrouter/")
    assert "glm-5" in chosen  # agentic_coding lane leads with GLM


def test_hosted_taskclass_research_leads_reasoning(tmp_path):
    """research hosted candidates lead with a reasoning family, not a coder."""
    d = route_for_task(
        TaskClass.RESEARCH,
        policy=_policy(local=False, hosted=("openrouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    chosen = d.chosen
    assert chosen is not None
    assert chosen.startswith("openrouter/")
    assert "deepseek-r1" in chosen


def test_hosted_disable_flag_restores_bare_provider(tmp_path, monkeypatch):
    """The owner escape hatch restores the legacy bare-provider-id candidate."""
    monkeypatch.setenv("HERMES_JARVIS_HOSTED_TASKCLASS", "off")
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("openrouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "openrouter"


def test_hosted_expansion_falls_back_when_catalog_unavailable(tmp_path, monkeypatch):
    """If the OSS catalog can't load, hosted stays the bare provider id."""
    import hermes_cli.oss_model_brain as ob

    def _boom(*a, **k):
        raise RuntimeError("no catalog / no PyYAML")

    monkeypatch.setattr(ob, "load_oss_catalog", _boom)
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("openrouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "openrouter"


def test_owner_override_wins_over_hosted_expansion(tmp_path):
    """An owner pin beats the (default-on) hosted task-class expansion."""
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("openrouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {"coding_build": "pinned"}},
    )
    assert d.chosen == "pinned"
    assert d.route_tier == "owner_override"


def test_hosted_evidence_matches_expanded_candidate_by_family(tmp_path):
    """A scorecard recorded under the family id ('qwen3-coder') still re-ranks
    the expanded hosted candidate ('openrouter/qwen/qwen3-coder'), and the
    rationale reflects measured evidence (no self-contradiction)."""
    book = _empty_book(tmp_path)
    for _ in range(3):
        book.record(
            ModelScorecard(
                "qwen3-coder", "openrouter", "coding_build",
                risk_class="RC3", tests_passed=20, tests_failed=0,
                accepted_diff_rate=0.97, tool_reliability=0.99,
            ),
            persist=False,
        )
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("openrouter",)),
        book=book,
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    # qwen3-coder is LAST in the agentic_coding ordering, but measured evidence
    # (matched by family across the provider/model string) lifts it to the top.
    assert d.chosen == "openrouter/qwen/qwen3-coder"
    assert "measured evidence" in d.why
    assert "no scorecards yet" not in d.why


def test_hosted_expansion_dedups_provider_casing(tmp_path):
    """A non-lowercase configured provider must not be re-appended as a bare
    duplicate of the expanded candidates."""
    d = route_for_task(
        TaskClass.CODING_BUILD,
        policy=_policy(local=False, claude=False, codex=False, hosted=("OpenRouter",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert "OpenRouter" not in d.fallback_chain  # no bare duplicate leaks
    assert all("/" in c for c in d.fallback_chain)  # every candidate expanded
    chosen = d.chosen
    assert chosen is not None
    assert chosen.startswith("openrouter/")


# ---------------------------------------------------------------------------
# Declarative output constraints (MUSE verifiable-arena findings, 2026-06-27)
# ---------------------------------------------------------------------------


def _route_simple(tc, tmp_path):
    return route_for_task(
        tc,
        policy=_policy(local_models=("qwen3-coder", "gpt-oss:20b", "qwen3.5:9b")),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )


def test_arena_flagged_lanes_declare_output_constraints(tmp_path):
    """The arena routing_aligned=false lanes declare post-gen constraints.

    ``algorithms`` and the creative ``companion`` reply now have their OWN task
    classes; the complexity-bar also lives on the coding lanes that absorb
    algorithm work.
    """
    for tc in (TaskClass.SUMMARIZATION, TaskClass.RESEARCH, TaskClass.COMPANION,
               TaskClass.ALGORITHMS, TaskClass.CODING_PLAN, TaskClass.CODING_BUILD):
        d = _route_simple(tc, tmp_path)
        assert d.output_constraints, f"{tc.value} should declare output constraints"
        # to_dict serializes each constraint to a {kind, detail, params} dict.
        serialized = d.to_dict()["output_constraints"]
        assert serialized == [c.to_dict() for c in d.output_constraints]
        assert all({"kind", "detail", "params"} <= set(s) for s in serialized)
        # Human-readable detail is surfaced in explain().
        for c in d.output_constraints:
            assert c.detail in explain(d)


def test_summarization_declares_150_word_cap(tmp_path):
    d = _route_simple(TaskClass.SUMMARIZATION, tmp_path)
    assert any(c.kind == "max_words" and c.param("limit") == 150
               for c in d.output_constraints)


def test_companion_routes_creative_specialist_and_caps_words(tmp_path):
    """The new companion lane wires the local_creative / qwythos specialist and
    declares the 30-55 word envelope + banned-phrase floor."""
    d = route_for_task(
        TaskClass.COMPANION,
        policy=_policy(local_models=("qwen3.5:9b", "qwythos-mythos-9b", "qwen3-coder")),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    )
    assert d.chosen == "qwythos-mythos-9b"  # creative specialist leads its lane
    kinds = {c.kind for c in d.output_constraints}
    assert {"min_words", "max_words", "banned_phrases"} <= kinds


def test_lanes_without_constraints_stay_empty(tmp_path):
    """Lanes the arena did not flag declare none — routing/decisions unchanged.

    MOBILE_CHAT is back to NO constraints (the creative caps moved to COMPANION).
    """
    for tc in (TaskClass.MOBILE_CHAT, TaskClass.CODING_REVIEW, TaskClass.TEST_DEBUG,
               TaskClass.VOICE_REPLY, TaskClass.MEMORY_CURATOR,
               TaskClass.CITATION_VERIFICATION):
        d = _route_simple(tc, tmp_path)
        assert d.output_constraints == []
        assert d.to_dict()["output_constraints"] == []


def test_all_routes_carry_constraints_field(tmp_path):
    """Every decision exposes the field (default empty list), never missing."""
    for d in all_routes(
        policy=_policy(local_models=("qwen3-coder",)),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
    ):
        assert isinstance(d.output_constraints, list)
        assert "output_constraints" in d.to_dict()
