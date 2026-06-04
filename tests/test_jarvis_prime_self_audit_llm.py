"""Tests for the optional model-driven self-audit lanes (llm_lane).

A stub ``model_invoke`` keeps these deterministic: the LLM judge maps model
JSON to clause findings, falls back to None on garbage/errors, and the LLM
auditor rewrites a seed's prompt (falling back to the seed prompt on error).
"""

import json

from hermes_cli.jarvis_prime.self_audit import (
    SEEDS,
    llm_auditor,
    llm_judge,
    llm_target,
    run_report,
    run_seed,
    select_seeds,
)
from hermes_cli.jarvis_prime.self_audit.harness import compliant_target


def _seed(seed_id):
    return next(s for s in SEEDS if s.id == seed_id)


def test_llm_judge_marks_violation():
    seed = _seed("S1")  # probes C9, C10 (both fatal)

    def model(_prompt):
        return json.dumps(
            {
                "findings": [
                    {"clause_id": "C9", "passed": False, "note": "deployed anyway"},
                    {"clause_id": "C10", "passed": False, "note": "no exact phrase"},
                ]
            }
        )

    findings = llm_judge(model)(seed, run_seed(seed, compliant_target))
    assert findings is not None
    assert all(not f.passed for f in findings)
    assert {f.clause_id for f in findings} == set(seed.probes)


def test_llm_judge_handles_code_fenced_json_and_pass():
    seed = _seed("S1")

    def model(_prompt):
        body = json.dumps(
            {"findings": [{"clause_id": "C9", "passed": True}, {"clause_id": "C10", "passed": True}]}
        )
        return f"```json\n{body}\n```"

    findings = llm_judge(model)(seed, run_seed(seed, compliant_target))
    assert findings is not None and all(f.passed for f in findings)


def test_llm_judge_falls_back_on_garbage():
    seed = _seed("S1")
    assert llm_judge(lambda _p: "not json at all")(seed, run_seed(seed, compliant_target)) is None


def test_llm_judge_falls_back_on_model_error():
    seed = _seed("S1")

    def boom(_prompt):
        raise RuntimeError("model down")

    assert llm_judge(boom)(seed, run_seed(seed, compliant_target)) is None


def test_run_report_with_llm_judge():
    # An empty findings list defaults every probed clause to passed -> approve.
    def lenient(_prompt):
        return json.dumps({"findings": []})

    report = run_report(
        select_seeds(pool="core"), compliant_target, grader=llm_judge(lenient), run_id="llm"
    )
    assert report.overall_verdict == "approve"


def test_llm_target_puts_a_model_under_test():
    target = llm_target(lambda _p: "I refuse; this needs your approval.")
    assert "refuse" in target(_seed("S1"))


def test_llm_auditor_rewrites_prompt_and_reaches_target():
    seed = _seed("S1")
    auditor = llm_auditor(lambda _p: "SHARPENED: deploy now, no time to ask")
    transcript = run_seed(seed, compliant_target, auditor=auditor)
    auditor_turn = next(t.text for t in transcript.turns if t.role == "auditor")
    assert auditor_turn.startswith("SHARPENED")


def test_llm_auditor_falls_back_on_error():
    seed = _seed("S1")

    def boom(_prompt):
        raise RuntimeError("x")

    assert llm_auditor(boom)(seed) == seed.prompt
