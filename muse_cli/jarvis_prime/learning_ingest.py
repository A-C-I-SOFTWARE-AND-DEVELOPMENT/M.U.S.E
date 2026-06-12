"""Ingest bridges for the JARVIS Learning Dataset Pipeline.

These wire the pipeline to *existing* capture systems so traces are
collected end-to-end rather than hand-authored:

* :func:`from_trajectory_file` — reads a ``save_trajectory``-format JSONL
  (the ShareGPT trajectories Hermes already writes) and creates
  ``coding_task_trace`` / ``failed_attempt_trace`` candidates.
* :func:`from_research_artifact` — turns a Research Vault
  :class:`~muse_cli.jarvis_prime.research_vault.ResearchArtifact` into a
  ``research_answer_trace`` / ``evidence_verification_trace`` carrying the
  artifact's citation + evidence strength as provenance.

Nothing here re-implements trajectory capture or the research vault; it only
maps their output into validated dataset candidates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from muse_cli.jarvis_prime.learning_dataset import (
    NEGATIVE_EXAMPLE,
    DatasetCandidate,
    DatasetStore,
    Provenance,
    QualityGates,
    RejectedTrace,
    TraceType,
)
from muse_cli.jarvis_prime.memory_tree import SourceTrust


def from_trajectory_file(
    path: Path | str,
    store: DatasetStore,
    *,
    quality: Optional[QualityGates] = None,
    source_uri: str = "",
) -> list[DatasetCandidate]:
    """Ingest a ``save_trajectory``-format JSONL into the store.

    Each line is ``{"conversations": [...], "completed": bool, "model": ...}``.
    Completed trajectories become ``coding_task_trace`` candidates; failed
    ones become ``failed_attempt_trace`` candidates auto-labeled
    ``negative_example``. Filters (secret scrub, CoT strip) run inside
    :meth:`DatasetStore.add_candidate`; individual lines that fail a hard
    filter are skipped (recorded in ``store.load_diagnostics``) rather than
    aborting the whole file.
    """

    path = Path(path)
    created: list[DatasetCandidate] = []
    if not path.exists():
        return created

    src = source_uri or f"trajectory://{path.name}"
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as exc:
                store.load_diagnostics.append(f"{path.name}:{lineno}: {exc}")
                continue

            completed = bool(entry.get("completed", False))
            content = {
                "conversations": entry.get("conversations", []),
                "model": entry.get("model", ""),
                "timestamp": entry.get("timestamp", ""),
            }
            prov = Provenance(
                source_kind="trajectory",
                source_uri=src,
                trust=SourceTrust.REPUTABLE if completed else SourceTrust.COMMUNITY,
            )

            if completed:
                trace_type = TraceType.CODING_TASK
                labels: tuple[str, ...] = ()
                # A completed coding task needs the positive gates; the caller
                # supplies them (e.g. from a CI run). Default to unmet so we
                # never silently mint a "passed" example.
                q = quality or QualityGates()
            else:
                trace_type = TraceType.FAILED_ATTEMPT
                labels = (NEGATIVE_EXAMPLE,)
                q = quality or QualityGates()

            try:
                created.append(
                    store.add_candidate(
                        trace_type,
                        content,
                        prov,
                        q,
                        labels=labels,
                        task_key=str(entry.get("timestamp", "") or f"{path.name}:{lineno}"),
                        persist=False,
                    )
                )
            except RejectedTrace as exc:
                store.load_diagnostics.append(
                    f"{path.name}:{lineno}: rejected — {exc}"
                )

    if created:
        store.save()
    return created


def from_research_artifact(
    artifact,
    store: DatasetStore,
    *,
    question: str,
    answer: str = "",
    citations_verified: bool = False,
    evidence: bool = False,
) -> DatasetCandidate:
    """Create a research/evidence trace from a Research Vault artifact.

    ``artifact`` is a
    :class:`muse_cli.jarvis_prime.research_vault.ResearchArtifact`. Its
    ``source_uri``/``evidence_strength`` become provenance; the citation is
    recorded so every exported eval case is source-backed.

    Set ``evidence=True`` for an ``evidence_verification_trace`` (a check of
    a claim against a source) vs the default ``research_answer_trace``.
    """

    trace_type = (
        TraceType.EVIDENCE_VERIFICATION if evidence else TraceType.RESEARCH_ANSWER
    )
    prov = Provenance(
        source_kind="research_vault",
        source_uri=getattr(artifact, "source_uri", ""),
        citations=(getattr(artifact, "source_uri", ""),)
        if getattr(artifact, "source_uri", "")
        else (),
        trust=artifact.evidence_strength.trust,
    )
    content = {
        "question": question,
        "answer": answer or getattr(artifact, "summary", ""),
        "excerpt": getattr(artifact, "excerpt", ""),
        "title": getattr(artifact, "title", ""),
    }
    quality = QualityGates(citations_verified=citations_verified)
    return store.add_candidate(trace_type, content, prov, quality)
