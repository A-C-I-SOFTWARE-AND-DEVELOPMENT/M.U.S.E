"""Anti-rot guard for the §5.3 seam extraction plan.

Work Packet §1 p4 / §5.3 prescribe *characterization tests and seam
extraction* for the fifteen branch-heavy orchestration hotspots — and
explicitly **not** a broad rewrite. The plan that records where those seams
are lives outside this repository, in ``muse-dsh/docs/SEAM_EXTRACTION_PLAN.md``.
A plan that names functions and line ranges rots the moment somebody renames
one of them, and a rotted plan is worse than no plan: it reads authoritative
while pointing at code that no longer exists.

This module asserts the **relationship between that plan and this tree**:

* every hotspot the plan names still resolves, uniquely, at the stated path;
* every seam symbol the plan names still exists in the module it claims;
* every hotspot is still branch-heavy, i.e. still a hotspot at all;
* every hotspot still carries the characterization coverage it demands
  *before* it may be touched;
* an extraction may only be recorded in the plan once the extracted symbol
  exists **and** a characterization test covering it exists.

What it deliberately does **not** assert
----------------------------------------
Line numbers. ``AGENTS.md`` § "Don't write change-detector tests" is binding:
"if the test reads like a snapshot of current data, delete it. If it reads
like a contract about how two pieces of data must relate, keep it." Line
numbers are expected to change on every edit; the plan records them as dated
observations, and pinning them here would guarantee that routine work breaks
CI. Names, uniqueness, existence and structure are contracts. Line numbers are
not.

Nothing here imports application code — ``cli.py`` and ``gateway/run.py`` are
read with :mod:`ast`, never executed.
"""

from __future__ import annotations

import ast
import json
import os
import re
from functools import lru_cache
from pathlib import Path

import pytest

# ── Locating the two documents this test relates ────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]

_PLAN_ENV_VAR = "MUSE_SEAM_EXTRACTION_PLAN"
_PLAN_SCHEMA = "seam-extraction-plan/v1"

#: How branch-heavy a function must still be to count as a §5.3 hotspot.
#: Deliberately far below every recorded value (the smallest is in the low
#: hundreds) — this is an invariant that catches "this name now points at
#: something else entirely", not a snapshot of a current measurement.
BRANCHISH_FLOOR = 50

#: AST node types counted as branching. Nested definitions are included,
#: because a closure's branches are still branches the caller must survive.
_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.BoolOp,
    ast.IfExp,
    ast.Match,
    ast.match_case,
    ast.Assert,
)


def _candidate_plan_paths() -> list[Path]:
    # An explicit override is authoritative: if it is set and does not exist,
    # skip rather than quietly checking a different document than the caller
    # asked for.
    override = os.environ.get(_PLAN_ENV_VAR)
    if override:
        return [Path(override)]
    return [
        # muse-dsh sits beside the repo, and is not itself a git repository.
        REPO_ROOT.parent / "muse-dsh" / "docs" / "SEAM_EXTRACTION_PLAN.md",
        # If the plan is ever vendored into this repo instead.
        REPO_ROOT / "docs" / "SEAM_EXTRACTION_PLAN.md",
    ]


def _find_plan() -> Path | None:
    for path in _candidate_plan_paths():
        if path.is_file():
            return path
    return None


_FENCE_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def _extract_index(text: str) -> dict | None:
    """Return the machine-readable index block, or None if absent."""
    for block in _FENCE_RE.findall(text):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("schema") == _PLAN_SCHEMA:
            return data
    return None


_PLAN_PATH = _find_plan()
_PLAN_TEXT = _PLAN_PATH.read_text(encoding="utf-8") if _PLAN_PATH else ""
_INDEX = _extract_index(_PLAN_TEXT) if _PLAN_TEXT else None
_HOTSPOTS: list[dict] = list(_INDEX.get("hotspots", [])) if _INDEX else []

_SKIP_REASON = (
    f"seam extraction plan not found; looked at "
    f"{', '.join(str(p) for p in _candidate_plan_paths())}. "
    f"Set {_PLAN_ENV_VAR} to point at it."
)

requires_plan = pytest.mark.skipif(_PLAN_PATH is None, reason=_SKIP_REASON)


# ── AST helpers (parse each module at most once per session) ────────────────


@lru_cache(maxsize=None)
def _parse(rel_path: str) -> tuple[tuple[str, ast.AST], ...]:
    """Return every ``(qualname, node)`` function definition in a module.

    Qualnames follow ``Class.method`` / ``outer.inner`` dotted form, matching
    how the plan writes them.
    """
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=rel_path)

    def walk(node: ast.AST, prefix: str):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = prefix + child.name
                yield qual, child
                yield from walk(child, qual + ".")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, prefix + child.name + ".")
            else:
                yield from walk(child, prefix)

    return tuple(walk(tree, ""))


def _resolve(rel_path: str, qualname: str) -> list[ast.AST]:
    return [node for qual, node in _parse(rel_path) if qual == qualname]


def _short_name_count(rel_path: str, short: str) -> int:
    return sum(1 for qual, _ in _parse(rel_path) if qual.rsplit(".", 1)[-1] == short)


def _branchish(node: ast.AST) -> int:
    return sum(1 for child in ast.walk(node) if isinstance(child, _BRANCH_NODES))


def _hotspot_id(hotspot: dict) -> str:
    return f"{hotspot.get('id', '?')}-{hotspot.get('qualname', '?')}"


_PARAMS = _HOTSPOTS or [None]
_IDS = [_hotspot_id(h) if h else "no-plan" for h in _PARAMS]


def _require(hotspot):
    if hotspot is None:
        pytest.skip(_SKIP_REASON)
    return hotspot


# ── Document integrity ──────────────────────────────────────────────────────


@requires_plan
def test_plan_carries_a_machine_readable_index():
    assert _INDEX is not None, (
        f"{_PLAN_PATH} has no ```json fenced block whose 'schema' is "
        f"{_PLAN_SCHEMA!r}. Without it this guard cannot check the plan "
        f"against the tree, and the plan is free to rot."
    )
    assert _HOTSPOTS, "the index declares no hotspots"


@requires_plan
def test_index_covers_every_packet_hotspot_exactly_once():
    """§5.3 names fifteen hotspots; the plan must address all fifteen."""
    assert len(_HOTSPOTS) == 15, (
        f"§5.3 names 15 complexity hotspots, the plan indexes "
        f"{len(_HOTSPOTS)}. Adding or dropping one is a change to what the "
        f"packet asked for and must be argued, not made silently."
    )
    ids = [h["id"] for h in _HOTSPOTS]
    assert len(set(ids)) == len(ids), f"duplicate hotspot ids: {ids}"

    keys = {(h["path"], h["qualname"]) for h in _HOTSPOTS}
    assert len(keys) == 15, "two hotspots resolve to the same path/qualname pair"

    ranks = sorted(h["rank"] for h in _HOTSPOTS)
    assert ranks == list(range(1, 16)), (
        f"ranks must be a permutation of 1..15 so the extraction order is "
        f"total and unambiguous; got {ranks}"
    )


@requires_plan
def test_index_and_prose_do_not_disagree():
    """Every indexed function must also be discussed in the prose body."""
    prose = _PLAN_TEXT.split("## Machine-readable index")[0]
    missing = [
        h["qualname"]
        for h in _HOTSPOTS
        if h["qualname"].rsplit(".", 1)[-1] not in prose
    ]
    assert not missing, (
        f"indexed but never discussed in the plan's prose: {missing}. "
        f"An index entry with no reasoning behind it is not a plan."
    )


@requires_plan
def test_packet_figures_are_preserved_alongside_measured_ones():
    """§14.1 forbids merging metrics from two revisions.

    The plan must keep the packet's pinned-archive numbers *and* the numbers
    measured on this working tree as separate columns. Dropping either side
    is how two revisions get silently merged into one figure.
    """
    for hotspot in _HOTSPOTS:
        name = _hotspot_id(hotspot)
        assert isinstance(hotspot.get("packet_lines"), int), (
            f"{name}: missing the packet's own line figure"
        )
        assert isinstance(hotspot.get("packet_branch_nodes"), int), (
            f"{name}: missing the packet's own branch-node figure"
        )
        measured = hotspot.get("measured")
        assert isinstance(measured, dict) and measured.get("lines"), (
            f"{name}: missing the working-tree measurement"
        )


# ── The plan against the tree ───────────────────────────────────────────────


@requires_plan
@pytest.mark.parametrize("hotspot", _PARAMS, ids=_IDS)
def test_hotspot_still_resolves_uniquely(hotspot):
    """The named function still exists, at that path, and only once."""
    hotspot = _require(hotspot)
    rel = hotspot["path"]
    qual = hotspot["qualname"]

    assert (REPO_ROOT / rel).is_file(), (
        f"{_PLAN_PATH} points at {rel}, which no longer exists under "
        f"{REPO_ROOT}. Update the plan."
    )

    found = _resolve(rel, qual)
    assert len(found) == 1, (
        f"{rel}::{qual} resolves to {len(found)} definitions, expected 1. "
        f"Either the function was renamed or moved (update the plan's "
        f"hotspot entry) or a second definition now shadows it."
    )


@requires_plan
@pytest.mark.parametrize("hotspot", _PARAMS, ids=_IDS)
def test_hotspot_is_still_branch_heavy(hotspot):
    """A §5.3 hotspot that stopped being branch-heavy needs the plan revisited.

    This is an invariant, not a measurement snapshot: the floor sits far below
    every recorded value, so ordinary edits never trip it. It trips when the
    name now points at something structurally different — which is exactly
    when the seam analysis underneath it stops being true.
    """
    hotspot = _require(hotspot)
    node = _resolve(hotspot["path"], hotspot["qualname"])[0]
    count = _branchish(node)
    assert count >= BRANCHISH_FLOOR, (
        f"{hotspot['path']}::{hotspot['qualname']} now has {count} branching "
        f"AST nodes, below the {BRANCHISH_FLOOR} floor. If it was genuinely "
        f"decomposed, that is good news — re-do the seam analysis and update "
        f"the plan rather than leaving a stale entry behind."
    )


@requires_plan
@pytest.mark.parametrize("hotspot", _PARAMS, ids=_IDS)
def test_named_seams_still_exist(hotspot):
    """Every seam symbol the plan names still lives in the module it claims.

    A seam legitimately promoted from a closure to module scope *within the
    same file* still passes — that is the extraction this plan is for. A seam
    that was renamed, deleted, or moved to another module fails, and the plan
    must record where it went (``extracted_to``).
    """
    hotspot = _require(hotspot)
    rel = hotspot["path"]
    problems = []

    for seam in hotspot.get("seams", []):
        symbol = seam.get("symbol")
        if not symbol:
            continue  # a line-range seam (dispatch chain, env block) — no symbol
        target_path = rel
        expected = symbol
        if seam.get("extracted_to"):
            target_path, _, expected = seam["extracted_to"].partition("::")
            if not (REPO_ROOT / target_path).is_file():
                problems.append(
                    f"{symbol}: extracted_to names {target_path}, which does not exist"
                )
                continue

        matches = [
            qual
            for qual, _ in _parse(target_path)
            if qual == expected or qual.rsplit(".", 1)[-1] == expected
        ]
        if not matches:
            problems.append(
                f"{symbol} ({seam.get('kind', 'seam')}) not found anywhere in {target_path}"
            )

    assert not problems, (
        f"{_hotspot_id(hotspot)} — seams named in {_PLAN_PATH} no longer "
        f"resolve:\n  " + "\n  ".join(problems)
    )


@requires_plan
@pytest.mark.parametrize("hotspot", _PARAMS, ids=_IDS)
def test_hotspot_states_its_characterization_precondition(hotspot):
    """§5.3 orders characterization first, seams second.

    Every hotspot must say, in the plan, what coverage has to exist before it
    is touched. An entry without that is an invitation to refactor blind.
    """
    hotspot = _require(hotspot)
    required = hotspot.get("characterization_required")
    assert isinstance(required, list) and required, (
        f"{_hotspot_id(hotspot)} names no characterization coverage. §5.3's "
        f"prescribed order is characterization tests first, seam extraction "
        f"second; a hotspot with no stated precondition cannot be worked on."
    )
    assert all(isinstance(item, str) and item.strip() for item in required), (
        f"{_hotspot_id(hotspot)} has an empty characterization requirement"
    )
    assert "blocked_until_covered" in hotspot, (
        f"{_hotspot_id(hotspot)} does not say whether it is blocked on coverage"
    )


@requires_plan
@pytest.mark.parametrize("hotspot", _PARAMS, ids=_IDS)
def test_ambiguity_warnings_are_still_true(hotspot):
    """The plan disambiguates one packet name; keep that warning honest.

    The packet writes ``gateway/run.py::run_sync``, and the working tree has
    two nested functions by that name. If one is ever renamed the warning
    becomes noise, and the plan should be simplified rather than left standing.
    """
    hotspot = _require(hotspot)
    if not hotspot.get("packet_name_ambiguous"):
        return

    qual = hotspot["qualname"]
    assert "." in qual, (
        f"{_hotspot_id(hotspot)} is flagged ambiguous but recorded under a "
        f"bare name; record the fully-qualified form"
    )
    assert hotspot.get("disambiguation", "").strip(), (
        f"{_hotspot_id(hotspot)} is flagged ambiguous but records no "
        f"disambiguation reasoning"
    )

    short = qual.rsplit(".", 1)[-1]
    occurrences = _short_name_count(hotspot["path"], short)
    assert occurrences >= 2, (
        f"{hotspot['path']} now defines {short!r} only {occurrences} time(s), "
        f"so the ambiguity the plan warns about is gone. Drop the warning "
        f"instead of leaving a stale caution in the document."
    )


# ── The gate on recording an extraction ─────────────────────────────────────


@requires_plan
def test_recorded_extractions_are_real_and_covered():
    """An extraction may be recorded only once it exists *and* is covered.

    §5.3 makes characterization the precondition for seam extraction. This
    keeps the plan from becoming a place where an extraction is claimed before
    the evidence for it exists. It passes vacuously while nothing has been
    extracted; the gate is live the moment something is.
    """
    extractions = _INDEX.get("extractions_performed", [])
    assert isinstance(extractions, list)

    for entry in extractions:
        label = entry.get("symbol", "<unnamed>")

        target = entry.get("to", "")
        target_path, _, target_qual = target.partition("::")
        assert target_path and target_qual, (
            f"extraction {label}: 'to' must be 'relative/path.py::qualname', got {target!r}"
        )
        assert (REPO_ROOT / target_path).is_file(), (
            f"extraction {label}: {target_path} does not exist"
        )
        assert _resolve(target_path, target_qual), (
            f"extraction {label}: {target_qual} is not defined in {target_path}. "
            f"The plan records an extraction that did not happen."
        )

        covered_by = entry.get("covered_by")
        assert covered_by, (
            f"extraction {label}: no 'covered_by' characterization test recorded. "
            f"§5.3 orders characterization first — an extraction without it may "
            f"not be recorded as done."
        )
        assert (REPO_ROOT / covered_by).is_file(), (
            f"extraction {label}: covered_by names {covered_by}, which does not exist"
        )


# ── The premises the plan rests on ──────────────────────────────────────────


def test_july_refactor_warning_is_still_on_record():
    """The plan's risk ranking cites this repository's own warning.

    Asserted by content, not by line number, so ordinary edits to
    GAP_ANALYSIS.md do not trip it.
    """
    path = REPO_ROOT / "GAP_ANALYSIS.md"
    if not path.is_file():
        pytest.skip(f"{path} not present in this tree")
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "Don't refactor `run_agent.py` or `cli.py`" in text, (
        "GAP_ANALYSIS.md no longer carries the warning the seam plan cites as "
        "the reason cli.py hotspots are ranked as high-risk. If the warning "
        "was withdrawn, the plan's risk ranking must be revisited."
    )


def test_change_detector_rule_is_still_on_record():
    """The plan forbids change-detector tests by citing AGENTS.md."""
    path = REPO_ROOT / "AGENTS.md"
    if not path.is_file():
        pytest.skip(f"{path} not present in this tree")
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "Don't write change-detector tests" in text, (
        "AGENTS.md no longer carries the change-detector rule that this "
        "module and the seam plan both defer to."
    )
