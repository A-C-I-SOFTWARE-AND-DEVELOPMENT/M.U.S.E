"""Behavioral tests for the W9 NL-compile fine-tuning export + dry-run harness.

Everything runs against an isolated ``HERMES_HOME`` (monkeypatched) and tmp
paths, so the real learning dataset is never touched. No GPU training is ever
launched — the harness is dry-run by construction and these tests assert that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from muse_cli.jarvis_prime import semantic_frontend as sf
from muse_cli.jarvis_prime.backend_selector import BackendContext, BackendTarget
from muse_cli.jarvis_prime.ir_compilers import get_compiler
from muse_cli.jarvis_prime.learning_dataset import (
    CandidateStatus,
    DatasetStore,
    RejectedTrace,
)
from muse_cli.jarvis_prime.nlp_training import (
    NL_COMPILE_LABEL,
    FinetuneJobSpec,
    export_compile_trace,
    prepare_finetune_job,
)


@pytest.fixture()
def hermes_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at a tmp dir so the real dataset is untouched."""

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def store(tmp_path):
    """A DatasetStore backed by an isolated tmp JSONL."""

    return DatasetStore(path=tmp_path / "dataset.jsonl")


def _compile(prompt: str, repo_root: str):
    """Parse + compile a prompt to a REPO_WORK_PACKET (small repo_root to be fast)."""

    parse = sf.parse(prompt)
    result = get_compiler(BackendTarget.REPO_WORK_PACKET).compile(
        parse.graph, BackendContext(repo_root=repo_root)
    )
    return parse, result


def test_export_compile_trace_lands_pending_with_provenance(hermes_home, store, tmp_path):
    parse, result = _compile("add a function to the gateway module", str(tmp_path))

    cand = export_compile_trace(result, parse, store=store)

    # Lands PENDING by default (owner approval is a separate step).
    assert cand.status == CandidateStatus.PENDING
    # Provenance points back at the NL-compile graph.
    assert cand.provenance.source_kind == "nl-compile"
    assert cand.provenance.source_uri == f"nl-compile:{parse.graph.graph_id}"
    assert NL_COMPILE_LABEL in cand.labels
    # Content carries the prompt + selected target, no obvious secret.
    assert cand.content["prompt"] == "add a function to the gateway module"
    assert cand.content["target"] == BackendTarget.REPO_WORK_PACKET.value
    flat = json.dumps(cand.content)
    assert "sk-" not in flat
    assert "BEGIN" not in flat or "PRIVATE KEY" not in flat
    # Persisted into the isolated store.
    assert store.get(cand.id) is not None


def test_export_compile_trace_owner_approve(hermes_home, store, tmp_path):
    parse, result = _compile("add a function to the gateway module", str(tmp_path))

    cand = export_compile_trace(result, parse, store=store, owner_approve=True)

    assert cand.status == CandidateStatus.APPROVED


def _tamper(result, **overrides):
    """A CompileResult-like stand-in with a tampered artifact_dict."""

    leaked = dict(result.artifact_dict)
    leaked.update(overrides)

    class _Tampered:
        target = result.target
        artifact = result.artifact
        artifact_dict = leaked
        gate_packet = result.gate_packet
        notes = result.notes

    return _Tampered()


def test_export_compile_trace_scrubs_secret(hermes_home, store, tmp_path):
    """A fake secret in the artifact is scrubbed by the pipeline's hard filters.

    The dataset store force-redacts secrets, so a recognizable raw key never
    survives into stored content, and the candidate is never auto-approved.
    """

    SECRET = "sk-ABCDEFGHIJKLMNOP1234567890"
    parse, result = _compile("add a function to the gateway module", str(tmp_path))
    tampered = _tamper(result, mission=f"call out with {SECRET} please")

    cand = export_compile_trace(tampered, parse, store=store)

    # The raw secret was scrubbed out of the stored content; nothing approved.
    flat = json.dumps(cand.content)
    assert SECRET not in flat
    assert cand.status != CandidateStatus.APPROVED


def test_export_compile_trace_rejects_unstrippable_chain_of_thought(
    hermes_home, store, tmp_path
):
    """Raw chain-of-thought that cannot be cleanly stripped trips a hard filter."""

    parse, result = _compile("add a function to the gateway module", str(tmp_path))
    # An unclosed <think> block cannot be stripped -> RejectedTrace.
    tampered = _tamper(result, mission="before <think> private reasoning never closed")

    with pytest.raises(RejectedTrace):
        export_compile_trace(tampered, parse, store=store)

    # Nothing was approved as a usable example.
    assert all(c["status"] != "approved" for c in store.export_audit_cards())


def test_prepare_finetune_job_dry_run(hermes_home, store, tmp_path):
    # Seed one owner-approved example.
    parse, result = _compile("add a function to the gateway module", str(tmp_path))
    export_compile_trace(result, parse, store=store, owner_approve=True)

    out_dir = tmp_path / "ft_out"
    spec = prepare_finetune_job(
        base_model="x",
        out_dir=str(out_dir),
        min_examples=1,
        store=store,
    )

    assert isinstance(spec, FinetuneJobSpec)
    assert spec.ready is True
    assert spec.num_examples == 1
    assert spec.base_model == "x"

    # Dataset JSONL was written under out_dir; the spec can be written too.
    dataset_file = Path(spec.dataset_path)
    assert dataset_file.exists()
    assert sum(1 for _ in dataset_file.open()) == 1

    spec_file = spec.write(out_dir)
    assert spec_file.exists()
    written = json.loads(spec_file.read_text())
    assert written["launched"] is False
    assert written["ready"] is True

    # No training side effects: out_dir holds only the dataset + spec files.
    produced = {p.name for p in out_dir.iterdir()}
    assert produced == {dataset_file.name, spec_file.name}


def test_prepare_finetune_job_not_ready_when_empty(hermes_home, store, tmp_path):
    spec = prepare_finetune_job(
        base_model="x",
        out_dir=str(tmp_path / "empty_out"),
        min_examples=1,
        store=store,
    )
    assert spec.ready is False
    assert spec.num_examples == 0
    assert any("need >=" in r for r in spec.reasons)


def test_prepare_finetune_job_launch_refused(hermes_home, store, tmp_path):
    # Even with an approved example present, launch is refused without a grant.
    parse, result = _compile("add a function to the gateway module", str(tmp_path))
    export_compile_trace(result, parse, store=store, owner_approve=True)

    spec = prepare_finetune_job(
        base_model="x",
        out_dir=str(tmp_path / "launch_out"),
        min_examples=1,
        store=store,
        launch=True,
        grant=None,
    )

    assert spec.ready is False
    assert any("grant" in r.lower() for r in spec.reasons)
    # Refusing launch still produced no training artifacts beyond the dataset.
    out_dir = tmp_path / "launch_out"
    produced = {p.name for p in out_dir.iterdir()}
    assert produced == {Path(spec.dataset_path).name}
