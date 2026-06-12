"""Tests for :mod:`hermes_cli.decision_ledger`.

The module backs the Phase 05 explainability work: every important
Hermes decision must produce a structured ledger that survives parse →
write → read round-trips and refuses to persist when sections are
missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermes_cli import decision_ledger as dl


# Most tests need a fully-populated ledger. Keeping the builder local
# (rather than a fixture) makes each test's preconditions visible in
# the test body.

def _filled_ledger(**overrides: str) -> dl.DecisionLedger:
    defaults: dict[str, str] = {
        "decision": "Switch the default delegation model to claude-sonnet-4-6.",
        "plain_english_summary": (
            "We are changing which AI model handles multi-file edits, "
            "so they run a bit faster and a bit cheaper without losing quality."
        ),
        "context": (
            "User reported `hermes delegate` was slow on a 12-file refactor. "
            "Triggered from session 20260523_182600_d4f5a6."
        ),
        "evidence_reviewed": (
            "- Files: agent/prompt_builder.py:142-180\n"
            "- Commands: `pytest tests/agent/test_delegation.py -q` (passed)\n"
            "- Docs: docs/orchestration/orchestrator-command-reference.md (section 'Delegation')\n"
            "- Web sources: (none consulted)\n"
            "- Prior memory: session 20260520_141200_a1b2c3 ledger 0003.\n"
            "- Gaps: did not benchmark on Windows."
        ),
        "options_considered": (
            "### Option A — sonnet\n"
            "Pros: cheaper than opus; long-context handling.\n"
            "Cons: occasional regressions on complex refactors.\n"
            "Risk: minor — fallback covers it.\n"
            "Validation: rerun the 12-file refactor.\n"
            "\n"
            "### Option B — keep opus\n"
            "Pros: best quality.\n"
            "Cons: 3x cost.\n"
            "Risk: budget overruns on cron jobs.\n"
            "Validation: monthly invoice review."
        ),
        "selected_model_worker": "delegation toolset -> anthropic/claude-sonnet-4-6",
        "why_this_choice": (
            "Sonnet matches Opus on the refactor benchmark within 5% while "
            "costing ~30% as much, and the fallback chain is already wired."
        ),
        "rejected_alternatives": (
            "Opus: too expensive for the cron path. Haiku: too small for "
            "long-context refactors. Fallback: openai/gpt-5-mini via OpenRouter."
        ),
        "cost_latency_quality_tradeoff": (
            "Estimated $0.40/turn; sub-30s/turn latency; quality acceptable "
            "for non-prod code path."
        ),
        "validation_plan": (
            "- Commands: `pytest tests/agent/test_delegation.py -q`\n"
            "- Manual checks: open the dashboard, confirm the new model name appears.\n"
            "- Success criteria: tests pass; runtime within 10% of baseline."
        ),
        "approval_required": "no — proceed; change is reversible and behind a flag.",
        "final_decision": "Option A — switch to sonnet.",
        "confidence": "medium — benchmark covers 90% of expected refactor shapes.",
        "open_risks": (
            "- Windows runner not yet exercised; mitigation: CI matrix run before release.\n"
            "- Long-context edits beyond 100k tokens not benchmarked; accept this for now."
        ),
        "rollback_plan": (
            "`git revert <sha>`; no migration state. Cron jobs auto-pick the "
            "new default within an hour after the revert."
        ),
    }
    defaults.update(overrides)
    return dl.DecisionLedger(**defaults)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchema:
    def test_section_headings_are_the_documented_15(self) -> None:
        # The Judge, curator, and /decisions slash command all parse by
        # heading. If this set changes, those consumers must be updated.
        assert dl.SECTION_HEADINGS == (
            "Decision",
            "Plain English Summary",
            "Context",
            "Evidence Reviewed",
            "Options Considered",
            "Selected Model / Worker",
            "Why This Choice",
            "Rejected Alternatives",
            "Cost / Latency / Quality Tradeoff",
            "Validation Plan",
            "Approval Required",
            "Final Decision",
            "Confidence",
            "Open Risks",
            "Rollback Plan",
        )

    def test_every_heading_maps_to_a_dataclass_field(self) -> None:
        ledger = dl.DecisionLedger()
        for heading in dl.SECTION_HEADINGS:
            # section() raises KeyError on typos, so calling it for
            # every heading is the round-trip check.
            assert ledger.section(heading) == ""

    def test_section_helper_rejects_typos(self) -> None:
        ledger = dl.DecisionLedger()
        with pytest.raises(KeyError):
            ledger.section("Selected Model")  # missing the slash form


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------


class TestRenderTemplate:
    def test_template_has_title_and_every_heading(self) -> None:
        text = dl.render_template()
        assert text.startswith(f"# {dl.TITLE}\n")
        for heading in dl.SECTION_HEADINGS:
            assert f"\n## {heading}\n" in text

    def test_template_sections_appear_in_canonical_order(self) -> None:
        text = dl.render_template()
        positions = [text.index(f"## {h}") for h in dl.SECTION_HEADINGS]
        assert positions == sorted(positions)

    def test_blank_template_parses_to_an_incomplete_ledger(self) -> None:
        text = dl.render_template()
        ledger = dl.parse_markdown(text)
        # Placeholders are HTML comments and get stripped; nothing is filled.
        assert ledger.is_complete() is False
        assert set(ledger.missing_sections()) == set(dl.SECTION_HEADINGS)

    def test_prefill_overrides_named_sections_only(self) -> None:
        text = dl.render_template({"Decision": "Adopt the new ledger schema."})
        ledger = dl.parse_markdown(text)
        assert ledger.decision == "Adopt the new ledger schema."
        # Other sections still empty (placeholders are stripped).
        assert ledger.plain_english_summary == ""

    def test_prefill_rejects_unknown_headings(self) -> None:
        with pytest.raises(KeyError):
            dl.render_template({"Bogus Section": "nope"})


# ---------------------------------------------------------------------------
# parse_markdown
# ---------------------------------------------------------------------------


class TestParseMarkdown:
    def test_round_trip_identity_for_filled_ledger(self) -> None:
        original = _filled_ledger()
        text = original.to_markdown()
        parsed = dl.parse_markdown(text)
        for heading in dl.SECTION_HEADINGS:
            assert parsed.section(heading) == original.section(heading), heading

    def test_unknown_heading_is_an_error(self) -> None:
        text = (
            "# Decision Ledger\n\n"
            "## Decision\nAdopt new schema.\n\n"
            "## Bogus\nshould not parse\n"
        )
        with pytest.raises(dl.LedgerValidationError) as ei:
            dl.parse_markdown(text)
        assert "Bogus" in str(ei.value)

    def test_duplicate_heading_is_an_error(self) -> None:
        text = (
            "# Decision Ledger\n\n"
            "## Decision\nFirst.\n\n"
            "## Decision\nSecond.\n"
        )
        with pytest.raises(dl.LedgerValidationError) as ei:
            dl.parse_markdown(text)
        assert "duplicate" in str(ei.value).lower()

    def test_missing_headings_yield_empty_fields_not_errors(self) -> None:
        # Only one section present — parse succeeds; validate() catches it.
        text = "# Decision Ledger\n\n## Decision\nDo the thing.\n"
        ledger = dl.parse_markdown(text)
        assert ledger.decision == "Do the thing."
        assert ledger.context == ""
        with pytest.raises(dl.LedgerValidationError):
            ledger.validate()

    def test_custom_title_is_preserved(self) -> None:
        text = "# Switch Model — Decision Ledger\n\n## Decision\nDo it.\n"
        ledger = dl.parse_markdown(text)
        assert ledger.title == "Switch Model — Decision Ledger"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_filled_ledger_validates(self) -> None:
        _filled_ledger().validate()  # no exception

    def test_blank_ledger_lists_every_section_as_missing(self) -> None:
        ledger = dl.DecisionLedger()
        assert set(ledger.missing_sections()) == set(dl.SECTION_HEADINGS)

    def test_bare_na_does_not_satisfy_a_section(self) -> None:
        ledger = _filled_ledger(rollback_plan="N/A")
        assert "Rollback Plan" in ledger.missing_sections()

    def test_na_with_justification_satisfies_a_section(self) -> None:
        ledger = _filled_ledger(
            rollback_plan="N/A — read-only command; no state to undo."
        )
        assert "Rollback Plan" not in ledger.missing_sections()
        ledger.validate()

    def test_html_comments_alone_count_as_empty(self) -> None:
        # The template placeholders are HTML comments — they must not
        # masquerade as filled content.
        ledger = _filled_ledger(open_risks="<!-- TODO -->")
        assert "Open Risks" in ledger.missing_sections()

    @pytest.mark.parametrize("confidence", ["high", "Medium", "low — only one repo tested"])
    def test_confidence_starting_with_known_level_passes(self, confidence: str) -> None:
        _filled_ledger(confidence=confidence).validate()

    def test_confidence_with_unknown_level_fails(self) -> None:
        ledger = _filled_ledger(confidence="extremely confident")
        with pytest.raises(dl.LedgerValidationError) as ei:
            ledger.validate()
        assert "Confidence" in str(ei.value)

    @pytest.mark.parametrize("approval", [
        "no - proceed",
        "yes — Jeremiah must sign off before push",
        "defer — waiting on user reply",
    ])
    def test_approval_with_recognised_verdict_passes(self, approval: str) -> None:
        _filled_ledger(approval_required=approval).validate()

    def test_approval_with_unknown_verdict_fails(self) -> None:
        ledger = _filled_ledger(approval_required="maybe? ask later")
        with pytest.raises(dl.LedgerValidationError):
            ledger.validate()

    def test_validation_error_collects_all_problems(self) -> None:
        ledger = _filled_ledger(
            confidence="extremely",
            approval_required="maybe",
            rollback_plan="",
        )
        with pytest.raises(dl.LedgerValidationError) as ei:
            ledger.validate()
        assert len(ei.value.problems) >= 2
        joined = "; ".join(ei.value.problems)
        assert "Rollback Plan" in joined  # missing section
        assert "Confidence" in joined or "extremely" in joined


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    @pytest.mark.parametrize("text,expected", [
        ("Switch the delegation model", "switch-the-delegation-model"),
        ("  Already Kebab-case  ", "already-kebab-case"),
        ("Use claude/sonnet-4-6 for code", "use-claude-sonnet-4-6-for-code"),
        ("Multiple   spaces!!!", "multiple-spaces"),
        ("Café — naïve façade", "cafe-naive-facade"),
    ])
    def test_canonical_slugs(self, text: str, expected: str) -> None:
        assert dl.slugify(text) == expected

    def test_empty_input_returns_default(self) -> None:
        assert dl.slugify("") == "decision"
        assert dl.slugify("!!!!") == "decision"

    def test_only_first_line_is_used(self) -> None:
        slug = dl.slugify("First line decision\nSecond line should not appear")
        assert slug == "first-line-decision"
        assert "second" not in slug

    def test_long_input_is_truncated_at_word_boundary(self) -> None:
        long = "x" * 200
        s = dl.slugify(long, max_len=20)
        assert len(s) <= 20


# ---------------------------------------------------------------------------
# Filesystem I/O
# ---------------------------------------------------------------------------


class TestWriteAndRead:
    def test_write_creates_session_directory_and_file(self) -> None:
        ledger = _filled_ledger()
        path = dl.write_ledger(ledger, session_id="20260523_182600_d4f5a6")
        assert path.is_file()
        # Layout: HERMES_HOME/decisions/<sid>/<seq>-<slug>.md
        assert path.parent.parent == dl.decisions_dir()
        assert path.parent.name == "20260523_182600_d4f5a6"
        assert path.name.startswith("0001-")
        assert path.suffix == ".md"

    def test_write_populates_metadata_on_the_ledger(self) -> None:
        ledger = _filled_ledger()
        path = dl.write_ledger(ledger, session_id="sess")
        assert ledger.session_id == "sess"
        assert ledger.seq == 1
        assert ledger.slug.startswith("switch-the-default-delegation-model")
        assert ledger.path == path
        assert ledger.created_at > 0

    def test_write_refuses_incomplete_ledger_by_default(self) -> None:
        incomplete = dl.DecisionLedger(decision="missing the rest")
        with pytest.raises(dl.LedgerValidationError):
            dl.write_ledger(incomplete, session_id="sess")

    def test_write_can_skip_validation(self) -> None:
        wip = dl.DecisionLedger(decision="work in progress")
        path = dl.write_ledger(
            wip, session_id="sess", validate=False, slug="wip"
        )
        assert path.is_file()
        # Content round-trips even without validation.
        parsed = dl.parse_markdown(path.read_text(encoding="utf-8"))
        assert parsed.decision == "work in progress"

    def test_write_auto_increments_sequence(self) -> None:
        for expected_seq in (1, 2, 3):
            ledger = _filled_ledger(decision=f"Decision number {expected_seq}.")
            path = dl.write_ledger(ledger, session_id="sess")
            assert path.name.startswith(f"{expected_seq:04d}-")
            assert ledger.seq == expected_seq

    def test_write_refuses_to_clobber_unless_overwrite(self) -> None:
        ledger = _filled_ledger()
        path = dl.write_ledger(ledger, session_id="sess", slug="pinned", seq=7)
        assert path.name == "0007-pinned.md"
        # Same coordinates again — must refuse.
        with pytest.raises(dl.LedgerError):
            dl.write_ledger(ledger, session_id="sess", slug="pinned", seq=7)
        # overwrite=True lets the second write succeed.
        dl.write_ledger(
            _filled_ledger(decision="overwritten."),
            session_id="sess",
            slug="pinned",
            seq=7,
            overwrite=True,
        )
        rewritten = dl.read_ledger(path)
        assert rewritten.decision == "overwritten."

    def test_read_round_trips_metadata(self) -> None:
        original = _filled_ledger()
        path = dl.write_ledger(original, session_id="my-session")
        back = dl.read_ledger(path)
        assert back.session_id == "my-session"
        assert back.seq == original.seq
        assert back.slug == original.slug
        assert back.decision == original.decision
        assert back.confidence == original.confidence

    def test_read_unknown_path_raises(self) -> None:
        with pytest.raises(dl.LedgerNotFoundError):
            dl.read_ledger(dl.decisions_dir() / "nope" / "0001-nope.md")

    def test_session_id_rejects_path_traversal(self) -> None:
        with pytest.raises(dl.LedgerError):
            dl.session_dir("../escape")
        with pytest.raises(dl.LedgerError):
            dl.write_ledger(_filled_ledger(), session_id="../escape")

    def test_session_id_rejects_empty_string(self) -> None:
        with pytest.raises(dl.LedgerError):
            dl.write_ledger(_filled_ledger(), session_id="")


class TestListLedgers:
    def _write(self, sid: str, decision: str) -> Path:
        return dl.write_ledger(
            _filled_ledger(decision=decision), session_id=sid
        )

    def test_list_for_unknown_session_is_empty(self) -> None:
        assert dl.list_ledgers("never-existed") == []

    def test_list_for_session_returns_sequence_order(self) -> None:
        self._write("s1", "First decision.")
        self._write("s1", "Second decision.")
        self._write("s1", "Third decision.")
        names = [p.name for p in dl.list_ledgers("s1")]
        assert names == [
            "0001-first-decision.md",
            "0002-second-decision.md",
            "0003-third-decision.md",
        ]

    def test_list_all_groups_by_session(self) -> None:
        self._write("alpha", "A1")
        self._write("beta", "B1")
        self._write("alpha", "A2")
        paths = dl.list_ledgers()
        # Both sessions appear; within each session, sequence order holds.
        parents = [p.parent.name for p in paths]
        assert sorted(set(parents)) == ["alpha", "beta"]
        alpha_names = [p.name for p in paths if p.parent.name == "alpha"]
        assert alpha_names == sorted(alpha_names)

    def test_unrecognised_files_are_ignored(self) -> None:
        self._write("s1", "Real decision.")
        # Drop a stray file in the session directory; it must not appear
        # in list_ledgers() output and must not affect next_seq.
        stray = dl.session_dir("s1") / "hand-edited-notes.md"
        stray.write_text("scratch\n", encoding="utf-8")
        ledgers = dl.list_ledgers("s1")
        assert stray not in ledgers
        # next_seq counts only NNNN-prefixed files, so the second real
        # ledger lands at seq 2.
        next_path = self._write("s1", "Next decision.")
        assert next_path.name.startswith("0002-")


# ---------------------------------------------------------------------------
# Template file on disk
# ---------------------------------------------------------------------------


class TestOnDiskTemplate:
    """The on-disk template file ships with the repo and must stay in sync."""

    def _template_path(self) -> Path:
        # Walk up from this test file to the repo root; the template
        # lives at templates/orchestration/decision-ledger-template.md.
        repo_root = Path(__file__).resolve().parent.parent
        return repo_root / "templates" / "orchestration" / "decision-ledger-template.md"

    def test_template_file_exists(self) -> None:
        assert self._template_path().is_file(), (
            "templates/orchestration/decision-ledger-template.md is missing — "
            "Phase 05 expects the blank ledger template to ship in the repo."
        )

    def test_template_file_contains_every_section(self) -> None:
        text = self._template_path().read_text(encoding="utf-8")
        for heading in dl.SECTION_HEADINGS:
            assert f"## {heading}" in text, (
                f"on-disk template is missing the '{heading}' section; "
                "in-process render_template() and the file must agree."
            )

    def test_template_file_parses_to_blank_ledger(self) -> None:
        text = self._template_path().read_text(encoding="utf-8")
        ledger = dl.parse_markdown(text)
        # Every section is HTML-comment placeholders only.
        assert ledger.is_complete() is False
        assert set(ledger.missing_sections()) == set(dl.SECTION_HEADINGS)
