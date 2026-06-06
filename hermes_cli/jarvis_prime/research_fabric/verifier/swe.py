"""SWE-style local repo verifier — a real Plane-4 domain instance.

Generalizes the executable-verifier idea from single functions (algorithms lane)
to **repo-level** changes: given a working copy with a failing test command, a
candidate patch (new file content) is applied to an isolated copy and graded by
running the repo's *real* test command — pass iff exit code 0. This is the local,
download-free analogue of SWE-bench-style grading (the reward is execution of
withheld tests, not a model's say-so).

Everything runs in a temp copy under a scrubbed env (no network/secrets), so the
source working tree is never touched.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .sandbox import run_command


@dataclass(frozen=True)
class SweTask:
    task_id: str
    repo_path: str           # path to a working copy (a real dir; may be a git repo)
    target_path: str         # file (relative to repo) the candidate rewrites
    test_command: list[str]  # e.g. ["python", "-m", "pytest", "-q", "test_x.py"]
    timeout_s: float = 120.0


@dataclass(frozen=True)
class SweScore:
    accepted: bool
    correctness: float       # 1.0 iff the test command passes
    ran: bool
    detail: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "correctness": round(self.correctness, 4),
            "ran": self.ran,
            "detail": self.detail,
            "raw": self.raw,
        }


def score_swe_patch(task: SweTask, new_content: str) -> SweScore:
    """Apply ``new_content`` to ``target_path`` in an isolated copy, run the tests."""

    src = Path(task.repo_path)
    if not src.is_dir():
        return SweScore(False, 0.0, False, f"repo not found: {task.repo_path}")

    rel = task.target_path.replace("\\", "/")
    with tempfile.TemporaryDirectory(prefix="rf_swe_") as td:
        work = Path(td) / "repo"
        shutil.copytree(src, work, dirs_exist_ok=False)
        target = (work / rel).resolve()
        # Defense in depth: the target must stay inside the working copy.
        if work.resolve() not in target.parents and target != work.resolve():
            return SweScore(False, 0.0, False, "target escapes repo")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        res = run_command(task.test_command, cwd=work, timeout_s=task.timeout_s)

    if res.timed_out:
        return SweScore(False, 0.0, False, "test command timed out")
    passed = res.ok
    return SweScore(
        accepted=passed,
        correctness=1.0 if passed else 0.0,
        ran=True,
        detail="tests passed" if passed else (res.stderr.strip()[-300:] or "tests failed"),
        raw={"exit_code": res.exit_code},
    )


def baseline_fails(task: SweTask) -> bool:
    """True if the unpatched repo's test command currently fails (a real bug)."""

    res = run_command(task.test_command, cwd=Path(task.repo_path), timeout_s=task.timeout_s)
    return not res.ok


__all__ = ["SweTask", "SweScore", "score_swe_patch", "baseline_fails"]
