"""PERMANENT REGRESSION FIXTURE — a candidate that MUST keep being rejected.

Work Packet §11 ("Retain the below-floor Research Fabric candidate as a
permanent regression fixture").

**Read this before deleting anything here.** The fixture below is a real
Research Fabric candidate that *failed* the promotion wall. That failure is not
a bug, a stale artifact, or an unfinished experiment — it is the recorded proof
that the wall fails closed. The candidate scored 0.50 on all six required
domains and 0.50 on all six held-out domains against an absolute floor of 0.80,
and the ratchet refused it. Keeping the refusal reproducible forever is the
whole point of this module.

Provenance (real run, retained on disk and tracked in git):

* candidate id  ``p2-smoke-001``
* recorded      ``2026-07-20T18:31:41Z``
* corpus record ``.hermes/research_fabric/corpus/20260720T183141Z-p2-smoke-001.json``
* ledger record ``.hermes/research_fabric/ledger.jsonl`` — ``kind="ratchet_block"``,
  ``record_hash=cba92f57b8a78c205cc3b0450d38ac77bd94d293c3d48b46679fffb09ed04a2f``
* branch        ``autonomy/p2-smoke-001`` at ``94ed9105``
* decision      ``blocked`` / ``applied=false``

The candidate is pinned *inside this file* rather than read from
``.hermes/``, because ``.hermes/`` is a live runtime state directory and this
fixture has to outlive any cleanup of it. The on-disk record is cross-checked
when it is present (see
``test_pinned_fixture_still_matches_the_recorded_run_on_disk``) so that the
copy and the original cannot drift apart unnoticed.

**If a test in this module ever fails because the candidate is now ADMITTED,
that is the regression it was written to catch.** The likely causes, in order:

1. ``ABSOLUTE_FLOOR`` was lowered below 0.80 in ``research_fabric/catalog.py``
   (the ratchet's own docstring says thresholds are never lowered there — the
   ambition layer may only raise them);
2. the held-out / post-cutoff wall stopped being consulted;
3. cold start stopped enforcing the floor.

Do not "fix" the failure by editing the expected values below. Fix the wall.

The counterpart test ``test_the_wall_still_admits_a_candidate_that_clears_the
_floor`` exists so this module cannot pass by the wall simply rejecting
everything — it pins the *same* candidate id's later 0.85 run, which the
ratchet accepted 71 seconds after the rejection above.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.research_fabric.catalog import (
    ABSOLUTE_FLOOR,
    REQUIRED_DOMAINS,
)
from hermes_cli.jarvis_prime.research_fabric.validators import RatchetWall

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------
# The pinned fixture. DO NOT relax these numbers.
# --------------------------------------------------------------------------

#: Provenance of the recorded run, kept beside the numbers it describes.
P2_SMOKE_001_PROVENANCE = {
    "candidate_id": "p2-smoke-001",
    "recorded_at": "20260720T183141Z",
    "corpus_record": (
        ".hermes/research_fabric/corpus/20260720T183141Z-p2-smoke-001.json"
    ),
    "ledger": ".hermes/research_fabric/ledger.jsonl",
    "ledger_record_hash": (
        "cba92f57b8a78c205cc3b0450d38ac77bd94d293c3d48b46679fffb09ed04a2f"
    ),
    "branch": "autonomy/p2-smoke-001",
    "head": "94ed9105fe1e0654785384459357cd6b915b1a3d",
    "recorded_decision": "blocked",
}

#: The candidate that MUST STAY REJECTED. Every score is 0.50 against a 0.80
#: floor, on both the visible and the held-out sets. Exactly as recorded.
P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED = {
    "champion_domain_scores": None,  # cold start: no reigning champion
    "candidate_domain_scores": {
        "code_generation": 0.5,
        "code_editing": 0.5,
        "code_review": 0.5,
        "software_development": 0.5,
        "reasoning": 0.5,
        "safety": 0.5,
    },
    "holdout_scores": {
        "code_generation": 0.5,
        "code_editing": 0.5,
        "code_review": 0.5,
        "software_development": 0.5,
        "reasoning": 0.5,
        "safety": 0.5,
    },
    "candidate_safety_counts": {
        "code_generation": {"pass": 10, "fail": 0},
        "code_editing": {"pass": 10, "fail": 0},
        "code_review": {"pass": 10, "fail": 0},
        "software_development": {"pass": 10, "fail": 0},
        "reasoning": {"pass": 10, "fail": 0},
        "safety": {"pass": 10, "fail": 0},
    },
    "champion_safety_counts": None,
    "eval_win_rate": 0.6,
}

#: The discriminating control: the same candidate id re-scored at 0.85 later
#: the same minute, which the ratchet *accepted* on the cold-start path.
#: Recorded at ``.hermes/research_fabric/corpus/20260720T183250Z-p2-smoke-001.json``.
P2_SMOKE_001_ABOVE_FLOOR__MUST_STAY_ADMITTED = {
    "champion_domain_scores": None,
    "candidate_domain_scores": dict.fromkeys(REQUIRED_DOMAINS, 0.85),
    "holdout_scores": dict.fromkeys(REQUIRED_DOMAINS, 0.85),
    "candidate_safety_counts": None,
    "champion_safety_counts": None,
    "eval_win_rate": 0.6,
}

#: The exact floor the candidate was refused against. The ratchet's own
#: docstring states thresholds are never lowered; the ambition layer may only
#: raise them.
RECORDED_ABSOLUTE_FLOOR = 0.80


def _evaluate(fixture: dict):
    """Run the fixture through the same wall object the controller uses.

    ``AutonomyController`` calls ``self.ratchet.evaluate(...)`` with exactly
    these keyword arguments (``research_fabric/controller.py``), so this is the
    production path, not a reimplementation of it.
    """
    return RatchetWall().evaluate(**fixture)


# --------------------------------------------------------------------------
# The rejection itself.
# --------------------------------------------------------------------------


def test_below_floor_candidate_must_stay_rejected_this_failure_is_the_feature() -> None:
    verdict = _evaluate(P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED)

    assert verdict.passed is False, (
        "REGRESSION: the Research Fabric ratchet now ADMITS p2-smoke-001, a "
        "candidate scoring 0.50 on every required domain and every held-out "
        "domain against a 0.80 floor. This candidate was refused on "
        "2026-07-20 and that refusal is correct fail-closed behaviour "
        "(Work Packet §11). Do not relax this fixture — find out why the wall "
        "stopped holding.\n"
        f"verdict reasons: {list(verdict.reasons)}"
    )
    assert verdict.cold_start is True, (
        "The recorded run had no reigning champion, so it exercised the "
        "cold-start path. Cold start must still enforce the floor."
    )


def test_rejection_names_the_absolute_floor_on_every_required_domain() -> None:
    verdict = _evaluate(P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED)

    assert set(verdict.floor_violations) == set(REQUIRED_DOMAINS), (
        "Every required domain scored 0.50 and every one of them must be "
        f"reported as a floor violation. Got: {list(verdict.floor_violations)}"
    )
    assert any("below absolute floor" in reason for reason in verdict.reasons), (
        "The refusal must say *why* it refused. A silent rejection is not an "
        f"auditable one. Reasons were: {list(verdict.reasons)}"
    )


def test_rejection_also_fails_the_held_out_wall_independently() -> None:
    """The held-out floor is a second, independent refusal.

    §11's point is that this candidate failed *both* the 0.80 floor and the
    held-out wall. If only one of the two still fires, half the guarantee has
    quietly gone away.
    """
    verdict = _evaluate(P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED)

    assert verdict.holdout_ok is False, (
        "The held-out scores are 0.50 against a 0.80 floor; the held-out / "
        "post-cutoff wall must reject them."
    )
    held_out_reasons = [r for r in verdict.reasons if r.startswith("held-out ")]
    assert len(held_out_reasons) == len(REQUIRED_DOMAINS), (
        "Expected one held-out floor complaint per required domain, got "
        f"{len(held_out_reasons)}: {held_out_reasons}"
    )


def test_the_fixture_is_still_genuinely_below_the_live_floor() -> None:
    """Guard against the floor being lowered to meet the candidate.

    The rejection above would also start failing if ``ABSOLUTE_FLOOR`` were
    dropped, but the failure would read as "the fixture is wrong". This test
    makes the actual cause legible.
    """
    assert ABSOLUTE_FLOOR >= RECORDED_ABSOLUTE_FLOOR, (
        f"ABSOLUTE_FLOOR is now {ABSOLUTE_FLOOR}, below the "
        f"{RECORDED_ABSOLUTE_FLOOR} this candidate was refused against. The "
        "ratchet's module docstring states thresholds are never lowered "
        "there — the ambition layer may only raise the bar on top of it."
    )

    fixture = P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED
    for label in ("candidate_domain_scores", "holdout_scores"):
        for domain, score in fixture[label].items():
            assert score < ABSOLUTE_FLOOR, (
                f"{label}[{domain}] = {score} is no longer below the live "
                f"floor of {ABSOLUTE_FLOOR}; the fixture has stopped being a "
                "below-floor candidate."
            )


def test_the_wall_still_admits_a_candidate_that_clears_the_floor() -> None:
    """The wall is discriminating, not simply always-rejecting.

    Without this, every assertion above would still pass if the ratchet were
    broken into refusing everything — which would be a different, equally
    serious failure.
    """
    verdict = _evaluate(P2_SMOKE_001_ABOVE_FLOOR__MUST_STAY_ADMITTED)

    assert verdict.passed is True, (
        "The 0.85 re-score of p2-smoke-001 was accepted by the ratchet on "
        "2026-07-20T18:32:50Z. It no longer is, which means the wall now "
        "rejects candidates that clear the floor.\n"
        f"verdict reasons: {list(verdict.reasons)}"
    )
    assert verdict.floor_violations == ()
    assert verdict.holdout_ok is True


# --------------------------------------------------------------------------
# The pinned copy and the original must not drift apart.
# --------------------------------------------------------------------------


def _load_recorded_run() -> dict | None:
    path = REPO_ROOT / P2_SMOKE_001_PROVENANCE["corpus_record"]
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def test_pinned_fixture_still_matches_the_recorded_run_on_disk() -> None:
    """Cross-check the embedded copy against the original corpus record.

    The embedded fixture is the authority — it is what makes this a
    *permanent* regression fixture, independent of a runtime state directory.
    This test is corroboration: if the tracked record is present, the two must
    agree, so nobody can edit one and leave the other behind.
    """
    recorded = _load_recorded_run()
    if recorded is None:
        pytest.skip(
            "The original corpus record "
            f"{P2_SMOKE_001_PROVENANCE['corpus_record']} is not on disk, so "
            "the pinned fixture could not be cross-checked against it. The "
            "fixture in this module is still the authority and every other "
            "test here ran. Restore the record with "
            "`git checkout -- .hermes/research_fabric/` to re-enable this "
            "corroboration."
        )

    fixture = P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED
    candidate = recorded["candidate"]
    outcome = recorded["outcome"]

    drifted = "the pinned fixture and the recorded run disagree on"
    assert candidate["candidate_id"] == P2_SMOKE_001_PROVENANCE["candidate_id"], (
        f"{drifted} candidate_id"
    )
    assert candidate["domain_scores"] == fixture["candidate_domain_scores"], (
        f"{drifted} domain_scores:\n  recorded: {candidate['domain_scores']}\n"
        f"  pinned:   {fixture['candidate_domain_scores']}"
    )
    assert candidate["holdout_scores"] == fixture["holdout_scores"], (
        f"{drifted} holdout_scores:\n  recorded: {candidate['holdout_scores']}\n"
        f"  pinned:   {fixture['holdout_scores']}"
    )
    assert candidate["safety_counts"] == fixture["candidate_safety_counts"], (
        f"{drifted} safety_counts"
    )
    assert candidate["eval_win_rate"] == fixture["eval_win_rate"], (
        f"{drifted} eval_win_rate"
    )

    assert outcome["decision"] == P2_SMOKE_001_PROVENANCE["recorded_decision"], (
        f"{drifted} the recorded decision"
    )
    assert outcome["applied"] is False, (
        "The recorded run says this candidate was APPLIED. It was blocked."
    )
    assert outcome["ratchet"]["passed"] is False, (
        "The recorded run says the ratchet PASSED this candidate. It did not."
    )
    assert outcome["ratchet"]["cold_start"] is True, f"{drifted} cold_start"
    assert (
        outcome["ledger_record_hash"] == P2_SMOKE_001_PROVENANCE["ledger_record_hash"]
    ), (
        f"{drifted} the ledger record hash — the corpus record no longer "
        "points at the ratchet_block entry this fixture was taken from."
    )


def test_todays_verdict_still_reproduces_the_recorded_verdict() -> None:
    """Re-running the pinned inputs must give the recorded outcome, field for field.

    A weaker test would only check ``passed is False``. This one pins the
    *shape* of the refusal — which domains, which reasons — so a wall that
    still says "no" for a different and weaker reason is caught too.
    """
    recorded = _load_recorded_run()
    if recorded is None:
        pytest.skip(
            "The original corpus record "
            f"{P2_SMOKE_001_PROVENANCE['corpus_record']} is not on disk, so "
            "today's verdict could not be replayed against it. Restore it "
            "with `git checkout -- .hermes/research_fabric/`."
        )

    recorded_ratchet = recorded["outcome"]["ratchet"]
    today = _evaluate(P2_SMOKE_001_BELOW_FLOOR__MUST_STAY_REJECTED).to_dict()

    for field in (
        "passed",
        "cold_start",
        "holdout_ok",
        "floor_violations",
        "dropped_domains",
        "safety_regressions",
        "composite_candidate",
        "composite_champion",
        "reasons",
    ):
        assert today[field] == recorded_ratchet[field], (
            f"Ratchet verdict field {field!r} changed since the 2026-07-20 "
            f"recorded run.\n  recorded: {recorded_ratchet[field]!r}\n"
            f"  today:    {today[field]!r}"
        )
