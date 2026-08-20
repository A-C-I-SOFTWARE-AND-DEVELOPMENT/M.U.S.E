# `tools/grading` — output normalization and unit interpretation, before grading

Work Packet §1 p4, §11, §12.

## The failure this exists for

A Level-1 QA answer was graded **wrong** because the model produced `17000`
against a gold field of `17`, after completing 6 turns and 6 API calls in
72.57 s. The work was right; the grader was unit-blind.

The incumbent grader is `benchmarks/gaia_runner.py`:

```python
def _normalize_answer(ans):
    s = str(ans).strip()
    s = _WHITESPACE_RE.sub(" ", s)
    return s.lower()

def exact_match_score(model_answer, gold_answer):
    return _normalize_answer(model_answer) == _normalize_answer(gold_answer)
```

Lowercase and whitespace, and nothing else. It cannot tell a unit convention
apart from a wrong answer — and, in the other direction, it happily reports
that `17 M` (seventeen million) equals `17 m` (seventeen metres).

## The rule

Making `17000 == 17` would be a worse bug than the one it fixes, because it
would also erase every genuinely wrong answer that happens to be a thousand
times too large. So the verdict is **three-way**:

| Verdict | Meaning |
|---|---|
| `MATCH` | Same value under a reading someone actually declared, or that the question makes inferable. |
| `MISMATCH` | Different values, and no unit convention reconciles them. |
| `AMBIGUOUS_UNIT` | They *would* agree under a plausible unit convention, but nothing — answer, gold field or question — says which convention applies. |

`AMBIGUOUS_UNIT` is **not a soft pass**. It is a defect in the *benchmark row*:
the task did not state the unit of its gold field, so the row cannot be graded
either way. It is surfaced, never resolved by the comparison.

```python
>>> from tools.grading import validate_answer, GradingContext
>>> validate_answer("17000", "17").verdict.value
'ambiguous_unit'
>>> validate_answer("17000", "17", GradingContext(question="Sales, in thousands?")).verdict.value
'match'
>>> validate_answer("17000", "17", GradingContext(question="Sales, in millions?")).verdict.value
'mismatch'
>>> validate_answer("17000", "18").verdict.value
'mismatch'
```

A declared unit cuts **both** ways: the same context that licenses the match
under "in thousands" forces the mismatch under "in millions".

## What it normalizes

- Thousands separators and currency symbols/codes — `$1,234.50`, `€1.234,56`,
  `USD 1,234`, `1 234 567`, accounting negatives `(1,234)`.
- Unit scaling — `17k`, `17K`, `17 thousand`, `1.5M`, `2bn`, `3 trillion`,
  plus English cardinals (`seventeen thousand`).
- Percentages vs fractions — `17%` ≡ `0.17`.
- Scientific notation — `1.7e4`, `1.7E+4`, `1.7 x 10^4`, `1.7 × 10^4`.
- Dimensional units — length, mass, time and data, converted through a base
  unit (`17 km` ≡ `17000 m`, `2 hours` ≡ `7200 s`, `1 GB` ≡ `1000 MB`).
- Dates — ISO, `MM/DD/YYYY`, `DD/MM/YYYY`, `August 16, 2026`, `16 August 2026`.
- Booleans — `yes` / `true` / `1`, `no` / `false` / `0`.
- Whitespace, case, markdown wrappers, quotes, `Final answer:` boilerplate, and
  a leading `:` / `=` left behind by final-answer extraction — the recorded
  failing row's `model_answer` is literally `": 17000"`.
- Numeric tolerance — configurable, `1e-9` relative by default.
- Lists — comma/semicolon separated, order-insensitive by default. `1,234`
  stays one number.

## What it deliberately does not do

- **10× is not an ambiguity.** No unit word means ten, so `1.7e4` against
  `1.7e5` is a plain wrong answer. The ambiguity factors are 10², 10³, 10⁶,
  10⁹, 10¹².
- **It never strips an unknown qualifier.** `17 apples` is text, not the number
  17 with decoration — otherwise `17 apples` would match `17 oranges`.
- **Two qualified sides are never ambiguous.** If both answers state their own
  units, a gap between them is a wrong answer: `17 km` vs `17 m` is a mismatch,
  and so is `1700%` vs `17%`.
- **Contested tokens are left out of the tables.** `ton` (short ton vs tonne),
  `mm` as "millions", bare `b` as bit/byte/billion, `pound` as a currency, and
  temperature (affine, not scalar) are all absent on purpose. See
  `units.py` for the reason attached to each omission.
- **It does not grade.** It reports what a grader is about to get wrong. No
  existing grader is edited by this package.

## Usage

```sh
# whole results file (the shape gaia_runner.py already writes)
python -m tools.grading.cli results.jsonl --json report.json

# one pair
python -m tools.grading.cli --answer 17000 --gold 17
```

Exit codes: `0` clean, `1` the incumbent grader disagrees with the validator on
at least one row, `2` at least one row is `ambiguous_unit` and cannot be graded
either way.

Optional per-row fields, honoured if present and ignored otherwise:
`unit_hint` (`"thousands"`, `"percent"`, `"km"`, ...) and `date_order`
(`"MDY"` / `"DMY"`).

## Wiring it in

This package is additive and runs **ahead of** grading; nothing in
`benchmarks/` is modified by it. To use it as a gate, a caller compares its
verdict with the incumbent score and routes `AMBIGUOUS_UNIT` rows to a human:

```python
from tools.grading import OutputNormalizationValidator, GradingContext, Verdict

validator = OutputNormalizationValidator()
result = validator.validate(model_answer, gold_answer, GradingContext(question=q))
if result.verdict is Verdict.AMBIGUOUS_UNIT:
    ...  # benchmark row is under-specified: fix the task, do not score it
correct = result.is_match
```

Editing `benchmarks/gaia_runner.py` to call this is a separate, deliberate
change and has not been made.

## Re-grading the real row

The failing row is on disk at `results.jsonl` in the repo root, task
`e1fc63a2-da7a-432f-be78-7c4a95598703` — `model_answer: ": 17000"`,
`gold_answer: "17"`, `correct: false`, 6 turns, 6 API calls, 72.57 s. Its
question reads *"how many **thousand** hours would it take him..."*, so the
unit was stated in the task all along.

```
$ python -m tools.grading.cli results.jsonl
output-normalization precheck (Work Packet sec.1 p4, sec.11, sec.12)
  rows                 : 1
  match                : 1
  mismatch             : 0
  ambiguous_unit       : 0
  incumbent grader ok  : 0
  grading defects      : 1

  defects to surface (not resolved here):
    [match         ] context_unit_inferred          model=': 17000' gold='17' (incumbent said wrong)
        equal at 17000 once the declared unit is applied [context_scale(question:'how many thousand')]; value=17000 vs value=17
```

Strip the question and the same row comes back `ambiguous_unit`, not `match`.
The file is read, never written.

## Tests

`tests/characterization/test_output_normalization.py` carries three labelled
corpora — equivalent, real-error, and ambiguous — and computes precision and
recall rather than asserting them case by case. It also pins the incumbent
grader's behaviour, so if `gaia_runner.py` ever becomes unit-aware the
characterization test says so.

```sh
.venv/Scripts/python.exe -m pytest tests/characterization/test_output_normalization.py \
    -p no:cacheprovider -o addopts="" -q
```
