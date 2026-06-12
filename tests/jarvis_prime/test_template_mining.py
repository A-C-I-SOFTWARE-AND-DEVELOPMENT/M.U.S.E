"""Tests for template mining (Phase 2) — PASSED-only, self-checked scaffolds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from hermes_cli.jarvis_prime.bench.corpus import CorpusRecord  # noqa: E402
from hermes_cli.jarvis_prime.clusters import HashedFeatureBackend, fit_clusters  # noqa: E402
from hermes_cli.jarvis_prime.template_mining import (  # noqa: E402
    load_template,
    mine_templates,
    templates_dir,
    write_templates,
)

REPO_TEMPLATES = Path(__file__).resolve().parents[2] / "hermes_cli" / "jarvis_prime" / "templates"

_PROMPTS = [
    "Compute the metric alpha for the quarterly report.",
    "Compute the metric beta for the quarterly report.",
    "Compute the metric gamma for the quarterly report.",
    "Compute the metric delta for the quarterly report.",
]


def _rec(i: int, *, passed: bool, output: str) -> CorpusRecord:
    return CorpusRecord(
        task_id=f"t-{i:02d}#c{0 if passed else 1}",
        domain="reasoning",
        prompt=_PROMPTS[i % len(_PROMPTS)],
        output=output,
        verifier_passed=passed,
        source="fixture:test",
    )


@pytest.fixture()
def corpus() -> list[CorpusRecord]:
    passed_outputs = [
        "# Reasoning: alpha rises with volume.\nanswer: 41\n",
        "# Reasoning: beta tracks the median.\nanswer: 7\n",
        "# Reasoning: gamma is seasonal.\nanswer: 13\n",
        "# Reasoning: delta lags by a quarter.\nanswer: 29\n",
    ]
    records = [_rec(i, passed=True, output=o) for i, o in enumerate(passed_outputs)]
    records.append(
        _rec(4, passed=False, output="# Reasoning: POISONTOKEN nonsense.\nanswer: banana\n")
    )
    return records


@pytest.fixture()
def mined(corpus):
    backend = HashedFeatureBackend()
    model = fit_clusters([r.prompt for r in corpus], backend=backend, k=1, seed=0)
    return mine_templates(corpus, model, backend=backend, min_support=3)


def test_failed_outputs_never_reach_templates(mined, corpus) -> None:
    assert len(mined) == 1
    template = mined[0]
    failed = [r for r in corpus if not r.verifier_passed]
    assert failed
    for rec in failed:
        assert rec.task_id not in template.meta["source_task_ids"]
        assert rec.output_hash not in template.meta["source_output_hashes"]
    assert "POISONTOKEN" not in "".join(template.literals)
    assert "POISONTOKEN" not in template.scaffold_gbnf


def test_source_hashes_cover_exactly_the_passed_records(mined, corpus) -> None:
    passed_hashes = sorted(r.output_hash for r in corpus if r.verifier_passed)
    assert mined[0].meta["source_output_hashes"] == passed_hashes
    assert mined[0].meta["verified_only"] is True


def test_grammar_rematches_every_exemplar(mined, corpus) -> None:
    template = mined[0]
    for rec in corpus:
        if rec.verifier_passed:
            assert template.matches(rec.output)
    assert not template.matches("totally unstructured output")


def test_scaffold_keeps_reasoning_before_answer(mined) -> None:
    scaffold = mined[0].scaffold_gbnf
    assert scaffold.index("Reasoning") < scaffold.index("answer")
    prefix = mined[0].prefix
    assert prefix.index("# Reasoning") < prefix.index("\nanswer:")


def test_number_slot_typing(mined) -> None:
    # The answer gap holds only integers across exemplars -> "number" slot.
    template = mined[0]
    assert any(s.kind == "number" for s in template.slots)


def test_min_support_skips_thin_clusters(corpus) -> None:
    backend = HashedFeatureBackend()
    model = fit_clusters([r.prompt for r in corpus], backend=backend, k=1, seed=0)
    assert mine_templates(corpus, model, backend=backend, min_support=10) == []


def test_write_and_load_roundtrip_deterministic(mined, tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    write_templates(mined, dir_a)
    write_templates(mined, dir_b)
    cluster_id = mined[0].cluster_id
    for name in ("scaffold.gbnf", "prefix.txt", "meta.json"):
        assert (dir_a / str(cluster_id) / name).read_bytes() == (
            dir_b / str(cluster_id) / name
        ).read_bytes()
    loaded = load_template(dir_a, cluster_id)
    assert loaded is not None
    assert loaded.scaffold_gbnf == mined[0].scaffold_gbnf
    assert loaded.prefix == mined[0].prefix
    assert loaded.mode == mined[0].meta["mode"]
    assert load_template(dir_a, 999) is None


def test_templates_dir_honors_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MUSE_TEMPLATES_DIR", raising=False)
    assert templates_dir() == REPO_TEMPLATES
    monkeypatch.setenv("MUSE_TEMPLATES_DIR", str(tmp_path / "live"))
    assert templates_dir() == tmp_path / "live"


def test_committed_registry_is_well_formed() -> None:
    cluster_dirs = sorted(d for d in REPO_TEMPLATES.iterdir() if d.name.isdigit())
    assert cluster_dirs, "expected committed cluster templates"
    modes = set()
    for d in cluster_dirs:
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        for key in (
            "v",
            "version",
            "cluster_id",
            "mode",
            "support",
            "coverage",
            "slot_count",
            "verified_only",
            "source_task_ids",
            "source_output_hashes",
            "corpus_hash",
            "backend_name",
            "tau",
            "created_at",
        ):
            assert key in meta, f"{d.name} missing {key}"
        assert meta["mode"] in ("hard", "soft")
        assert meta["verified_only"] is True
        assert meta["cluster_id"] == int(d.name)
        assert (d / "prefix.txt").read_text(encoding="utf-8").strip()
        grammar = (d / "scaffold.gbnf").read_text(encoding="utf-8")
        assert grammar.startswith("root ::=")
        modes.add(meta["mode"])
    assert "hard" in modes, "at least one structural hard-mode cluster expected"
