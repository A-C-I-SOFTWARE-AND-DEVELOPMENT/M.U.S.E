"""Phase 6 — the trust scorecard and autonomy bands: trust is measured
from outside (accuracy, promise-keeping, Brier calibration), autonomy
is earned per capability, and one high-severity gate failure demotes
immediately. EXIT GATE: a seeded calibration regression auto-demotes.
"""

from __future__ import annotations

import pytest

from axiom.core.ledger import Ledger
from axiom.governance.bands import B0, B1, BandManager
from axiom.governance.scorecard import TrustScorecard
from axiom.governance.sovereignty import Sovereignty


# ------------------------------------------------------------ 6.1 scorecard

def test_scorecard_accuracy_brier_promise():
    sc = TrustScorecard(":memory:")
    # Four calibrated, correct predictions; one honest miss.
    for conf, outcome in [(0.9, True), (0.8, True), (0.9, True),
                          (0.1, False), (0.7, False)]:
        sc.record_prediction("deploy", confidence=conf, outcome=outcome)
    sc.record_promise("deploy", kept=True)
    sc.record_promise("deploy", kept=True)
    sc.record_promise("deploy", kept=False)

    stats = sc.stats("deploy")
    assert stats["n_predictions"] == 5
    assert stats["accuracy"] == pytest.approx(4 / 5)
    expected_brier = ((0.9 - 1) ** 2 + (0.8 - 1) ** 2 + (0.9 - 1) ** 2
                      + (0.1 - 0) ** 2 + (0.7 - 0) ** 2) / 5
    assert stats["brier"] == pytest.approx(expected_brier)
    assert stats["promise_rate"] == pytest.approx(2 / 3)


def test_scorecard_rolling_window():
    sc = TrustScorecard(":memory:")
    for _ in range(50):
        sc.record_prediction("x", confidence=0.1, outcome=True)  # bad
    for _ in range(20):
        sc.record_prediction("x", confidence=0.95, outcome=True)  # good
    stats = sc.stats("x", window=20)
    assert stats["accuracy"] == 1.0
    assert stats["brier"] == pytest.approx(0.0025)


# ----------------------------------------------------------------- 6.2 bands

def _good_window(sc, capability, n=20):
    for _ in range(n):
        sc.record_prediction(capability, confidence=0.95, outcome=True)
        sc.record_promise(capability, kept=True)


def test_band_promotion_needs_rolling_window_and_is_ledgered():
    ledger = Ledger(":memory:")
    sc = TrustScorecard(":memory:")
    bm = BandManager(sc, ledger)
    assert bm.band("deploy") == B0  # autonomy starts at zero

    # Too few samples: no promotion, however good.
    sc.record_prediction("deploy", confidence=0.95, outcome=True)
    assert bm.evaluate("deploy") == B0

    _good_window(sc, "deploy")
    assert bm.evaluate("deploy") == B1
    transitions = ledger.events("band_transition")
    assert transitions and transitions[-1]["payload"] == {
        "capability": "deploy", "from": B0, "to": B1, "reason": "promotion",
    }


def test_high_severity_gate_failure_demotes_immediately():
    ledger = Ledger(":memory:")
    sc = TrustScorecard(":memory:")
    bm = BandManager(sc, ledger)
    _good_window(sc, "deploy")
    assert bm.evaluate("deploy") == B1

    bm.gate_failure("deploy", severity="high")
    assert bm.band("deploy") == B0  # immediate, no window debate
    t = ledger.events("band_transition")[-1]["payload"]
    assert t["reason"] == "high-severity gate failure"

    # Low severity does not demote by itself.
    _good_window(sc, "deploy")
    bm.evaluate("deploy")
    bm.gate_failure("deploy", severity="low")
    assert bm.band("deploy") == B1


def test_seeded_calibration_regression_auto_demotes():
    """EXIT GATE: confident-and-wrong predictions demote the band."""
    ledger = Ledger(":memory:")
    sc = TrustScorecard(":memory:")
    bm = BandManager(sc, ledger)
    _good_window(sc, "research")
    assert bm.evaluate("research") == B1

    # Seed the regression: overconfident and wrong, repeatedly.
    for _ in range(20):
        sc.record_prediction("research", confidence=0.95, outcome=False)
        sc.record_promise("research", kept=True)
    assert bm.evaluate("research") == B0  # auto-demotion
    t = ledger.events("band_transition")[-1]["payload"]
    assert t["from"] == B1 and t["to"] == B0
    assert "calibration" in t["reason"]
    assert ledger.verify_chain() is True


# ----------------------------------------------------------- 6.3 sovereignty

def test_sovereignty_clauses_and_coverage():
    sov = Sovereignty()

    # Clause 1: interruption threshold (stub) — always interruptible.
    assert sov.check_interruptible({"action": "long_job"}) is True

    # Clause 2: decisions carry their why.
    assert sov.check_decision_has_why(
        {"decision": "use sqlite", "why": "zero ops burden"}) is True
    assert sov.check_decision_has_why({"decision": "use sqlite"}) is False

    # Clause 3: the oracle check — no confident answer without an
    # attestation reference.
    assert sov.check_answer(confidence=0.95, attestation_ref="ab12") is True
    assert sov.check_answer(confidence=0.95, attestation_ref=None) is False
    assert sov.check_answer(confidence=0.5, attestation_ref=None) is True

    cov = sov.coverage()
    assert cov["interruption"]["checked"] == 1
    assert cov["interruption"]["violations"] == 0
    assert cov["why_attached"]["checked"] == 2
    assert cov["why_attached"]["violations"] == 1
    assert cov["oracle"]["checked"] == 3
    assert cov["oracle"]["violations"] == 1
