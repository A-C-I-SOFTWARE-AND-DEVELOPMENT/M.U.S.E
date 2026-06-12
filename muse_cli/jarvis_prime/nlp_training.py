"""W9 — NL-compile fine-tuning export + prepare/dry-run harness.

Bridges the deterministic NL-compile pipeline
(:mod:`muse_cli.jarvis_prime.semantic_frontend` →
:mod:`muse_cli.jarvis_prime.ir_compilers`) into the **existing** owner-gated
learning-dataset pipeline (:mod:`muse_cli.jarvis_prime.learning_dataset`) and
prepares — *dry-run only* — a fine-tune job spec.

Two responsibilities, nothing more:

* :func:`export_compile_trace` — turn a verified NL-compile
  (:class:`~muse_cli.jarvis_prime.ir_compilers.base.CompileResult` + its
  :class:`~muse_cli.jarvis_prime.semantic_frontend.ParseResult`) into a
  :class:`~muse_cli.jarvis_prime.learning_dataset.DatasetCandidate`. The
  dataset store's hard filters scrub secrets / strip raw chain-of-thought and
  refuse anything unsafe; this module relies on them and additionally never
  puts a secret into the content it builds. Candidates land ``PENDING`` —
  owner approval stays a separate, explicit step.
* :func:`prepare_finetune_job` — export the owner-**approved** examples to a
  JSONL under ``out_dir`` and assemble a :class:`FinetuneJobSpec`. **It never
  launches a GPU training run.** ``launch=True`` is refused unless a valid
  owner grant *and* an external runner are configured — neither is available
  autonomously, so it returns a not-ready spec rather than running anything.

Clean-room, stdlib-only, IO confined to the dataset store + the dry-run spec
file. No model is loaded; no training is started.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from muse_cli.jarvis_prime.learning_dataset import (
    NEGATIVE_EXAMPLE,
    DatasetCandidate,
    DatasetStore,
    Provenance,
    QualityGates,
    TraceType,
)
from muse_cli.jarvis_prime.memory_tree import SourceTrust

#: Label every NL-compile trace carries, so the cohort is filterable.
NL_COMPILE_LABEL = "nl-compile"


def export_compile_trace(
    compile_result: Any,
    parse: Any,
    gate_summary: Optional[Any] = None,
    *,
    store: Optional[DatasetStore] = None,
    owner_approve: bool = False,
) -> DatasetCandidate:
    """Export an NL-compile into the learning dataset as a ``PENDING`` candidate.

    ``compile_result`` is a
    :class:`muse_cli.jarvis_prime.ir_compilers.base.CompileResult` and
    ``parse`` is the
    :class:`muse_cli.jarvis_prime.semantic_frontend.ParseResult` it was
    compiled from.

    The ``content`` carries only the prompt, the selected backend target, and
    the (non-sensitive) artifact dict. The dataset store's hard filters scrub
    secrets and strip raw chain-of-thought, raising
    :class:`~muse_cli.jarvis_prime.learning_dataset.RejectedTrace` on anything
    that survives — we rely on that and never deliberately embed a secret.

    A bare compile is an *intent* artifact, not proof of a passing run: at
    compile time there is no executed-test / review / rollback evidence, so the
    positive coding-task gates cannot pass. The trace is therefore stored as a
    labelled negative (unverified) example — that keeps it eligible to land
    ``PENDING`` for owner review without ever masquerading as a gate-passed
    positive. Quality labels are still derived from the real gate packet so the
    owner sees exactly which gates are (un)met.

    Set ``owner_approve=True`` to also move it to ``APPROVED`` in the same call
    (the owner-gated step); by default it stays ``PENDING``.
    """

    graph = parse.graph

    # Quality labels from the real JARVIS verification gates when a gate packet
    # is available; otherwise a conservative all-False QualityGates.
    packet = gate_summary
    if packet is None:
        packet = getattr(compile_result, "gate_packet", None)
    if packet is not None:
        quality = QualityGates.from_gate_summary(packet)
    else:
        quality = QualityGates()

    content: dict[str, Any] = {
        "prompt": graph.raw_text,
        "target": compile_result.target.value,
        "artifact": dict(compile_result.artifact_dict),
        "notes": list(getattr(compile_result, "notes", ()) or ()),
    }

    provenance = Provenance(
        source_kind="nl-compile",
        source_uri=f"nl-compile:{graph.graph_id}",
        job_id="",
        citations=(),
        trust=SourceTrust.UNVERIFIED,
    )

    store = store or DatasetStore.load()
    cand = store.add_candidate(
        TraceType.CODING_TASK,
        content,
        provenance,
        quality,
        labels=(NL_COMPILE_LABEL, NEGATIVE_EXAMPLE),
        task_key=f"nl-compile:{graph.graph_id}",
        persist=True,
    )
    if owner_approve:
        store.approve(cand.id, note="nl-compile owner-approved")
    return cand


@dataclass(frozen=True)
class FinetuneJobSpec:
    """A *dry-run* fine-tune job description. Writing it launches nothing."""

    dataset_path: str
    base_model: str
    method: str
    out_dir: str
    num_examples: int
    ready: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "hermes.jarvis.finetune_spec.v1",
            "dataset_path": self.dataset_path,
            "base_model": self.base_model,
            "method": self.method,
            "out_dir": self.out_dir,
            "num_examples": self.num_examples,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "launched": False,
        }

    def write(self, directory: Path | str) -> Path:
        """Write the spec as JSON under ``directory``. Starts no training."""

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "finetune_job_spec.json"
        _write_text(target, json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
        return target


def prepare_finetune_job(
    *,
    base_model: str,
    out_dir: str,
    dataset_path: Optional[Path | str] = None,
    method: str = "lora",
    min_examples: int = 1,
    store: Optional[DatasetStore] = None,
    launch: bool = False,
    grant: Any = None,
) -> FinetuneJobSpec:
    """Assemble a *dry-run* fine-tune job spec from owner-approved examples.

    Exports the owner-**approved** dataset examples to a JSONL under
    ``out_dir`` (via :meth:`DatasetStore.export_jsonl`) and reports readiness:
    ``ready`` is True only when at least ``min_examples`` approved examples were
    exported.

    **Never launches a GPU training run.** ``launch=True`` is refused unless a
    valid owner ``grant`` *and* an external runner are configured. Neither is
    available autonomously, so a launch request returns a ``ready=False`` spec
    whose reasons explain the refusal — training is never started here.
    """

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    store = store or DatasetStore.load()

    export_target = Path(dataset_path) if dataset_path else out_path / "nl_compile_dataset.jsonl"
    count = store.export_jsonl(export_target)

    reasons: list[str] = []
    ready = count >= min_examples
    if ready:
        reasons.append(f"exported {count} owner-approved example(s) (>= {min_examples})")
    else:
        reasons.append(
            f"only {count} owner-approved example(s) exported, need >= {min_examples}"
        )

    if launch:
        # Refuse to launch: real training requires an owner grant AND a
        # configured external runner. Neither is available autonomously, so we
        # never start training — we return a not-ready spec instead.
        ready = False
        reasons.append("launch refused: owner grant + external runner required")

    return FinetuneJobSpec(
        dataset_path=str(export_target),
        base_model=base_model,
        method=method,
        out_dir=str(out_path),
        num_examples=count,
        ready=ready,
        reasons=tuple(reasons),
    )


def _write_text(target: Path, content: str) -> None:
    """Atomic write with restrictive perms on the temp file."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".ftspec-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


__all__ = [
    "NL_COMPILE_LABEL",
    "export_compile_trace",
    "FinetuneJobSpec",
    "prepare_finetune_job",
]
