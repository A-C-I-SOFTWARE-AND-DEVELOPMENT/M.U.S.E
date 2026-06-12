"""Tests for the benchmark-harness layer (real verifiers, temp repo, local suite)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from muse_cli.jarvis_prime.research_fabric.benchmarks import (
    BenchmarkTaskSpec,
    load_suite,
    run_suite,
)


def _alg_spec(candidate: str) -> dict:
    return {
        "task_id": "alg_sum",
        "domain": "code_generation",
        "kind": "algorithm",
        "payload": {
            "entrypoint": "solve",
            "prompt": "sum a list",
            "public_cases": [{"args": [[1, 2, 3]], "expected": 6}],
            "holdout_cases": [{"args": [[10, -5, 5]], "expected": 10}],
            "candidate": candidate,
        },
    }


def _swe_spec(repo_rel: str, candidate: str) -> dict:
    return {
        "task_id": "swe_square",
        "domain": "software_development",
        "kind": "swe",
        "payload": {
            "repo_path": repo_rel,
            "target_path": "mod.py",
            "test_command": [sys.executable, "-c", "import mod; assert mod.f(3) == 9; print('ok')"],
            "candidate": candidate,
        },
    }


def _write_suite(tmp_path: Path, specs: list[dict]) -> Path:
    path = tmp_path / "suite.jsonl"
    path.write_text("\n".join(json.dumps(s) for s in specs) + "\n", encoding="utf-8")
    return path


def _make_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mod.py").write_text("def f(x):\n    return x\n", encoding="utf-8")


def test_load_suite_round_trips(tmp_path) -> None:
    path = _write_suite(tmp_path, [_alg_spec("def solve(xs):\n    return sum(xs)\n")])
    specs = load_suite(path)
    assert len(specs) == 1
    assert isinstance(specs[0], BenchmarkTaskSpec)
    assert specs[0].kind == "algorithm"


def test_correct_candidates_score_full(tmp_path) -> None:
    _make_repo(tmp_path)
    path = _write_suite(
        tmp_path,
        [
            _alg_spec("def solve(xs):\n    return sum(xs)\n"),
            _swe_spec("repo", "def f(x):\n    return x * x\n"),
        ],
    )
    result = run_suite(load_suite(path), base_dir=path.parent)
    assert result.resolved_rate == 1.0
    scores = result.per_domain_scores()
    assert scores["code_generation"] == 1.0
    assert scores["software_development"] == 1.0


def test_wrong_candidates_score_zero(tmp_path) -> None:
    _make_repo(tmp_path)
    path = _write_suite(
        tmp_path,
        [
            _alg_spec("def solve(xs):\n    return 0\n"),
            _swe_spec("repo", "def f(x):\n    return x + 1\n"),
        ],
    )
    result = run_suite(load_suite(path), base_dir=path.parent)
    assert result.resolved_rate == 0.0


def test_solver_used_when_no_embedded_candidate(tmp_path) -> None:
    spec = _alg_spec("ignored")
    del spec["payload"]["candidate"]
    path = _write_suite(tmp_path, [spec])
    result = run_suite(
        load_suite(path),
        solver=lambda _task: "def solve(xs):\n    return sum(xs)\n",
        base_dir=path.parent,
    )
    assert result.resolved_rate == 1.0


def test_missing_candidate_and_solver_does_not_crash(tmp_path) -> None:
    spec = _alg_spec("ignored")
    del spec["payload"]["candidate"]
    path = _write_suite(tmp_path, [spec])
    result = run_suite(load_suite(path), base_dir=path.parent)
    assert result.resolved_rate == 0.0
    assert result.outcomes[0].ran is False
