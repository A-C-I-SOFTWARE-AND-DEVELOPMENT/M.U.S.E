"""Tests for the user-profile builder surface.

In Hermes the orchestrator routes work to a *profile* — the agent
identity — and the profile_describer module is the pure-function half
of that builder pipeline: it walks a profile directory, harvests skill
names, and renders the prompt that asks the auxiliary LLM for a
description.

These tests cover only the *pure* pieces — skill discovery, JSON
extraction, and the "describable profiles" enumeration — so the suite
does not require an aux LLM, network access, or any provider keys.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hermes_cli import profile_describer as pd


# ── _collect_skills ───────────────────────────────────────────────────


class TestCollectSkills:
    def _write_skill(self, root: Path, rel: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nname: x\ndescription: y\n---\nbody\n", encoding="utf-8")

    def test_empty_when_skills_dir_missing(self, tmp_path: Path) -> None:
        assert pd._collect_skills(tmp_path) == []

    def test_flat_skill_yields_bare_name(self, tmp_path: Path) -> None:
        self._write_skill(tmp_path, "skills/alpha/SKILL.md")
        names = pd._collect_skills(tmp_path)
        assert names == ["alpha"]

    def test_categorised_skill_uses_category_prefix(self, tmp_path: Path) -> None:
        self._write_skill(tmp_path, "skills/devops/observability/SKILL.md")
        names = pd._collect_skills(tmp_path)
        assert names == ["devops/observability"]

    def test_ignores_hub_and_git(self, tmp_path: Path) -> None:
        self._write_skill(tmp_path, "skills/.hub/cached/SKILL.md")
        self._write_skill(tmp_path, "skills/.git/leftover/SKILL.md")
        self._write_skill(tmp_path, "skills/real/SKILL.md")
        names = pd._collect_skills(tmp_path)
        assert names == ["real"]

    def test_caps_to_prompt_budget(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(pd, "MAX_SKILLS_FOR_PROMPT", 4)
        for letter in "abcdefghij":
            self._write_skill(tmp_path, f"skills/cat/skill-{letter}/SKILL.md")
        names = pd._collect_skills(tmp_path)
        assert len(names) == 4
        # Sampling is evenly spaced so the suffix slice differs from the
        # head slice — we just confirm the cap holds.
        assert all(n.startswith("cat/skill-") for n in names)

    def test_returns_sorted_names(self, tmp_path: Path) -> None:
        for n in ("zeta", "alpha", "mu"):
            self._write_skill(tmp_path, f"skills/{n}/SKILL.md")
        names = pd._collect_skills(tmp_path)
        assert names == sorted(names)


# ── _extract_json_blob ────────────────────────────────────────────────


class TestExtractJsonBlob:
    def test_extracts_bare_object(self) -> None:
        assert pd._extract_json_blob('{"description": "x"}') == {"description": "x"}

    def test_strips_code_fences(self) -> None:
        raw = '```json\n{"description": "x"}\n```'
        assert pd._extract_json_blob(raw) == {"description": "x"}

    def test_handles_surrounding_prose(self) -> None:
        raw = 'Sure! Here it is:\n{"description": "ok"}\nLet me know!'
        assert pd._extract_json_blob(raw) == {"description": "ok"}

    def test_returns_none_on_no_object(self) -> None:
        assert pd._extract_json_blob("just prose") is None

    def test_returns_none_on_empty(self) -> None:
        assert pd._extract_json_blob("") is None

    def test_returns_none_on_invalid_json(self) -> None:
        assert pd._extract_json_blob("{not json}") is None

    def test_returns_none_when_top_level_is_array(self) -> None:
        # The describer always returns a single mapping; anything else
        # is treated as a parse failure.
        assert pd._extract_json_blob('["a", "b"]') is None


# ── describe_profile (failure-only — no aux LLM) ──────────────────────


class TestDescribeProfileGuards:
    def test_unknown_profile_returns_outcome_without_raising(self) -> None:
        outcome = pd.describe_profile("definitely-does-not-exist")
        assert isinstance(outcome, pd.DescribeOutcome)
        assert outcome.ok is False
        assert outcome.reason


# ── list_describable_profiles ─────────────────────────────────────────


class TestListDescribableProfiles:
    def test_returns_list(self) -> None:
        # With an isolated HERMES_HOME there are no profiles to describe;
        # the call must still succeed and return a list.
        result = pd.list_describable_profiles()
        assert isinstance(result, list)
