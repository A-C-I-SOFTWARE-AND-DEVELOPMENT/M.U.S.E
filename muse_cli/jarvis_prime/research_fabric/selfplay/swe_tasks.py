"""A runnable demo SWE task for the repo-level (Plane 4) improvement loop.

Materializes a tiny working copy with a real bug and a real test command, so the
``swe_local`` improvement path can be exercised end-to-end with no external
downloads. A real task points ``repo_path`` at an actual checkout and supplies
the repo's real test command; the grading is identical (run the tests, pass iff
exit 0).
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..verifier.swe import SweTask

# `f` should square its input; the seeded bug returns the input unchanged.
_BUGGY = "def f(x):\n    return x\n"
_FIX = "def f(x):\n    return x * x\n"
_TEST_CMD = [
    sys.executable,
    "-c",
    "import mod; assert mod.f(3) == 9; assert mod.f(4) == 16; print('ok')",
]


def make_demo_swe_repo(dest: Path) -> SweTask:
    """Create a buggy working copy at ``dest`` and return its SweTask."""

    dest.mkdir(parents=True, exist_ok=True)
    (dest / "mod.py").write_text(_BUGGY, encoding="utf-8")
    return SweTask(
        task_id="square_fix",
        repo_path=str(dest),
        target_path="mod.py",
        test_command=list(_TEST_CMD),
    )


def demo_swe_baseline() -> str:
    return _BUGGY


def demo_swe_fix() -> str:
    return _FIX


def demo_swe_proposer(_current: str) -> list[str]:
    """Reference proposer: returns the correct fix (stand-in for an LLM)."""

    return [_FIX]


__all__ = [
    "make_demo_swe_repo",
    "demo_swe_baseline",
    "demo_swe_fix",
    "demo_swe_proposer",
]
