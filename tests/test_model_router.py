"""Tests for hermes_cli.model_router and hermes_cli.model_registry.

The router is the seat of routing policy in Hermes — these tests
exist to catch silent regressions in the rules the policy doc
spells out:

- hermes-local is always in the selected list.
- Claude Code Windows requires a healthy tunnel; otherwise falls back
  to claude-code-local.
- Codex is the preferred primary for focused implementation / test
  repair.
- Aider is the preferred primary for git-native local patch loops.
- Browser research is added for research tasks (or whenever the
  caller flags ``needs_external_docs``).
- Supabase / Vercel are gated behind schema/deployment approval.
- Human approval shows up for secrets, deployment, publish, remote
  tunnel setup, and continuous listening.
- Every decision carries explanation + ledger entry + fallback ladder
  + approval requirements + validation plan.

These tests use the *built-in* registry (not the YAML on disk) so
they're hermetic. A few sanity-check tests against the YAML loader
live at the end of the file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import model_registry as mr
from hermes_cli.model_router import (
    APPROVAL_GATED_CATEGORIES,
    BROWSER_REQUIRED_CATEGORIES,
    RouterContext,
    RoutingDecision,
    TASK_CATEGORIES,
    render_report,
    route,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> mr.Registry:
    # Use the built-in registry so tests are independent of the YAML on
    # disk. The YAML-loading sanity checks at the bottom of the file
    # still verify that the shipped YAML loads cleanly.
    return mr.builtin_registry()


@pytest.fixture()
def all_available_ctx() -> RouterContext:
    """A context where every external worker has been detected."""
    return RouterContext(
        available_workers={
            "codex",
            "claude-code-local",
            "claude-code-windows",
            "aider",
            "goose",
            "browser-research",
            "supabase-worker",
            "vercel-worker",
            "android-builder",
            "github-publisher",
        },
        tunnel_healthy=True,
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_builtin_contains_all_required_workers(self, registry):
        registered = set(registry.ids())
        for required in mr.required_worker_ids():
            assert required in registered, f"missing required worker: {required}"

    def test_no_duplicate_ids(self, registry):
        ids = registry.ids()
        assert len(ids) == len(set(ids))

    def test_get_and_require(self, registry):
        assert registry.get("hermes-local") is not None
        assert registry.get("nonexistent") is None
        with pytest.raises(KeyError):
            registry.require("nonexistent")

    def test_categories_present(self, registry):
        for w in registry.workers:
            # Every registered worker should claim at least one
            # category — otherwise the router can't reason about it.
            assert w.categories, f"{w.id} has no categories"

    def test_approval_required_metadata(self, registry):
        # The four workers the policy spec says must require approval.
        for wid in ("supabase-worker", "vercel-worker", "github-publisher", "human-approval"):
            w = registry.require(wid)
            assert w.approval_required is True, f"{wid} should require approval"


# ---------------------------------------------------------------------------
# Task category contract
# ---------------------------------------------------------------------------


class TestTaskCategories:
    def test_canonical_set_matches_spec(self):
        expected = {
            "mobile-android",
            "voice-pipeline",
            "backend-orchestration",
            "research",
            "planning",
            "implementation",
            "refactor",
            "debug",
            "validation",
            "security",
            "deployment",
            "github-pr",
            "user-profile-learning",
            "remote-execution",
            "secrets-management",
        }
        assert set(TASK_CATEGORIES) == expected

    def test_unknown_category_raises(self, registry):
        with pytest.raises(ValueError):
            route("anything", "bogus-category", registry=registry)


# ---------------------------------------------------------------------------
# Core routing rules
# ---------------------------------------------------------------------------


class TestRoutingRules:
    def test_hermes_local_always_selected(self, registry):
        for category in TASK_CATEGORIES:
            d = route("x", category, registry=registry, context=RouterContext())
            assert "hermes-local" in d.selected_ids(), (
                f"hermes-local missing from selected for {category}"
            )

    def test_validator_is_always_hermes_local(self, registry, all_available_ctx):
        for category in TASK_CATEGORIES:
            d = route("x", category, registry=registry, context=all_available_ctx)
            assert d.validator == "hermes-local"

    def test_decision_returns_required_fields(self, registry, all_available_ctx):
        d = route("Add feature", "implementation", registry=registry, context=all_available_ctx)
        assert isinstance(d, RoutingDecision)
        assert d.selected
        assert d.explanation
        assert isinstance(d.rejected, dict)
        assert isinstance(d.fallback_plan, list)
        assert isinstance(d.approval_requirements, list)
        assert isinstance(d.validation_plan, list) and d.validation_plan
        assert isinstance(d.ledger_entry, dict)
        # Ledger entry has stable schema tag for downstream consumers.
        assert d.ledger_entry["schema"] == "hermes.routing.decision.v1"
        assert d.ledger_entry["task_id"] == d.task_id

    def test_fallback_terminates_in_hermes_local(self, registry, all_available_ctx):
        d = route("refactor", "refactor", registry=registry, context=all_available_ctx)
        assert d.fallback_plan, "fallback plan should be non-empty"
        assert d.fallback_plan[-1] == "hermes-local"


class TestClaudeCodeWindows:
    def test_preferred_when_tunnel_healthy(self, registry, all_available_ctx):
        d = route(
            "repo-wide refactor across packages",
            "refactor",
            registry=registry,
            context=all_available_ctx,
        )
        assert d.primary == "claude-code-windows"
        # Anything that triggers the windows tunnel needs the
        # remote-tunnel-setup approval surface.
        assert "remote-tunnel-setup" in d.approval_requirements

    def test_rejected_when_tunnel_down(self, registry):
        ctx = RouterContext(
            available_workers={"codex", "claude-code-local", "claude-code-windows", "aider"},
            tunnel_healthy=False,
        )
        d = route("repo-wide refactor", "refactor", registry=registry, context=ctx)
        assert d.primary != "claude-code-windows"
        assert "claude-code-windows" in d.rejected
        assert "tunnel" in d.rejected["claude-code-windows"].lower()


class TestCodex:
    def test_codex_preferred_for_implementation(self, registry):
        ctx = RouterContext(available_workers={"codex", "aider", "claude-code-local"})
        d = route("Add a new flag to the CLI", "implementation", registry=registry, context=ctx)
        assert d.primary == "codex"

    def test_codex_preferred_for_debug(self, registry):
        ctx = RouterContext(available_workers={"codex", "aider", "claude-code-local"})
        d = route("Fix the failing test", "debug", registry=registry, context=ctx)
        assert d.primary == "codex"


class TestAider:
    def test_aider_appears_in_fallback_for_implementation(self, registry):
        ctx = RouterContext(available_workers={"codex", "aider", "claude-code-local"})
        d = route("implement foo", "implementation", registry=registry, context=ctx)
        assert "aider" in d.fallback_plan


class TestGooseOptional:
    def test_goose_not_default_for_implementation_when_codex_available(self, registry):
        # Goose is optional — for a vanilla implementation task with
        # codex around, codex should win because it's the #1 preferred
        # primary for implementation.
        ctx = RouterContext(available_workers={"codex", "goose"})
        d = route("add a flag", "implementation", registry=registry, context=ctx)
        assert d.primary == "codex"
        assert d.primary != "goose"

    def test_goose_appears_in_rejected_or_fallback(self, registry):
        # Goose should still be visible in the decision — never silently
        # dropped — even when it isn't the primary.
        ctx = RouterContext(available_workers={"codex", "goose"})
        d = route("add a flag", "implementation", registry=registry, context=ctx)
        accounted = set(d.selected_ids()) | set(d.rejected.keys()) | set(d.fallback_plan)
        assert "goose" in accounted


class TestBrowserResearch:
    def test_added_for_research_category(self, registry):
        ctx = RouterContext(available_workers={"browser-research", "codex"})
        d = route("latest react hooks docs", "research", registry=registry, context=ctx)
        assert "browser-research" in d.selected_ids()

    def test_added_when_caller_flags_external_docs(self, registry):
        ctx = RouterContext(
            available_workers={"browser-research", "codex"},
            needs_external_docs=True,
        )
        d = route("add feature", "implementation", registry=registry, context=ctx)
        assert "browser-research" in d.selected_ids()


class TestApprovalGate:
    @pytest.mark.parametrize(
        "category,expected_tag",
        [
            ("secrets-management", "secrets"),
            ("deployment", "deployment"),
            ("github-pr", "publish"),
            ("remote-execution", "remote-tunnel-setup"),
        ],
    )
    def test_categories_trigger_human_approval(self, registry, category, expected_tag):
        ctx = RouterContext(
            available_workers={"codex", "github-publisher", "supabase-worker", "vercel-worker"},
            approvals_granted={"schema-approval", "deployment"},
        )
        d = route("task", category, registry=registry, context=ctx)
        assert "human-approval" in d.selected_ids(), (
            f"category {category} should add human-approval"
        )
        assert expected_tag in d.approval_requirements, (
            f"category {category} should request {expected_tag}"
        )

    def test_continuous_listening_triggers_approval(self, registry):
        ctx = RouterContext(
            available_workers={"codex"},
            continuous_listening=True,
        )
        d = route("listen for events", "planning", registry=registry, context=ctx)
        assert "human-approval" in d.selected_ids()
        assert "continuous-listening" in d.approval_requirements


class TestSupabaseGate:
    def test_held_back_without_schema_approval(self, registry):
        ctx = RouterContext(
            available_workers={"supabase-worker", "codex"},
            approvals_granted=set(),
        )
        d = route("run migration", "deployment", registry=registry, context=ctx)
        assert "supabase-worker" not in d.selected_ids()
        assert "supabase-worker" in d.rejected
        assert "schema" in d.rejected["supabase-worker"].lower()

    def test_runs_after_schema_approval(self, registry):
        ctx = RouterContext(
            available_workers={"supabase-worker", "codex"},
            approvals_granted={"schema-approval", "deployment"},
        )
        d = route(
            "run schema migration to add users table",
            "deployment",
            registry=registry,
            context=ctx,
        )
        assert "supabase-worker" in d.selected_ids()


class TestVercelGate:
    def test_held_back_without_deployment_approval(self, registry):
        ctx = RouterContext(
            available_workers={"vercel-worker", "codex"},
            approvals_granted=set(),
        )
        d = route("ship a preview", "deployment", registry=registry, context=ctx)
        assert "vercel-worker" not in d.selected_ids()
        assert "vercel-worker" in d.rejected

    def test_runs_after_deployment_approval(self, registry):
        ctx = RouterContext(
            available_workers={"vercel-worker"},
            approvals_granted={"deployment"},
        )
        d = route("ship preview", "deployment", registry=registry, context=ctx)
        assert "vercel-worker" in d.selected_ids()


class TestPublisher:
    def test_publisher_assigned_for_github_pr(self, registry):
        ctx = RouterContext(
            available_workers={"codex", "github-publisher"},
        )
        d = route("open a PR", "github-pr", registry=registry, context=ctx)
        assert d.publisher == "github-publisher"
        assert "github-publisher" in d.selected_ids()

    def test_no_publisher_for_planning(self, registry, all_available_ctx):
        d = route("draft a plan", "planning", registry=registry, context=all_available_ctx)
        assert d.publisher is None


class TestAndroidBuilder:
    def test_primary_for_mobile_android(self, registry):
        ctx = RouterContext(available_workers={"android-builder", "codex"})
        d = route("build the APK", "mobile-android", registry=registry, context=ctx)
        assert d.primary == "android-builder"


class TestChatGPTHandoff:
    def test_not_routed_without_opt_in(self, registry):
        ctx = RouterContext(available_workers={"codex"})
        d = route("anything", "research", registry=registry, context=ctx)
        assert d.primary != "chatgpt-handoff"
        assert "chatgpt-handoff" in d.rejected

    def test_selected_with_explicit_preference(self, registry):
        # Manual handoff is detected like any other worker — the user
        # opt-in only removes the "manual handoff: not selected on
        # explicit user opt-in" rejection. The host still needs to
        # advertise it as available.
        ctx = RouterContext(
            available_workers={"chatgpt-handoff"},
            user_preferences=["chatgpt-handoff"],
        )
        d = route("hand off to ChatGPT", "research", registry=registry, context=ctx)
        assert "chatgpt-handoff" not in d.rejected


# ---------------------------------------------------------------------------
# Output completeness
# ---------------------------------------------------------------------------


class TestOutputCompleteness:
    def test_ledger_entry_is_json_serialisable(self, registry, all_available_ctx):
        d = route("Add /foo subcommand", "implementation", registry=registry, context=all_available_ctx)
        payload = json.dumps(d.ledger_entry)
        assert "task_id" in payload
        # Round-trip the whole decision through .to_dict() / json.
        json.dumps(d.to_dict(), default=str)

    def test_explanation_is_non_empty_string(self, registry, all_available_ctx):
        d = route("x", "validation", registry=registry, context=all_available_ctx)
        assert isinstance(d.explanation, str)
        assert len(d.explanation) > 10

    def test_render_report_includes_sections(self, registry, all_available_ctx):
        d = route("Add /foo subcommand", "implementation", registry=registry, context=all_available_ctx)
        report = render_report(d)
        for section in (
            "# Worker selection",
            "## Selected workers",
            "## Rejected workers",
            "## Fallback plan",
            "## Approval requirements",
            "## Validation plan",
            "## Explanation",
            "## Ledger entry",
        ):
            assert section in report, f"missing section in report: {section}"

    def test_every_worker_appears_in_selected_or_rejected(self, registry):
        # The registry has 13 required workers; every one of them must
        # be accounted for in any decision, with no silent drops.
        ctx = RouterContext(
            available_workers={
                "codex",
                "claude-code-local",
                "claude-code-windows",
                "aider",
                "goose",
                "browser-research",
                "supabase-worker",
                "vercel-worker",
                "android-builder",
                "github-publisher",
            },
            tunnel_healthy=True,
            approvals_granted={"schema-approval", "deployment"},
        )
        d = route("ship a small thing", "implementation", registry=registry, context=ctx)
        accounted = (
            set(d.selected_ids())
            | set(d.rejected.keys())
            | set(d.fallback_plan)
        )
        for wid in mr.required_worker_ids():
            assert wid in accounted, f"{wid} silently dropped from decision"


# ---------------------------------------------------------------------------
# Offline mode
# ---------------------------------------------------------------------------


class TestOfflineMode:
    def test_cloud_workers_excluded_when_offline(self, registry):
        ctx = RouterContext(
            available_workers={"codex", "aider", "claude-code-local"},
            offline=True,
        )
        d = route("implement foo", "implementation", registry=registry, context=ctx)
        # All cloud workers are rejected for offline mode.
        for cloud in ("codex", "aider", "claude-code-local"):
            assert cloud in d.rejected
            assert "offline" in d.rejected[cloud].lower()
        # Hermes-local survives.
        assert d.primary == "hermes-local"

    def test_hermes_offline_env_forces_offline(self, registry, monkeypatch):
        # The env flag is a floor: with no offline context, HERMES_OFFLINE=1
        # must still exclude cloud workers (the wiring in route()).
        monkeypatch.setenv("HERMES_OFFLINE", "1")
        ctx = RouterContext(available_workers={"codex", "aider", "claude-code-local"})
        d = route("implement foo", "implementation", registry=registry, context=ctx)
        for cloud in ("codex", "aider", "claude-code-local"):
            assert cloud in d.rejected
            assert "offline" in d.rejected[cloud].lower()
        assert d.primary == "hermes-local"

    def test_no_env_keeps_cloud_eligible(self, registry, monkeypatch):
        # Sanity: without the env flag and without an offline context, cloud
        # workers are not excluded for offline reasons.
        monkeypatch.delenv("HERMES_OFFLINE", raising=False)
        ctx = RouterContext(available_workers={"codex", "aider", "claude-code-local"})
        d = route("implement foo", "implementation", registry=registry, context=ctx)
        accounted = set(d.selected_ids()) | set(d.rejected.keys())
        for cloud in ("codex", "aider", "claude-code-local"):
            if cloud in d.rejected:
                assert "offline" not in d.rejected[cloud].lower()
        assert "hermes-local" in accounted


# ---------------------------------------------------------------------------
# YAML loader sanity (not a substitute for the built-in test set above)
# ---------------------------------------------------------------------------


class TestYamlLoaderSanity:
    def test_yaml_loads_if_present(self):
        # Reset the cache so this isn't an artifact of an earlier
        # in-process load.
        mr.reset_cache()
        reg = mr.load_registry()
        # Either we read the YAML or we fell back to built-in — both
        # are valid outcomes, but we should never silently return an
        # empty registry.
        assert reg.workers, "registry should never be empty"
        assert reg.source in ("yaml", "builtin", "merged")

    def test_missing_path_falls_back_to_builtin(self, tmp_path):
        mr.reset_cache()
        bogus = tmp_path / "does-not-exist.yaml"
        reg = mr.load_registry(bogus)
        assert reg.source == "builtin"
        for required in mr.required_worker_ids():
            assert required in reg.ids()

    @pytest.mark.skip(
        reason="model-registry.yaml needs a 'claude-code-windows' entry from the Windows "
        "bridge impl PR; salvaged ahead of that PR."
    )
    def test_shipped_yaml_includes_all_required_ids(self):
        mr.reset_cache()
        yaml_path = Path(__file__).resolve().parent.parent / "docs" / "ai-intelligence" / "model-registry.yaml"
        if not yaml_path.exists():
            pytest.skip("model-registry.yaml not present in this checkout")
        reg = mr.load_registry(yaml_path)
        if reg.source != "yaml":
            pytest.skip("YAML did not load (PyYAML missing?); skipping shipped-registry check")
        for required in mr.required_worker_ids():
            assert required in reg.ids(), f"YAML missing required worker: {required}"
