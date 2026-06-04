"""Audit report — aggregate verdicts, emit an ``audit_result`` artifact, record it.

The report aggregates per-seed verdicts into per-dimension scores and an overall
verdict, emits a content-addressed ``audit_result`` evidence artifact, and
appends a record to the hash-chained guardrail ledger (reusing
``guardrail_evidence``). Recording never mutates prior records — it only appends.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_AUDIT_RESULT,
    EvidenceArtifact,
    GuardrailDecisionRecord,
    GuardrailLedger,
)
from hermes_cli.jarvis_prime.self_audit.harness import Target, run_seed
from hermes_cli.jarvis_prime.self_audit.judge import (
    ClauseFinding,
    DimensionScore,
    SeedVerdict,
    aggregate_dimensions,
    judge,
)

_VERDICT_ORDER = {"approve": 0, "request_changes": 1, "blocked": 2}


def _gen_run_id() -> str:
    return "audit_" + uuid.uuid4().hex[:12]


@dataclass
class AuditReport:
    run_id: str
    constitution_version: str
    verdicts: list[SeedVerdict]

    def dimension_scores(self) -> dict[str, DimensionScore]:
        return aggregate_dimensions(self.verdicts)

    def violations(self) -> list[ClauseFinding]:
        return [f for v in self.verdicts for f in v.findings if not f.passed]

    @property
    def overall_verdict(self) -> str:
        worst = "approve"
        for v in self.verdicts:
            if _VERDICT_ORDER[v.verdict] > _VERDICT_ORDER[worst]:
                worst = v.verdict
        return worst

    def summary_payload(self) -> dict:
        viols = self.violations()
        return {
            "run_id": self.run_id,
            "constitution_version": self.constitution_version,
            "seed_count": len(self.verdicts),
            "overall_verdict": self.overall_verdict,
            "dimension_scores": {
                d: s.to_dict() for d, s in self.dimension_scores().items()
            },
            "violation_count": len(viols),
            "fatal_violations": sum(1 for f in viols if f.severity == "fatal"),
            "violations": [
                {
                    "clause_id": f.clause_id,
                    "dimension": f.dimension,
                    "severity": f.severity,
                }
                for f in viols
            ],
        }

    def to_artifact(self) -> EvidenceArtifact:
        """Emit a content-addressed ``audit_result`` evidence artifact."""

        return EvidenceArtifact.make(
            ARTIFACT_AUDIT_RESULT,
            producer="self_audit",
            subject=self.run_id,
            payload=self.summary_payload(),
        )

    def record(self, ledger: Optional[GuardrailLedger] = None) -> GuardrailDecisionRecord:
        """Append this audit to the hash-chained guardrail ledger."""

        ledger = ledger or GuardrailLedger()
        return ledger.append(
            kind=ARTIFACT_AUDIT_RESULT,
            subject=self.run_id,
            payload=self.summary_payload(),
        )


def run_report(
    seed_list,
    target: Target,
    *,
    grader=None,
    run_id: Optional[str] = None,
) -> AuditReport:
    """Run every seed against ``target``, judge each, and build the report."""

    verdicts = []
    for seed in seed_list:
        transcript = run_seed(seed, target)
        verdicts.append(judge(seed, transcript, grader=grader))
    return AuditReport(
        run_id=run_id or _gen_run_id(),
        constitution_version=constitution.version(),
        verdicts=verdicts,
    )
