"""Learning-loop closure: approved traces → dataset+spec → owner-gated launch.

Uses a fake dataset store (controls readiness) and an injected ``spawn`` so the
launch path is verified without running a real trainer.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.nlp_training import (
    TRAINING_RUNNER_ENV,
    close_training_loop,
)

PHRASE = "Yes, with authorization."


class _FakeStore:
    def __init__(self, n: int) -> None:
        self._n = n

    def export_jsonl(self, path) -> int:
        body = "".join("{}\n" for _ in range(self._n))
        Path(path).write_text(body, encoding="utf-8")
        return self._n


def test_not_ready_without_examples(tmp_path):
    r = close_training_loop(base_model="m", out_dir=str(tmp_path), store=_FakeStore(0))
    assert r.spec.ready is False
    assert r.launched is False
    # spec is still materialized for the owner
    assert (tmp_path / "finetune_job_spec.json").exists()


def test_ready_requires_owner_phrase(tmp_path):
    r = close_training_loop(base_model="m", out_dir=str(tmp_path), store=_FakeStore(3))
    assert r.spec.ready is True
    assert r.launched is False
    assert "owner authorization" in r.reason


def test_ready_phrase_but_no_runner(tmp_path, monkeypatch):
    monkeypatch.delenv(TRAINING_RUNNER_ENV, raising=False)
    r = close_training_loop(
        base_model="m", out_dir=str(tmp_path), store=_FakeStore(3), owner_phrase=PHRASE
    )
    assert r.launched is False
    assert "no training runner" in r.reason


def test_launches_with_phrase_and_runner(tmp_path):
    calls: dict = {}

    def spawn(runner: str, dataset: str, spec: str) -> int:
        calls.update(runner=runner, dataset=dataset, spec=spec)
        return 0

    r = close_training_loop(
        base_model="m",
        out_dir=str(tmp_path),
        store=_FakeStore(3),
        owner_phrase=PHRASE,
        runner_cmd="python train.py",
        spawn=spawn,
    )
    assert r.launched is True
    assert r.returncode == 0
    assert calls["runner"] == "python train.py"
    assert calls["dataset"].endswith(".jsonl")
    assert calls["spec"].endswith("finetune_job_spec.json")


def test_nonzero_runner_is_not_launched(tmp_path):
    r = close_training_loop(
        base_model="m",
        out_dir=str(tmp_path),
        store=_FakeStore(2),
        owner_phrase=PHRASE,
        runner_cmd="x",
        spawn=lambda *_a: 3,
    )
    assert r.launched is False
    assert r.returncode == 3
