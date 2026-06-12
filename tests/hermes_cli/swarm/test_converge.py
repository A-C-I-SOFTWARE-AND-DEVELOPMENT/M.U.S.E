"""Tests for convergence — cooperative conflict backstop + competitive best-of-N."""

from __future__ import annotations

import json
from pathlib import Path

from muse_cli.swarm.converge import (
    converge_competitive,
    converge_cooperative,
    detect_runtime_conflicts,
)


def test_no_conflict_when_disjoint():
    changed = {"a": ["src/api/x.py"], "b": ["src/web/y.py"]}
    assert detect_runtime_conflicts(changed) == []
    result = converge_cooperative(changed)
    assert result.requires_manual_review is False
    assert set(result.kept) == {"a", "b"}


def test_runtime_conflict_surfaced():
    changed = {"a": ["src/shared.py"], "b": ["src/shared.py", "src/web/y.py"]}
    conflicts = detect_runtime_conflicts(changed)
    assert len(conflicts) == 1
    assert conflicts[0].files == ("src/shared.py",)
    result = converge_cooperative(changed)
    assert result.requires_manual_review is True


def _candidate(d: Path, name: str, *, diff: str, validation: str, success: bool):
    cdir = d / name
    cdir.mkdir(parents=True)
    (cdir / "output.md").write_text(f"# {name}\ndid the thing\n")
    (cdir / "patch.diff").write_text(diff)
    files = "\n".join(
        line[5:] for line in diff.splitlines() if line.startswith("+++ b/")
    )
    (cdir / "changed-files.txt").write_text(files + "\n")
    (cdir / "validation-output.txt").write_text(validation)
    (cdir / "status.json").write_text(json.dumps({"success": success}))


def test_competitive_picks_a_winner(tmp_path: Path):
    cand = tmp_path / "candidates"
    out = tmp_path / "merge"
    # Two candidates for the same grain; both pass, smaller diff should win.
    _candidate(
        cand, "cand-a",
        diff="+++ b/x.py\n+a = 1\n+b = 2\n+c = 3\n",
        validation="All tests passed", success=True,
    )
    _candidate(
        cand, "cand-b",
        diff="+++ b/x.py\n+a = 1\n",
        validation="All tests passed", success=True,
    )
    result = converge_competitive(cand, out)
    assert result.mode == "competitive"
    # A winner was chosen and the canonical merge artifacts were written.
    assert result.winner in {"cand-a", "cand-b"}
    assert (out / "scorecard.json").exists()
    assert (out / "final-plan.md").exists()
