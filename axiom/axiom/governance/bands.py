"""Autonomy bands B0–B3: autonomy is earned by measured trust, never
granted by assertion (Phase 6.2).

Promotion requires a full rolling window of good measurements.
Demotion is asymmetric by design: a calibration or accuracy regression
demotes on evaluation, and ONE high-severity gate failure demotes
immediately, with no window debate. Every transition is ledgered.
"""

from __future__ import annotations

from ..core.ledger import Ledger
from .scorecard import TrustScorecard

B0 = "B0"  # propose only
B1 = "B1"  # act with review
B2 = "B2"  # act, report after
B3 = "B3"  # act autonomously within constitution
BANDS = (B0, B1, B2, B3)

WINDOW = 20
PROMOTE_ACCURACY = 0.8
PROMOTE_BRIER = 0.15
PROMOTE_PROMISE = 0.9
DEMOTE_ACCURACY = 0.6
DEMOTE_BRIER = 0.25


class BandManager:
    """Per-capability autonomy bands driven by the scorecard."""

    def __init__(self, scorecard: TrustScorecard, ledger: Ledger):
        self.scorecard = scorecard
        self.ledger = ledger
        self._bands: dict[str, str] = {}

    def band(self, capability: str) -> str:
        return self._bands.get(capability, B0)

    def _transition(self, capability: str, to: str, reason: str) -> None:
        frm = self.band(capability)
        if frm == to:
            return
        self._bands[capability] = to
        self.ledger.append(
            "band_transition",
            {"capability": capability, "from": frm, "to": to,
             "reason": reason},
        )

    def evaluate(self, capability: str) -> str:
        """Re-derive the band from the rolling window. Returns the
        (possibly new) band."""
        stats = self.scorecard.stats(capability, window=WINDOW)
        current = self.band(capability)
        idx = BANDS.index(current)

        if stats["n_predictions"] >= WINDOW:
            if (stats["brier"] > DEMOTE_BRIER
                    or stats["accuracy"] < DEMOTE_ACCURACY):
                if idx > 0:
                    self._transition(
                        capability, BANDS[idx - 1],
                        reason=(f"calibration regression: brier="
                                f"{stats['brier']:.3f} accuracy="
                                f"{stats['accuracy']:.2f}"),
                    )
                return self.band(capability)
            if (stats["accuracy"] >= PROMOTE_ACCURACY
                    and stats["brier"] <= PROMOTE_BRIER
                    and stats["promise_rate"] >= PROMOTE_PROMISE
                    and idx < len(BANDS) - 1):
                self._transition(capability, BANDS[idx + 1],
                                 reason="promotion")
        return self.band(capability)

    def gate_failure(self, capability: str, severity: str) -> str:
        """One high-severity gate failure demotes immediately."""
        if severity == "high":
            idx = BANDS.index(self.band(capability))
            if idx > 0:
                self._transition(capability, BANDS[idx - 1],
                                 reason="high-severity gate failure")
        return self.band(capability)
