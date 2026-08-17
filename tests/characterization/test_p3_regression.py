"""Characterization + regression tests for the P3 SWE-bench smoke run.

Two linked defects from the M.U.S.E. Work Packet are pinned here.

**1. The P3 constructor TypeError (§1 p4).**
``.hermes/research_fabric/smoke/p3_run.log`` ends with::

    File "C:\\Users\\Echer\\M.U.S.E\\scripts\\research_fabric\\p3_swe_bench.py", line 519, in main
        cand = Candidate(
    TypeError: Candidate.__init__() missing 3 required positional arguments:
    'target_path', 'risk_class', and 'domain_scores'

The live 5-task suite had already scored 5/5 by then; the crash was in the
*auto_apply bundle step* that runs afterwards.  Two facts make that path easy
to break and hard to notice:

* ``--dry-run`` returns before the block that builds the ``Candidate``, so the
  offline smoke mode never exercised the line that raised.  Only a **live** run
  (network + ``NVIDIA_API_KEY`` + ~14 minutes of queue-bound NIM calls) reached
  it.
* nothing in the test suite constructed a ``Candidate`` from the harness.

``test_recorded_typeerror_still_reproduces_from_the_pre_fix_argument_set``
reproduces the recorded exception exactly, and the two tests after it prove the
current call site is complete -- statically (every required dataclass field is
passed) and dynamically (the harness is actually run offline, end to end, and
the constructed ``Candidate`` captured).

**2. The 5/5-versus-2/2 mutable-baseline drift (§11, §12.1, §12.2).**
``P3_STATUS.md`` and ``p3_run.log`` record ``resolved_rate=1.0 (5/5)`` over the
five built-in fixture tasks; the ``P3_BASELINE.json`` still on disk holds
``task_count: 2`` over two task ids (``swe-verified-test-001/002``) that do not
exist in the harness.  A later ``--suite`` run overwrote the file, because the
harness writes one constant filename with no run id.  The correct outcome is a
recorded finding plus a test that fails if the artifact is overwritten again --
**not** a rewritten baseline.  See ``muse-dsh/docs/P3_RECONCILIATION.md``.

Nothing here needs the network, an API key, or a GPU.  ``drive_candidate`` is
stubbed in every test that runs the harness: the real one creates a git branch.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "research_fabric" / "p3_swe_bench.py"
SMOKE_DIR = REPO_ROOT / ".hermes" / "research_fabric" / "smoke"
CORPUS_DIR = REPO_ROOT / ".hermes" / "research_fabric" / "corpus"

# LF-normalized SHA-256 of the artifacts as they stand.  Normalizing line
# endings keeps the pin stable across a Windows autocrlf checkout; it does not
# weaken the pin, because every drift documented here is a content change.
PINNED_SHA256 = {
    "P3_BASELINE.json": "971e79f89ca1f88cfed063514fbf852c0a29491bc3c99839cde2dbf4e35e126c",
    "P3_AUTO_APPLY.json": "d96070d21bfab85059d6ccaa6608e4246908c9c4c315f24c7bb2ec53d4b678d6",
    "p3_run.log": "6ccb99d4a8b9c3c8e03606c96a9ab0c001bae8e3bdffd16f7adf3a418a594ee2",
}

_OVERWRITE_MSG = (
    "\n\n{name} changed. A P3 evidence artifact is not a scratch file: the "
    "harness writes one constant path with no run id, so re-running it "
    "DESTROYS the previous result -- which is exactly how the 5/5 fixture "
    "baseline was lost (muse-dsh/docs/P3_RECONCILIATION.md). If a new run was "
    "intended, write it to a fresh immutable run directory and leave this "
    "artifact alone; only then update the pin here, in the same change that "
    "updates the reconciliation note."
)

# The keyword set the pre-fix call used, deduced from the recorded exception:
# it named exactly target_path, risk_class and domain_scores as missing, so
# everything else the current call site passes was already there.
_PRE_FIX_KWARGS = ("candidate_id", "kind", "holdout_scores", "eval_win_rate", "diff_text", "note")

_RECORDED_TYPEERROR = (
    "Candidate.__init__() missing 3 required positional arguments: "
    "'target_path', 'risk_class', and 'domain_scores'"
)

# Deterministic stand-ins for the model's patches.  The two adversarial tasks
# (ok_max.py, ok_flatten.py) are already correct and must be returned unchanged.
_OFFLINE_PATCHES = {
    "calc.py": "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n",
    "strings.py": "def reverse_words(s):\n    return ' '.join(reversed(s.split()))\n",
    "stats.py": "def mean(xs):\n    return sum(xs) / len(xs) if xs else 0.0\n",
}


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"P3 evidence artifact not present in this checkout: {path}")
    return path


def _load_harness():
    """Import ``scripts/research_fabric/p3_swe_bench.py`` as a module.

    It lives outside any package, so it is loaded by path.  Import is
    side-effect-light: it only ``mkdir(exist_ok=True)``s the smoke directory.
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("p3_swe_bench_under_test", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _required_candidate_fields(candidate_cls) -> set[str]:
    """Dataclass fields with no default -- the ones a call site must pass."""
    required = set()
    for f in dataclasses.fields(candidate_cls):
        no_default = f.default is dataclasses.MISSING
        no_factory = f.default_factory is dataclasses.MISSING  # type: ignore[misc]
        if no_default and no_factory:
            required.add(f.name)
    return required


def _candidate_call_keywords(source: str) -> list[set[str]]:
    """Every ``Candidate(...)`` call in ``source``, as its keyword-name set."""
    tree = ast.parse(source)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "Candidate":
                calls.append({kw.arg for kw in node.keywords if kw.arg is not None})
    return calls


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


@pytest.fixture(scope="module")
def offline_live_run(harness, tmp_path_factory):
    """Run the harness's *live* code path end to end, offline.

    This is the path ``--dry-run`` skips, and the one that raised the recorded
    TypeError.  Redirected so nothing in the real repo is touched:

    * ``REPO`` / ``STATE_DIR`` -> a temp tree (the fixture repo and the
      ``P3_BASELINE.json`` / ``P3_AUTO_APPLY.json`` writes land there);
    * ``nim_fix`` -> a deterministic offline fixer (no network, no API key);
    * ``drive_candidate`` -> a capturing stub (the real one creates a git
      branch and commits).
    """
    tmp = tmp_path_factory.mktemp("p3_live_path")
    captured: dict = {}

    def offline_fixer(task, current):
        return _OFFLINE_PATCHES.get(task.target_path, current)

    def capturing_drive(repo_root, candidate, packet, evidence_bundle, **kwargs):
        captured["repo_root"] = repo_root
        captured["candidate"] = candidate
        captured["packet"] = packet
        captured["bundle"] = evidence_bundle
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            decision="stubbed-offline",
            applied=False,
            rolled_back=False,
            rationale="offline regression stub; no branch, no commit, no ledger write",
            gate_overall=None,
            ledger_record_hash="stub",
            extra={},
        )

    state_dir = tmp / "repo" / ".hermes" / "research_fabric" / "smoke"
    state_dir.mkdir(parents=True)

    saved = (harness.REPO, harness.STATE_DIR, harness.nim_fix, harness.drive_candidate, sys.argv)
    harness.REPO = tmp / "repo"
    harness.STATE_DIR = state_dir
    harness.nim_fix = offline_fixer
    harness.drive_candidate = capturing_drive
    sys.argv = ["p3_swe_bench.py"]  # no --dry-run, no --suite => the live path
    try:
        rc = harness.main()
    finally:
        (harness.REPO, harness.STATE_DIR, harness.nim_fix,
         harness.drive_candidate, sys.argv) = saved

    captured["returncode"] = rc
    captured["state_dir"] = state_dir
    captured["baseline"] = json.loads((state_dir / "P3_BASELINE.json").read_text(encoding="utf-8"))
    return captured


# --------------------------------------------------------------------------- #
# 1. The constructor TypeError
# --------------------------------------------------------------------------- #

def test_recorded_typeerror_still_reproduces_from_the_pre_fix_argument_set(harness):
    """The recorded failure, reproduced verbatim.

    ``Candidate`` still requires the three fields the crashing call omitted, so
    the diagnosis in ``p3_run.log`` is the whole story: the call site was
    incomplete, the dataclass was not at fault.
    """
    from hermes_cli.jarvis_prime.research_fabric.controller import Candidate
    from hermes_cli.jarvis_prime.self_update import ProposalKind

    scores = {"swe": 1.0}
    with pytest.raises(TypeError) as excinfo:
        Candidate(  # type: ignore[call-arg]  # deliberately the pre-fix call
            candidate_id="p3-swe-local-001",
            kind=ProposalKind.SKILL_UPDATE,
            holdout_scores=scores,
            eval_win_rate=1.0,
            diff_text="def add(a, b):\n    return a + b\n",
            note="p3 SWE fix for calc.py",
        )

    assert str(excinfo.value) == _RECORDED_TYPEERROR, (
        "the exception text no longer matches p3_run.log line 40; the "
        "characterization above needs updating before this is called fixed"
    )
    # And the pre-fix kwargs really are a subset of what the harness passes now.
    assert set(_PRE_FIX_KWARGS) <= _candidate_call_keywords(
        HARNESS_PATH.read_text(encoding="utf-8")
    )[0]


def test_harness_candidate_call_site_passes_every_required_field(harness):
    """Static guard: the fix cannot silently regress.

    Derives the required field set from the dataclass, so adding a new
    no-default field to ``Candidate`` fails here rather than in a live run
    fourteen minutes and one API quota later.
    """
    from hermes_cli.jarvis_prime.research_fabric.controller import Candidate

    required = _required_candidate_fields(Candidate)
    assert required == {"candidate_id", "kind", "target_path", "risk_class", "domain_scores"}

    calls = _candidate_call_keywords(HARNESS_PATH.read_text(encoding="utf-8"))
    assert len(calls) == 1, f"expected exactly one Candidate(...) call in the harness, got {len(calls)}"
    missing = required - calls[0]
    assert not missing, (
        f"{HARNESS_PATH.name} constructs Candidate without {sorted(missing)} -- "
        "this is the exact shape of the failure recorded in p3_run.log"
    )


def test_the_static_guard_would_have_caught_the_original_call_site():
    """The guard above is not vacuous.

    Fed a reconstruction of the pre-fix call site, it reports exactly the three
    names the recorded ``TypeError`` reported -- so it fails on the historical
    defect and passes on the current source, rather than passing on both.
    """
    from hermes_cli.jarvis_prime.research_fabric.controller import Candidate

    pre_fix_source = (
        "cand = Candidate(\n"
        "    candidate_id=f'p3-{spec.task_id}',\n"
        "    kind=ProposalKind.SKILL_UPDATE,\n"
        "    holdout_scores=domain_scores,\n"
        "    eval_win_rate=1.0,\n"
        "    diff_text=candidate_content,\n"
        "    note='p3 SWE fix',\n"
        ")\n"
    )
    [keywords] = _candidate_call_keywords(pre_fix_source)
    assert keywords == set(_PRE_FIX_KWARGS)

    missing = _required_candidate_fields(Candidate) - keywords
    assert missing == {"target_path", "risk_class", "domain_scores"}
    for name in sorted(missing):
        assert f"'{name}'" in _RECORDED_TYPEERROR


def test_live_path_constructs_a_complete_candidate(offline_live_run):
    """Dynamic proof: the line that raised now runs and yields a real object."""
    from hermes_cli.jarvis_prime.research_fabric.controller import Candidate
    from hermes_cli.jarvis_prime.self_update import ProposalKind

    assert offline_live_run["returncode"] == 0
    cand = offline_live_run["candidate"]
    assert isinstance(cand, Candidate)
    assert cand.candidate_id == "p3-swe-local-001"
    assert cand.kind is ProposalKind.SKILL_UPDATE
    # The three formerly-missing fields, populated:
    assert cand.target_path == ".hermes/research_fabric/auto_applied/p3-swe-local-001-fix.py"
    assert cand.risk_class == "RC1"
    assert dict(cand.domain_scores)["swe"] == 1.0
    assert set(dict(cand.domain_scores)) >= {
        "code_generation", "code_editing", "code_review",
        "software_development", "reasoning", "safety", "swe",
    }
    # The evidence bundle really was assembled, not faked.
    assert offline_live_run["bundle"].packet_id == "p3-swe-local-001"
    assert offline_live_run["packet"]["allowed_files"] == ["calc.py"]


def test_dry_run_never_reaches_the_candidate_construction(harness, tmp_path):
    """Why the bug escaped: the offline smoke mode skips the crashing block.

    ``--dry-run`` returns after writing the baseline, so no amount of
    ``--dry-run`` exercise could have caught the TypeError.  Pinned so that if
    someone later makes ``--dry-run`` cover the auto_apply path, this test
    fails and the note above gets corrected rather than quietly going stale.
    """
    calls: list = []

    def offline_fixer(task, current):
        return _OFFLINE_PATCHES.get(task.target_path, current)

    def refusing_drive(*args, **kwargs):
        calls.append(args)
        raise AssertionError("drive_candidate must not run under --dry-run")

    state_dir = tmp_path / "repo" / ".hermes" / "research_fabric" / "smoke"
    state_dir.mkdir(parents=True)

    saved = (harness.REPO, harness.STATE_DIR, harness.nim_fix, harness.drive_candidate, sys.argv)
    harness.REPO = tmp_path / "repo"
    harness.STATE_DIR = state_dir
    harness.nim_fix = offline_fixer
    harness.drive_candidate = refusing_drive
    sys.argv = ["p3_swe_bench.py", "--dry-run"]
    try:
        rc = harness.main()
    finally:
        (harness.REPO, harness.STATE_DIR, harness.nim_fix,
         harness.drive_candidate, sys.argv) = saved

    assert rc == 0
    assert calls == []
    report = json.loads((state_dir / "P3_BASELINE.json").read_text(encoding="utf-8"))
    assert report["model"] == "dry-run"
    assert not (state_dir / "P3_AUTO_APPLY.json").exists()


# --------------------------------------------------------------------------- #
# 2. Mutable-artifact drift: 5/5 versus 2/2
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", sorted(PINNED_SHA256))
def test_p3_evidence_artifact_is_not_overwritten(name):
    """Fail if a P3 evidence artifact changes.

    This is the §12.2 guard the harness itself does not provide: it writes one
    constant filename per artifact, unconditionally, with no run id and no
    manifest, so every re-run silently replaces the previous evidence.
    """
    path = _require(SMOKE_DIR / name)
    assert _sha256_lf(path) == PINNED_SHA256[name], _OVERWRITE_MSG.format(name=name)


def test_stored_baseline_counts_a_different_experiment_than_the_log(offline_live_run):
    """The 2/2 in the file is not a shrunken 5/5 -- it is another suite.

    Both are ``resolved_rate == 1.0``, which is exactly why averaging or
    "correcting" them would destroy the finding.  What differs is the
    denominator's *identity*: the fixture suite's five task ids are defined in
    the harness source, and none of them appears in the stored artifact.
    """
    stored = json.loads(_require(SMOKE_DIR / "P3_BASELINE.json").read_text(encoding="utf-8"))
    assert stored["task_count"] == 2
    assert stored["resolved_rate"] == 1.0
    stored_ids = {o["task_id"] for o in stored["outcomes"]}
    assert stored_ids == {"swe-verified-test-001", "swe-verified-test-002"}

    # Re-derived offline from the harness itself, this run, no network:
    fixture = offline_live_run["baseline"]
    assert fixture["task_count"] == 5
    assert fixture["resolved_rate"] == 1.0
    fixture_ids = {o["task_id"] for o in fixture["outcomes"]}
    assert fixture_ids == {f"swe-local-00{i}" for i in range(1, 6)}

    assert stored_ids.isdisjoint(fixture_ids), (
        "the stored baseline would have to share task ids with the fixture "
        "suite for 2/2 to be a subset of 5/5; it shares none"
    )

    log = _require(SMOKE_DIR / "p3_run.log").read_text(encoding="utf-8")
    assert "resolved_rate=1.0 (5/5)" in log
    assert "P3_BASELINE.json" in log  # the log names the file the 5/5 was written to
    for tid in sorted(fixture_ids):
        assert f"[PASS] {tid}" in log


def test_the_run_that_produced_the_stored_baseline_is_unreproducible():
    """Nothing on disk identifies the ``--suite`` input that produced the 2/2.

    No suite path, no suite hash, no row count, no per-task model, no repo
    provenance -- and the two task ids appear in no other file in the tree.
    This is the §14.3 manifest gap, observed rather than argued.
    """
    stored = json.loads(_require(SMOKE_DIR / "P3_BASELINE.json").read_text(encoding="utf-8"))
    for absent in ("suite", "suite_path", "suite_sha256", "run_id", "manifest", "repo_sha", "timestamp"):
        assert absent not in stored, f"{absent!r} is present after all -- update the finding"

    # The task ids exist nowhere else under the repo. Vendored/virtualenv trees
    # are pruned during the walk rather than filtered afterwards -- descending
    # into .venv costs minutes and finds nothing.
    needle = "swe-verified-test"
    pruned = {".venv", "venv", ".git", "node_modules", "__pycache__",
              "site-packages", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
    hits = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in pruned]
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = Path(dirpath) / filename
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                if needle in path.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(path)
            except OSError:
                continue
    assert [p.name for p in hits] == ["P3_BASELINE.json"], (
        f"expected the stored baseline to be the only trace of {needle!r}; found {hits}"
    )


def test_auto_apply_artifact_drifted_away_from_the_status_note():
    """The same overwrite defect, caught a second time on a second artifact.

    ``P3_STATUS.md`` narrates ``decision=auto_applied applied=True gate=pass``
    with ledger hash ``4777b44d...``; ``P3_AUTO_APPLY.json`` holds a *blocked*
    decision with hash ``8983beb3...``.  Both are true of different runs; the
    mutable file simply kept the last one.
    """
    status = _require(SMOKE_DIR / "P3_STATUS.md").read_text(encoding="utf-8")
    stored = json.loads(_require(SMOKE_DIR / "P3_AUTO_APPLY.json").read_text(encoding="utf-8"))

    assert "decision=auto_applied applied=True gate=pass" in status
    assert "4777b44d" in status

    assert stored["decision"] == "blocked"
    assert stored["applied"] is False
    assert stored["gate_overall"] is None
    assert stored["ledger_record_hash"].startswith("8983beb3")
    assert not stored["ledger_record_hash"].startswith("4777b44d"), (
        "the file now matches the status note; if a run genuinely reconciled "
        "them, record it and update P3_RECONCILIATION.md"
    )


def test_append_only_corpus_retained_what_the_mutable_files_lost():
    """The fix pattern, already present in the same tree.

    ``.hermes/research_fabric/corpus/`` names every record
    ``<UTC timestamp>-<candidate id>.json`` and appends, so both decisions the
    mutable artifacts disagree about are still there, in order, with their
    ledger hashes.  That is what §12.2 asks the benchmark artifacts to do.
    """
    if not CORPUS_DIR.is_dir():
        pytest.skip(f"corpus directory not present in this checkout: {CORPUS_DIR}")

    records = []
    for path in sorted(CORPUS_DIR.glob("*-p3-swe-local-001.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        records.append((data["ts"], data["outcome"]["decision"],
                        (data["outcome"]["ledger_record_hash"] or "")[:8]))

    assert len(records) >= 8, f"expected the full P3 decision history, got {len(records)}"
    assert records == sorted(records), "corpus filenames must sort in decision order"

    by_hash = {h: (ts, dec) for ts, dec, h in records}
    # The decision P3_STATUS.md quotes, preserved:
    assert by_hash["4777b44d"] == ("20260720T200424Z", "auto_applied")
    # The decision P3_AUTO_APPLY.json kept, also preserved:
    assert by_hash["8983beb3"] == ("20260720T212825Z", "blocked")
    # And the one neither mutable artifact mentions: the harness's own last run
    # passed the ratchet and was then rolled back by the canary.
    assert by_hash["ce33996d"] == ("20260720T212820Z", "rolled_back")


def test_baseline_model_field_names_the_head_of_chain_not_the_answering_model(offline_live_run):
    """Why ``model`` in the artifact cannot attribute the 2/2 to anything.

    The harness stamps ``NIM_CHAIN[0]`` into the report regardless of which
    model answered.  Proven here at the limit: this run made **no model call at
    all**, and the field still names the head of the chain.  ``p3_run.log``
    shows the same gap live -- every one of the five calls was answered by
    ``nemotron-49b`` after the head timed out twice.
    """
    fixture = offline_live_run["baseline"]
    assert fixture["model"] == "meta/llama-3.3-70b-instruct"
    log = _require(SMOKE_DIR / "p3_run.log").read_text(encoding="utf-8")
    assert "[p3] LIVE: NIM meta/llama-3.3-70b-instruct" in log
    assert "answered by nvidia/llama-3.3-nemotron-super-49b-v1.5" in log
    assert "meta/llama-3.3-70b-instruct attempt 2/2: The read operation timed out" in log
