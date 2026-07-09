"""Tests for hermes_cli.jarvis_prime.seat_portfolio — owner-gated seat swaps.

The seat portfolio is proposal-only: it reports the roster honestly (no
measured evidence ⇒ says so) and queues owner-gated model-swap proposals
without ever touching a profile's config.yaml.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.seat_portfolio import (
    append_seat_proposal,
    build_seat_swap_proposal,
    seat_report,
)
from hermes_cli.orchestrator_trio import FULL_ROSTER, install_trio


@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    """Isolate Path.home() / HERMES_HOME / scorecard store in tmp_path.

    Mirrors tests/hermes_cli/test_orchestrator_trio.py, plus pins the
    scorecard default path (a module-import-time constant) into tmp_path so
    a developer's real ~/.hermes never leaks into these tests.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    default_home = tmp_path / ".hermes"
    default_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(default_home))

    from hermes_cli.jarvis_prime import model_scorecard

    monkeypatch.setattr(
        model_scorecard,
        "DEFAULT_SCORECARD_PATH",
        default_home / "jarvis_prime" / "model_scorecards.jsonl",
    )
    return tmp_path


def _proposals_path(tmp_path: Path) -> Path:
    return tmp_path / ".hermes" / "jarvis_prime" / "proposals.jsonl"


def _other_seat_ref(seat: str) -> str:
    """A catalog ref guaranteed to exist: another roster seat's pin."""
    return next(r.catalog_ref for r in FULL_ROSTER if r.profile != seat)


class TestSeatReport:
    def test_empty_home_reports_honestly(self, profile_env):
        report = seat_report()

        assert set(report["seats"]) == {r.profile for r in FULL_ROSTER}
        assert report["scorecards_recorded"] == 0
        for role in FULL_ROSTER:
            seat = report["seats"][role.profile]
            assert seat["installed"] is False
            assert seat["pinned_model"] is None
            assert seat["preset_model"] == role.model
            cards = seat["scorecards"]
            assert cards["measured"] is False
            assert cards["samples"] == 0
            assert cards["mean_score"] is None
            # Candidates come from the live catalog — don't pin their exact
            # contents, but the seat's own pinned entry is never a candidate.
            assert isinstance(seat["candidates"], list)
            assert role.catalog_ref not in seat["candidates"]

    def test_report_after_extended_install(self, profile_env):
        install_trio(extended=True)

        report = seat_report()
        for role in FULL_ROSTER:
            seat = report["seats"][role.profile]
            assert seat["installed"] is True
            assert seat["pinned_model"] == role.model

    def test_report_reflects_measured_scorecards(self, profile_env):
        from hermes_cli.jarvis_prime.model_scorecard import (
            ModelScorecard,
            ScorecardBook,
        )

        book = ScorecardBook(path=profile_env / "cards.jsonl")
        book.record(
            ModelScorecard(
                model="meituan/longcat-2.0",
                provider="openrouter",
                task_type="coding_build",
                tests_passed=5,
            ),
            persist=False,
        )

        report = seat_report(book=book)
        cards = report["seats"]["executor"]["scorecards"]
        assert cards["measured"] is True
        assert cards["samples"] == 1
        assert cards["mean_score"] is not None
        assert report["scorecards_recorded"] == 1


class TestBuildProposal:
    def test_unknown_seat_raises(self, profile_env):
        with pytest.raises(ValueError, match="unknown seat"):
            build_seat_swap_proposal("not-a-seat", _other_seat_ref("executor"))

    def test_unknown_candidate_ref_raises(self, profile_env):
        with pytest.raises(ValueError, match="unknown candidate ref"):
            build_seat_swap_proposal("executor", "nope/not-a-model")

    def test_proposal_shape_is_owner_gated_with_rollback(self, profile_env):
        install_trio()
        candidate_ref = _other_seat_ref("executor")

        proposal = build_seat_swap_proposal("executor", candidate_ref)

        assert proposal["requires_owner_approval"] is True
        assert proposal["risk_class"] == "RC2"
        assert proposal["kind"] == "routing_rule_update"
        assert proposal["status"] == "proposed"
        assert proposal["target_path"].endswith("config.yaml")
        assert "executor" in proposal["target_path"]
        # Rollback re-pins the current model.
        assert "meituan/longcat-2.0" in proposal["rollback"]
        assert proposal["seat_swap"]["current_model"] == "meituan/longcat-2.0"
        assert proposal["seat_swap"]["candidate_ref"] == candidate_ref

    def test_no_scorecards_rationale_is_honest(self, profile_env):
        proposal = build_seat_swap_proposal("critic", _other_seat_ref("critic"))

        assert "no measured scorecards" in proposal["rationale"]
        assert "do not approve without a bench run" in proposal["rationale"]
        assert proposal["seat_swap"]["scorecards"]["measured"] is False

    def test_measured_scorecards_are_cited(self, profile_env):
        from hermes_cli.jarvis_prime.model_scorecard import (
            ModelScorecard,
            ScorecardBook,
        )

        book = ScorecardBook(path=profile_env / "cards.jsonl")
        book.record(
            ModelScorecard(
                model="moonshotai/kimi-k2",
                provider="openrouter",
                task_type="research",
                tests_passed=3,
            ),
            persist=False,
        )

        proposal = build_seat_swap_proposal(
            "executor", "openrouter/kimi-k2", book=book
        )

        assert "Measured evidence" in proposal["rationale"]
        assert "no measured scorecards" not in proposal["rationale"]
        assert proposal["seat_swap"]["scorecards"]["samples"] == 1
        assert proposal["evidence"][0]["kind"] == "scorecard"

    def test_never_touches_profile_config(self, profile_env):
        install_trio(extended=True)
        config_path = (
            profile_env / ".hermes" / "profiles" / "executor" / "config.yaml"
        )
        before = config_path.read_bytes()

        build_seat_swap_proposal("executor", _other_seat_ref("executor"))

        assert config_path.read_bytes() == before
        # Building a proposal also never persists it by itself.
        assert not _proposals_path(profile_env).exists()


class TestAppendAndCli:
    def test_append_writes_one_jsonl_line_with_0600(self, profile_env):
        proposal = build_seat_swap_proposal("executor", _other_seat_ref("executor"))

        assert append_seat_proposal(proposal) is True

        path = _proposals_path(profile_env)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        stored = json.loads(lines[0])
        assert stored["requires_owner_approval"] is True
        assert stored["rollback"] == proposal["rollback"]
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_cli_propose_dry_run_writes_nothing(self, profile_env, capsys):
        from hermes_cli.jarvis_prime.__main__ import main

        rc = main(
            ["seats", "propose", "executor", _other_seat_ref("executor"), "--dry-run"]
        )

        assert rc == 0
        assert not _proposals_path(profile_env).exists()
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_cli_propose_appends(self, profile_env, capsys):
        from hermes_cli.jarvis_prime.__main__ import main

        rc = main(["seats", "propose", "executor", _other_seat_ref("executor")])

        assert rc == 0
        path = _proposals_path(profile_env)
        assert len(path.read_text(encoding="utf-8").splitlines()) == 1
        assert "queued for owner approval" in capsys.readouterr().out

    def test_cli_propose_rejects_unknown_seat(self, profile_env, capsys):
        from hermes_cli.jarvis_prime.__main__ import main

        rc = main(["seats", "propose", "nope", _other_seat_ref("executor")])

        assert rc == 2
        assert "unknown seat" in capsys.readouterr().err
        assert not _proposals_path(profile_env).exists()

    def test_cli_report_json(self, profile_env, capsys):
        from hermes_cli.jarvis_prime.__main__ import main

        rc = main(["seats", "report", "--json"])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload["seats"]) == {r.profile for r in FULL_ROSTER}
