"""Tests for the EVAL-1 eval harness."""

from muse_cli.evals import EvalCase, EvalReport, run_suite
from muse_cli.model_registry import _worker_from_yaml


def test_model_independent_cases_run_without_runner():
    report = run_suite("w1")
    # compaction_quality + scrub_no_leak run; tool_call_correctness is skipped.
    assert "compaction_quality" in report.scores
    assert "scrub_no_leak" in report.scores
    assert "tool_call_correctness" in report.skipped


def test_scrub_case_scores_full():
    report = run_suite("w1")
    assert report.scores["scrub_no_leak"] == 1.0


def test_compaction_case_scores_positive():
    report = run_suite("w1")
    assert report.scores["compaction_quality"] > 0.0


def test_runner_enables_model_dependent_case():
    def good_runner(_prompt):
        return {"name": "echo", "arguments": {"text": "hi"}}

    report = run_suite("w1", runner=good_runner)
    assert report.scores.get("tool_call_correctness") == 1.0
    assert "tool_call_correctness" not in report.skipped


def test_bad_runner_scores_zero_not_crash():
    report = run_suite("w1", runner=lambda _p: "not a tool call")
    assert report.scores["tool_call_correctness"] == 0.0


def test_case_exception_scores_zero_not_crash():
    def boom(_runner):
        raise RuntimeError("kaboom")

    report = run_suite("w1", cases=(EvalCase("boom", boom),))
    assert report.scores["boom"] == 0.0
    assert report.passed is False


def test_threshold_and_pass():
    report = run_suite("w1", threshold=0.0)
    assert report.passed is True
    assert 0.0 <= report.aggregate <= 1.0


def test_empty_report_does_not_pass():
    assert EvalReport(worker_id="x").passed is False


def test_to_registry_fields_feeds_route2():
    report = run_suite("w1", threshold=0.0)
    fields = report.to_registry_fields()
    assert set(fields) == {"eval_passed", "eval_results"}
    # The fields must load into a WorkerEntry (ROUTE-2 consumer).
    w = _worker_from_yaml({"id": "w1", **{
        "eval_passed": fields["eval_passed"],
        "eval_results": dict(fields["eval_results"]),
    }})
    assert w.eval_passed == fields["eval_passed"]
    assert w.eval_results_dict == dict(fields["eval_results"])
