"""Tests for the orchestrator's keyword-based model router.

The router is an *explain-only* surface in Phase 16 — it tells callers
which profile a prompt would resolve to without actually flipping the
live model. Tests pin keyword matching, fallback behaviour, and the
``/model-router explain`` slash dispatch.
"""

from __future__ import annotations

import pytest

from hermes_cli import orchestrator as orch


# ── pure function: model_router_explain ───────────────────────────────


class TestRouterDecisions:
    @pytest.mark.parametrize(
        "prompt,expected_route",
        [
            ("please review this PR", "reviewer-profile"),
            ("help me debug a flaky test", "debug-profile"),
            ("refactor the auth module", "builder-profile"),
            ("design a new ingestion service", "architect-profile"),
            ("plan the migration steps", "planner-profile"),
            ("write unit tests for foo", "tester-profile"),
            ("update the docs", "writer-profile"),
        ],
    )
    def test_keyword_routes(self, prompt: str, expected_route: str) -> None:
        decision = orch.model_router_explain(prompt)
        assert decision["route"] == expected_route
        assert isinstance(decision["rationale"], str)
        assert decision["rationale"]

    def test_default_when_no_keyword_matches(self) -> None:
        decision = orch.model_router_explain("the sky is blue")
        assert decision["route"] == "default-profile"
        assert decision["matched_keywords"] == []
        assert "no routing keywords matched" in decision["rationale"]

    def test_empty_prompt_falls_back_to_default(self) -> None:
        decision = orch.model_router_explain("")
        assert decision["route"] == "default-profile"

    def test_case_insensitive(self) -> None:
        a = orch.model_router_explain("REVIEW this code")
        b = orch.model_router_explain("review this code")
        assert a["route"] == b["route"]

    def test_first_matching_keyword_wins_for_route(self) -> None:
        # Both "review" and "test" would match — the rule list is
        # ordered, so the first wins for ``route``.
        decision = orch.model_router_explain("review the tests")
        assert decision["route"] == "reviewer-profile"
        # ``matched_keywords`` still records every matching route.
        assert "reviewer-profile" in decision["matched_keywords"]
        assert "tester-profile" in decision["matched_keywords"]

    def test_returns_dict_with_documented_keys(self) -> None:
        decision = orch.model_router_explain("plan something")
        assert set(decision.keys()) == {"route", "rationale", "matched_keywords"}


# ── slash dispatch: run_model_router ──────────────────────────────────


class TestRouterSlashCommand:
    def test_help_when_empty(self) -> None:
        assert "Usage:" in orch.run_model_router("")

    def test_help_when_help_flag(self) -> None:
        for flag in ("-h", "--help", "?", "help"):
            assert "Usage:" in orch.run_model_router(flag)

    def test_explain_renders_route_line(self) -> None:
        out = orch.run_model_router("explain refactor the parser")
        assert "builder-profile" in out
        assert "rationale:" in out

    def test_explain_with_no_prompt_returns_help(self) -> None:
        out = orch.run_model_router("explain")
        assert "Usage:" in out

    def test_unknown_subcommand_returns_error(self) -> None:
        out = orch.run_model_router("decide foo")
        assert "unknown subcommand" in out

    def test_malformed_quoting_falls_back_to_error(self) -> None:
        out = orch.run_model_router('explain "unterminated')
        # shlex.split should raise ValueError; the dispatcher should
        # surface it without crashing.
        assert "/model-router" in out
