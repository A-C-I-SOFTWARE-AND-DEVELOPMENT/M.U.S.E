#!/usr/bin/env python3
"""Corpus + characterization tests for ``tools/grading``.

Work Packet §1 p4, §11, §12.

The driving failure is concrete: a Level-1 QA answer was graded WRONG because
the model produced ``17000`` against a gold field of ``17``, after completing 6
turns and 6 API calls in 72.57 s.  The work was right; the grader was
unit-blind.

The obvious "fix" — make 17000 equal 17 — would be a worse bug, because it also
erases every genuinely wrong answer that happens to be a thousand times too
large.  So this file proves **both** directions:

*Recall*     every genuinely-equivalent pair is recognised as a match.
*Precision*  no genuinely-wrong pair is ever recognised as a match, and no
             genuinely-wrong pair is laundered into the ``ambiguous_unit``
             bucket either.

The third corpus, ``AMBIGUOUS``, is the point of the whole exercise: pairs that
*would* agree under some unit convention that nobody declared anywhere.  Those
must come back ``AMBIGUOUS_UNIT`` — a grading defect to surface, never resolved
by the comparison.

Run:

    .venv/Scripts/python.exe -m pytest tests/characterization/test_output_normalization.py \
        -p no:cacheprovider -o addopts="" -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from tools.grading import (
    GradingContext,
    NormalizationPolicy,
    OutputNormalizationValidator,
    Reason,
    Verdict,
    naive_normalize,
    parse_number_words,
    parse_numeric,
    validate_answer,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

Case = Tuple[str, str, Optional[GradingContext]]

#: The verbatim question from the recorded Level-1 row that this whole module
#: exists for (``results.jsonl`` at the repo root, task
#: ``e1fc63a2-da7a-432f-be78-7c4a95598703``).  Note "how many thousand hours":
#: the unit was stated in the question all along, and the grader could not read
#: it.
RECORDED_QUESTION = (
    "If Eliud Kipchoge could maintain his record-making marathon pace "
    "indefinitely, how many thousand hours would it take him to run the "
    "distance between the Earth and the Moon its closest approach? Please use "
    "the minimum perigee value on the Wikipedia page for the Moon when "
    "carrying out your calculation. Round your result to the nearest 1000 "
    "hours and do not use any comma separators if necessary."
)
RECORDED_MODEL_ANSWER = ": 17000"
RECORDED_GOLD_ANSWER = "17"


def ctx(**kwargs: object) -> GradingContext:
    return GradingContext(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Corpus 1 — genuinely equivalent.  Every one of these MUST be Verdict.MATCH.
# ---------------------------------------------------------------------------

EQUIVALENT: List[Case] = [
    # --- the recorded failure itself, verbatim from results.jsonl ---
    (RECORDED_MODEL_ANSWER, RECORDED_GOLD_ANSWER, ctx(question=RECORDED_QUESTION)),
    # --- the driving failure, with the unit actually declared or inferable ---
    ("17000", "17", ctx(question="How many units were sold, in thousands?")),
    ("17000", "17", ctx(unit_hint="thousands")),
    ("17000", "17", ctx(question="Revenue (in thousands) for FY24?")),
    ("17", "17000", ctx(unit_hint="thousands")),
    # --- unit scaling declared on the answer itself ---
    ("17k", "17000", None),
    ("17K", "17,000", None),
    ("17 thousand", "17000", None),
    ("1.5M", "1500000", None),
    ("1.5 million", "1,500,000", None),
    ("2bn", "2000000000", None),
    ("2 billion", "2,000,000,000", None),
    ("3 trillion", "3000000000000", None),
    # --- thousands separators and currency symbols ---
    ("1,234", "1234", None),
    ("$1,234.50", "1234.5", None),
    ("1,234.50", "$1,234.50", None),
    ("USD 1,234", "1234", None),
    ("1 234 567", "1234567", None),
    ("1.234.567", "1234567", None),
    ("€1.234,56", "1234.56", None),
    ("(1,234)", "-1234", None),
    # --- percentages vs fractions ---
    ("17%", "0.17", None),
    ("0.17", "17%", None),
    ("17 percent", "0.17", None),
    ("17%", "17", ctx(question="What percentage of respondents agreed?")),
    ("0.17", "17", ctx(question="What percentage of respondents agreed?")),
    ("17%", "17", ctx(unit_hint="percent")),
    # --- scientific notation ---
    ("1.7e4", "17000", None),
    ("1.7E+4", "17000", None),
    ("1.7 x 10^4", "17000", None),
    ("1.7 × 10^4", "17000", None),
    ("1.7e-2", "0.017", None),
    # --- spelled-out numbers ---
    ("seventeen", "17", None),
    ("seventeen thousand", "17000", None),
    ("one hundred five", "105", None),
    ("twenty-one", "21", None),
    # --- dimensional units, converted honestly ---
    ("17 km", "17000 m", None),
    ("17000 m", "17 km", None),
    ("1.5 kg", "1500 g", None),
    ("2 hours", "7200 s", None),
    ("1 GB", "1000 MB", None),
    ("17 km", "17", None),
    ("100 m", "100", None),
    # --- dates ---
    ("2026-08-16", "August 16, 2026", None),
    ("16 August 2026", "2026-08-16", None),
    ("Aug 16, 2026", "2026-08-16", None),
    ("08/16/2026", "2026-08-16", None),
    ("2026/08/16", "2026-08-16", None),
    ("01/02/2026", "2026-01-02", ctx(date_order="MDY")),
    ("01/02/2026", "2026-02-01", ctx(date_order="DMY")),
    # --- booleans ---
    ("yes", "true", None),
    ("Yes.", "TRUE", None),
    ("1", "yes", None),
    ("0", "no", None),
    ("no", "False", None),
    ("y", "yes", None),
    # --- whitespace, case and output wrappers ---
    ("  Paris  ", "paris", None),
    ("**Paris**", "Paris", None),
    ('"Paris"', "Paris", None),
    ("The answer is Paris", "Paris", None),
    ("Final answer: 42", "42", None),
    ("42.", "42", None),
    # --- numeric tolerance ---
    ("0.30000000001", "0.3", None),
    # --- lists ---
    ("apple, banana", "banana, apple", None),
    ("1,234; 5,678", "1234; 5678", None),
    ("Paris, France", "paris, france", None),
]


# ---------------------------------------------------------------------------
# Corpus 2 — genuinely wrong.  Every one MUST be Verdict.MISMATCH.
#
# Nothing here is a near-miss on a power of ten with an undeclared unit; those
# belong in AMBIGUOUS below.  These are answers that no unit convention can
# rescue, and a normalizer that "helpfully" matched any of them would be
# destroying the benchmark it is supposed to be repairing.
# ---------------------------------------------------------------------------

REAL_ERROR: List[Case] = [
    ("17000", "18", None),
    ("17000", "17001", None),
    ("1,234", "1,235", None),
    ("17%", "18%", None),
    ("1700%", "17%", None),  # both declare percent: a real 100x error
    ("1.7e4", "1.7e5", None),  # 10x is not a unit word anywhere
    ("0.5", "0.05", None),
    ("3.15", "3.14", None),
    ("42", "forty-three", None),
    # both sides declare their unit, so a gap is an error and not a convention
    ("17 km", "17 m", None),
    ("17 km", "17 mi", None),
    ("5 kg", "5 lb", None),
    ("1.5 GB", "1.5 MB", None),
    ("2 hours", "2 minutes", None),
    ("17 thousand", "17 million", None),
    ("17 M", "17 m", None),  # seventeen million is not seventeen metres
    # currency is a unit, not decoration
    ("$100", "€100", None),
    ("100 USD", "100 EUR", None),
    # non-numeric
    ("yes", "no", None),
    ("true", "0", None),
    ("Paris", "London", None),
    ("2026-08-16", "2026-08-17", None),
    ("August 16, 2026", "September 16, 2026", None),
    ("apple, banana", "apple, cherry", None),
    ("apple, banana", "apple", None),
    ("17", "17 apples", None),
    # a declared unit is not allowed to be inferred away by a contrary context
    ("17000", "17", ctx(question="How many units were sold, in millions?")),
]


# ---------------------------------------------------------------------------
# Corpus 3 — reconcilable only under a convention nobody declared.
# Every one MUST be Verdict.AMBIGUOUS_UNIT: not a pass, not a fail, a defect.
# ---------------------------------------------------------------------------

AMBIGUOUS: List[Case] = [
    ("17000", "17", None),  # <- the exact reported failure, unaided
    (RECORDED_MODEL_ANSWER, RECORDED_GOLD_ANSWER, None),  # same row, no question
    ("17", "17000", None),
    ("17k", "17", None),
    ("17", "17 thousand", None),
    ("1500000", "1.5", None),
    ("17000 m", "17", None),
    ("1.7e4", "17", None),
    ("17%", "17", None),
    ("17", "0.17", None),
    ("0.17", "17", None),
    ("1,234", "1.234", None),  # thousands separator vs decimal point
    ("01/02/2026", "2026-02-01", None),
    ("02/01/2026", "2026-02-01", None),
    ("3.14159", "3.14", None),
    ("3.14", "3.14159", None),
    ("17000, Paris", "17, Paris", None),
]


VALIDATOR = OutputNormalizationValidator()


def _label(case: Case) -> str:
    model, gold, context = case
    tag = ""
    if context is not None:
        tag = f"|ctx({context.question or context.unit_hint or context.date_order})"
    return f"{model!r}~{gold!r}{tag}"


# ---------------------------------------------------------------------------
# The driving failure, stated directly
# ---------------------------------------------------------------------------


def test_driving_failure_is_surfaced_and_not_coerced() -> None:
    """17000 against a gold of 17, with no unit anywhere, is a grading defect."""
    result = validate_answer("17000", "17")

    assert result.verdict is Verdict.AMBIGUOUS_UNIT
    assert result.reason == Reason.UNIT_SCALE_UNDECLARED
    assert not result.is_match
    # The incumbent lowercase/whitespace grader called this simply wrong.
    assert result.naive_match is False
    # ... and this is the row a human has to look at.
    assert result.is_grading_defect is True
    assert "1000" in result.detail


def test_the_recorded_level1_row_is_regraded_from_its_own_artifact() -> None:
    """Re-grade the real recorded row, read off disk, not paraphrased.

    ``results.jsonl`` at the repo root holds the row the packet describes:
    6 turns, 6 API calls, 72.57 s, ``model_answer=": 17000"`` against
    ``gold_answer="17"``, recorded ``correct: false``.  The question itself
    says "how many **thousand** hours", so the unit was declared all along and
    the incumbent grader simply could not read it.
    """
    artifact = REPO_ROOT / "results.jsonl"
    if not artifact.exists():  # pragma: no cover - depends on checkout state
        pytest.skip("results.jsonl not present in this checkout")
    rows = [
        json.loads(line)
        for line in artifact.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    recorded = [
        r for r in rows if r.get("task_id") == "e1fc63a2-da7a-432f-be78-7c4a95598703"
    ]
    if not recorded:  # pragma: no cover - depends on checkout state
        pytest.skip("the recorded Level-1 row is not in results.jsonl")
    row = recorded[0]

    # The failure exactly as recorded.
    assert row["model_answer"] == ": 17000"
    assert row["gold_answer"] == "17"
    assert row["correct"] is False
    assert (row["turns"], row["api_calls"], row["elapsed_s"]) == (6, 6, 72.57)

    result = validate_answer(
        row["model_answer"], row["gold_answer"], GradingContext(question=row["question"])
    )
    assert result.verdict is Verdict.MATCH
    assert result.reason == Reason.CONTEXT_UNIT_INFERRED
    assert "how many thousand" in result.detail
    # The recorded grade and the validator disagree, so the row is a defect.
    assert result.naive_match is False
    assert result.is_grading_defect is True

    # Without the question there is nothing declaring the unit, and the same
    # row is undecidable rather than a free pass.
    assert (
        validate_answer(row["model_answer"], row["gold_answer"]).verdict
        is Verdict.AMBIGUOUS_UNIT
    )


def test_driving_failure_matches_once_the_unit_is_declared() -> None:
    """The same pair is a clean match when the question states the unit."""
    question = "How many units were sold in 2024, in thousands?"
    result = validate_answer("17000", "17", GradingContext(question=question))

    assert result.verdict is Verdict.MATCH
    assert result.reason == Reason.CONTEXT_UNIT_INFERRED
    # The incumbent grader marked this row wrong; the validator disagrees, so
    # the recorded score for the row is wrong and must be surfaced.
    assert result.naive_match is False
    assert result.is_grading_defect is True


def test_the_inverse_is_never_normalised_into_a_false_match() -> None:
    """No amount of normalization may turn 17000 vs 17 into a pass."""
    for context in (
        None,
        GradingContext(),
        GradingContext(question="How many units were sold in 2024?"),
        GradingContext(question="What is the population of the town?"),
    ):
        result = validate_answer("17000", "17", context)
        assert result.verdict is not Verdict.MATCH, context


def test_a_contrary_declared_unit_is_a_mismatch_not_a_rescue() -> None:
    """A declared "millions" does not license a 1000x match."""
    result = validate_answer(
        "17000", "17", GradingContext(question="Revenue, in millions?")
    )
    assert result.verdict is Verdict.MISMATCH


# ---------------------------------------------------------------------------
# Corpus sweeps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", EQUIVALENT, ids=[_label(c) for c in EQUIVALENT])
def test_equivalent_pairs_match(case: Case) -> None:
    model, gold, context = case
    result = VALIDATOR.validate(model, gold, context)
    assert result.verdict is Verdict.MATCH, f"{result.reason}: {result.detail}"


@pytest.mark.parametrize("case", REAL_ERROR, ids=[_label(c) for c in REAL_ERROR])
def test_real_errors_are_mismatches(case: Case) -> None:
    model, gold, context = case
    result = VALIDATOR.validate(model, gold, context)
    assert result.verdict is Verdict.MISMATCH, f"{result.reason}: {result.detail}"


@pytest.mark.parametrize("case", AMBIGUOUS, ids=[_label(c) for c in AMBIGUOUS])
def test_ambiguous_pairs_are_surfaced(case: Case) -> None:
    model, gold, context = case
    result = VALIDATOR.validate(model, gold, context)
    assert result.verdict is Verdict.AMBIGUOUS_UNIT, f"{result.reason}: {result.detail}"
    assert result.is_grading_defect is True


# ---------------------------------------------------------------------------
# Precision and recall, computed rather than asserted case by case
# ---------------------------------------------------------------------------


def _confusion(predicate) -> Tuple[int, int, int, int]:
    """Return ``(tp, fp, fn, tn)`` for a "calls it a match" predicate."""
    tp = sum(1 for m, g, c in EQUIVALENT if predicate(m, g, c))
    fn = len(EQUIVALENT) - tp
    fp = sum(1 for m, g, c in REAL_ERROR if predicate(m, g, c))
    tn = len(REAL_ERROR) - fp
    return tp, fp, fn, tn


def _validator_says_match(model: str, gold: str, context: Optional[GradingContext]) -> bool:
    return VALIDATOR.validate(model, gold, context).verdict is Verdict.MATCH


def _incumbent_says_match(model: str, gold: str, _context: Optional[GradingContext]) -> bool:
    return naive_normalize(model) == naive_normalize(gold)


def test_precision_and_recall_are_both_perfect_on_the_corpus() -> None:
    tp, fp, fn, tn = _confusion(_validator_says_match)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0

    assert (tp, fp, fn, tn) == (len(EQUIVALENT), 0, 0, len(REAL_ERROR)), (
        f"tp={tp} fp={fp} fn={fn} tn={tn}"
    )
    assert precision == 1.0
    assert recall == 1.0


def test_no_real_error_is_laundered_into_the_ambiguous_bucket() -> None:
    """The third verdict must not become a dumping ground for wrong answers."""
    leaked = [
        (m, g)
        for m, g, c in REAL_ERROR
        if VALIDATOR.validate(m, g, c).verdict is Verdict.AMBIGUOUS_UNIT
    ]
    assert leaked == []


def test_validator_strictly_beats_the_incumbent_grader_in_both_directions() -> None:
    """The improvement is measured, not asserted."""
    v_tp, v_fp, v_fn, _ = _confusion(_validator_says_match)
    n_tp, n_fp, n_fn, _ = _confusion(_incumbent_says_match)

    v_recall = v_tp / (v_tp + v_fn)
    n_recall = n_tp / (n_tp + n_fn)
    v_precision = v_tp / (v_tp + v_fp)
    n_precision = n_tp / (n_tp + n_fp)

    assert v_recall > n_recall, (v_recall, n_recall)
    assert v_precision > n_precision, (v_precision, n_precision)
    # The incumbent's false positives are real, not hypothetical: lowercasing
    # makes "17 M" (seventeen million) equal "17 m" (seventeen metres).
    assert n_fp > 0
    assert _incumbent_says_match("17 M", "17 m", None) is True
    assert VALIDATOR.validate("17 M", "17 m").verdict is Verdict.MISMATCH


# ---------------------------------------------------------------------------
# Characterization of the grader this runs ahead of
# ---------------------------------------------------------------------------


def test_incumbent_normalizer_behaviour_is_pinned() -> None:
    """``naive_normalize`` mirrors gaia_runner's normalizer; pin its behaviour."""
    assert naive_normalize("  Paris  ") == "paris"
    assert naive_normalize("A  B") == "a b"
    assert naive_normalize(None) == ""
    # And the exact defect: it cannot see units at all.
    assert naive_normalize("17000") != naive_normalize("17")
    assert naive_normalize("$1,234.50") != naive_normalize("1234.5")


def test_gaia_runner_grader_is_still_unit_blind() -> None:
    """Characterization anchor over the grader this validator runs ahead of.

    If someone teaches ``benchmarks/gaia_runner.py`` about units, this test
    fails and this module's premise has to be re-checked.  It is read-only.
    """
    runner = REPO_ROOT / "benchmarks" / "gaia_runner.py"
    if not runner.exists():  # pragma: no cover - depends on checkout layout
        pytest.skip("benchmarks/gaia_runner.py not present in this checkout")
    source = runner.read_text(encoding="utf-8", errors="replace")
    assert "def _normalize_answer" in source
    assert "def exact_match_score" in source
    body_start = source.index("def _normalize_answer")
    body = source[body_start : source.index("def exact_match_score")]
    for unit_aware_token in ("thousand", "percent", "1000", "unit_"):
        assert unit_aware_token not in body, (
            "gaia_runner._normalize_answer now looks unit-aware; re-check the "
            "premise of tools/grading before trusting this test file"
        )


# ---------------------------------------------------------------------------
# Parser-level behaviour that the corpus depends on
# ---------------------------------------------------------------------------


def test_parse_numeric_keeps_declarations_separate() -> None:
    parsed = parse_numeric("17k")
    assert parsed is not None
    assert parsed.magnitude == Decimal(17)
    assert parsed.scale == Decimal(1000)
    assert parsed.scale_token == "k"
    assert parsed.reported == Decimal(17000)
    assert parsed.qualified is True

    bare = parse_numeric("17000")
    assert bare is not None
    assert bare.qualified is False


def test_parse_numeric_refuses_to_strip_an_unknown_qualifier() -> None:
    """``17 apples`` is not the number 17 with decoration."""
    assert parse_numeric("17 apples") is None
    assert parse_numeric("17 km") is not None


def test_single_letter_scale_suffixes_are_case_sensitive() -> None:
    million = parse_numeric("1.5M")
    metres = parse_numeric("1.5 m")
    assert million is not None and metres is not None
    assert million.reported == Decimal("1500000")
    assert metres.reported == Decimal("1.5")
    assert metres.dimension == "length"


def test_number_words_report_the_scale_they_declared() -> None:
    assert parse_number_words("seventeen thousand") == (Decimal(17000), "thousand")
    assert parse_number_words("seventeen") == (Decimal(17), None)
    assert parse_number_words("not a number") is None


def test_ten_is_not_an_ambiguity_factor() -> None:
    """No unit word means ten, so a 10x gap is a wrong answer."""
    assert Decimal(10) not in NormalizationPolicy().ambiguity_factors
    assert validate_answer("170", "17").verdict is Verdict.MISMATCH


def test_precision_ambiguity_can_be_switched_off() -> None:
    strict = OutputNormalizationValidator(
        NormalizationPolicy(precision_ambiguity=False)
    )
    assert strict.validate("3.14159", "3.14").verdict is Verdict.MISMATCH
    assert validate_answer("3.14159", "3.14").verdict is Verdict.AMBIGUOUS_UNIT


def test_numeric_tolerance_is_configurable_and_tight_by_default() -> None:
    # Same stated precision on both sides, so this is not a rounding question:
    # at the default tolerance it is simply a different number.
    assert validate_answer("0.3000001", "0.3000000").verdict is Verdict.MISMATCH
    loose = OutputNormalizationValidator(NormalizationPolicy(rel_tol=Decimal("1e-5")))
    assert loose.validate("0.3000001", "0.3000000").verdict is Verdict.MATCH
    # A gold field stated to fewer decimals is a precision question, and gets
    # surfaced instead of being failed.
    assert validate_answer("0.3000001", "0.3").verdict is Verdict.AMBIGUOUS_UNIT


# ---------------------------------------------------------------------------
# Report and CLI
# ---------------------------------------------------------------------------


def _records() -> List[dict]:
    return [
        {
            "task_id": "t-ok",
            "question": "What is the capital of France?",
            "model_answer": "  paris ",
            "gold_answer": "Paris",
        },
        {
            "task_id": "t-defect",
            "question": "How many units were sold in 2024?",
            "model_answer": "17000",
            "gold_answer": "17",
        },
        {
            "task_id": "t-fixed",
            "question": "How many units were sold in 2024, in thousands?",
            "model_answer": "17000",
            "gold_answer": "17",
        },
        {
            "task_id": "t-wrong",
            "question": "How many units were sold in 2024?",
            "model_answer": "17000",
            "gold_answer": "18",
        },
    ]


def test_report_counts_and_defect_selection() -> None:
    report = VALIDATOR.validate_records(_records())
    summary = report.summary()

    assert summary["total"] == 4
    assert summary["match"] == 2  # t-ok, t-fixed
    assert summary["mismatch"] == 1  # t-wrong
    assert summary["ambiguous_unit"] == 1  # t-defect
    assert summary["naive_grader_match"] == 1  # only t-ok

    defect_ids = sorted(r.task_id for r in report.defects)
    assert defect_ids == ["t-defect", "t-fixed"]

    rendered = report.render()
    assert "ambiguous_unit       : 1" in rendered
    assert "grading defects      : 2" in rendered
    # The ambiguous row is named in the body, with the incumbent's verdict.
    assert "unit_scale_undeclared" in rendered
    assert "(incumbent said wrong)" in rendered
    # The plainly-wrong row is not something a human is asked to look at.
    assert "'18'" not in rendered
    # ASCII only, so the report survives a non-UTF-8 console.
    assert rendered.isascii()


def test_cli_reports_and_signals_ambiguity(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in _records():
            handle.write(json.dumps(record) + "\n")
    out_json = tmp_path / "report.json"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.grading.cli",
            str(path),
            "--json",
            str(out_json),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 2, proc.stderr  # ambiguity present
    assert "ambiguous_unit       : 1" in proc.stdout, proc.stdout

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["grading_defects"] == 2
    verdicts = {row["task_id"]: row["verdict"] for row in payload["results"]}
    assert verdicts == {
        "t-ok": "match",
        "t-defect": "ambiguous_unit",
        "t-fixed": "match",
        "t-wrong": "mismatch",
    }


def test_cli_single_pair_mode(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.grading.cli", "--answer", "17000", "--gold", "17"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 2, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["verdict"] == "ambiguous_unit"
    assert payload["reason"] == Reason.UNIT_SCALE_UNDECLARED

    clean = subprocess.run(
        [sys.executable, "-m", "tools.grading.cli", "--answer", "1,234", "--gold", "1234"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    # A match the incumbent grader would have failed is still a defect (exit 1),
    # because the recorded score for that row is wrong.
    assert clean.returncode == 1, clean.stderr
    assert json.loads(clean.stdout)["verdict"] == "match"
