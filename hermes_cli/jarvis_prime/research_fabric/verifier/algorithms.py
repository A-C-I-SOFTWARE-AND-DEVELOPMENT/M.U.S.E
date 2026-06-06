"""Algorithms-lane verifier — the purest executable reward.

Per the research, the algorithms lane (op-count / latency are exact, and
correctness is checked by execution against held-out cases) is the ideal first
proving ground for the self-improvement machinery — the same propose ->
execute-verify -> keep-winners loop behind AlphaTensor / AlphaDev / AlphaEvolve.

An :class:`AlgorithmTask` defines an entrypoint function name, *public* cases
(visible to the solver) and *held-out* cases (used only for grading, never shown
to the solver — anti-overfit). :func:`score_algorithm_candidate` runs the
candidate's code in the sandbox and returns correctness + latency. Correctness is
binary per case; a candidate that passes all held-out cases is verifier-accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .sandbox import run_python_script

# Harness appended after the candidate code. Reads cases from argv[1] (a JSON
# file), calls the entrypoint, and prints a single JSON result line.
_HARNESS = """

if __name__ == "__main__":
    import json as _json, sys as _sys, time as _time
    _cases = _json.loads(open(_sys.argv[1], encoding="utf-8").read())
    _fn = globals().get({entrypoint!r})
    if _fn is None:
        print(_json.dumps({{"error": "missing entrypoint {entrypoint}"}}))
        raise SystemExit(2)
    _passed = 0
    _total = len(_cases)
    _t0 = _time.perf_counter()
    for _c in _cases:
        try:
            _out = _fn(*_c["args"])
        except Exception as _e:  # noqa: BLE001
            continue
        if _out == _c["expected"]:
            _passed += 1
    _elapsed = _time.perf_counter() - _t0
    print(_json.dumps({{"passed": _passed, "total": _total, "latency_s": _elapsed}}))
"""


@dataclass(frozen=True)
class AlgorithmCase:
    args: list[Any]
    expected: Any

    def to_dict(self) -> dict[str, Any]:
        return {"args": list(self.args), "expected": self.expected}


@dataclass(frozen=True)
class AlgorithmTask:
    task_id: str
    entrypoint: str
    prompt: str
    public_cases: tuple[AlgorithmCase, ...]
    holdout_cases: tuple[AlgorithmCase, ...]
    timeout_s: float = 15.0

    def public_cases_json(self) -> str:
        return json.dumps([c.to_dict() for c in self.public_cases])


@dataclass(frozen=True)
class AlgorithmScore:
    accepted: bool
    correctness: float          # fraction of held-out cases passed (0..1)
    public_correctness: float
    latency_s: float
    ran: bool
    detail: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "correctness": round(self.correctness, 4),
            "public_correctness": round(self.public_correctness, 4),
            "latency_s": round(self.latency_s, 6),
            "ran": self.ran,
            "detail": self.detail,
            "raw": self.raw,
        }


def _grade(code: str, task: AlgorithmTask, cases: tuple[AlgorithmCase, ...]) -> tuple[float, float, bool, str]:
    if not cases:
        return 0.0, 0.0, False, "no cases"
    script = code + _HARNESS.format(entrypoint=task.entrypoint)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="rf_alg_") as td:
        cases_path = Path(td) / "cases.json"
        cases_path.write_text(json.dumps([c.to_dict() for c in cases]), encoding="utf-8")
        res = run_python_script(
            script, args=[str(cases_path)], timeout_s=task.timeout_s
        )
    if res.timed_out:
        return 0.0, res.latency_s, False, "timed out"
    if not res.ok or res.parsed is None:
        return 0.0, res.latency_s, False, (res.stderr.strip()[-300:] or "no result")
    passed = float(res.parsed.get("passed", 0))
    total = float(res.parsed.get("total", len(cases))) or 1.0
    return passed / total, float(res.parsed.get("latency_s", res.latency_s)), True, "ok"


def score_algorithm_candidate(code: str, task: AlgorithmTask) -> AlgorithmScore:
    """Execute ``code`` against the task and return a verifier-grounded score."""

    pub_correct, _, pub_ran, _ = _grade(code, task, task.public_cases)
    hold_correct, latency, ran, detail = _grade(code, task, task.holdout_cases)
    accepted = ran and hold_correct >= 1.0 and pub_correct >= 1.0
    return AlgorithmScore(
        accepted=accepted,
        correctness=hold_correct,
        public_correctness=pub_correct,
        latency_s=latency,
        ran=ran and pub_ran,
        detail=detail,
        raw={"holdout_detail": detail},
    )


__all__ = [
    "AlgorithmCase",
    "AlgorithmTask",
    "AlgorithmScore",
    "score_algorithm_candidate",
]
