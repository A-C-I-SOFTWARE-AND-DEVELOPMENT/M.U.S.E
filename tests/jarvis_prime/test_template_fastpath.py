"""Tests for the template fast path (Phase 3) — gating, modes, fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from hermes_cli.jarvis_prime.clusters import HashedFeatureBackend, fit_clusters  # noqa: E402
from hermes_cli.jarvis_prime.llama_client import LlamaServerClient  # noqa: E402
from hermes_cli.jarvis_prime.template_fastpath import (  # noqa: E402
    TemplateFastPath,
    build_fastpath,
    maybe_wrap_runner,
    templates_enabled,
)

_PROMPTS = [
    "Compute the metric alpha for the quarterly report.",
    "Compute the metric beta for the quarterly report.",
    "Compute the metric gamma for the quarterly report.",
    "Compute the metric delta for the quarterly report.",
]


def _write_template(root: Path, cluster_id: int, mode: str) -> None:
    d = root / str(cluster_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "scaffold.gbnf").write_text(
        'root ::= "# Reasoning: " slot0 ".\\nanswer: " slot1 "\\n"\n'
        "slot0 ::= [^\\n]+\nslot1 ::= [0-9]+\n",
        encoding="utf-8",
    )
    (d / "prefix.txt").write_text("Shared prefix.\n---\n", encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps({"v": 1, "cluster_id": cluster_id, "mode": mode}), encoding="utf-8"
    )


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail = False

    def completion(self, prompt: str, **kwargs):
        if self.fail:
            raise RuntimeError("server exploded")
        self.calls.append({"prompt": prompt, **kwargs})
        from hermes_cli.jarvis_prime.llama_client import CompletionResult

        return CompletionResult(
            text="# Reasoning: ok.\nanswer: 1\n",
            tokens_predicted=4,
            tokens_cached=11,
            prompt_ms=1.0,
            predict_ms=2.0,
            raw={},
        )


@pytest.fixture()
def fastpath(tmp_path: Path):
    backend = HashedFeatureBackend()
    model = fit_clusters(_PROMPTS, backend=backend, k=1, seed=0)
    _write_template(tmp_path, 0, "hard")
    records: list[tuple] = []
    fp = TemplateFastPath(
        model=model,
        backend=backend,
        templates_root=tmp_path,
        client=_FakeClient(),  # ty: ignore[invalid-argument-type]
        tau=0.75,
        n_slots=4,
        recorder=lambda kind, payload, outcome=None: records.append((kind, payload, outcome)),
        improvement_queue=lambda summary, payload: records.append(("queue", summary, payload)),
    )
    return fp, records


def test_hard_mode_single_constrained_call(fastpath) -> None:
    fp, records = fastpath
    result = fp.run(_PROMPTS[0])
    assert result is not None and result.used_fastpath
    assert result.mode == "hard"
    client = fp.client
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["grammar"].startswith("root ::=")
    assert call["id_slot"] == 0  # cluster 0 % 4 slots
    assert call["cache_prompt"] is True
    assert call["prompt"].startswith("Shared prefix.")
    assert any(p.get("summary") == "template fastpath used" for _, p, _ in records if isinstance(p, dict))


def test_soft_mode_two_stage_reason_then_format(fastpath, tmp_path: Path) -> None:
    fp, _ = fastpath
    _write_template(tmp_path, 0, "soft")
    result = fp.run(_PROMPTS[1])
    assert result is not None and result.mode == "soft"
    calls = fp.client.calls
    assert len(calls) == 2
    stage1, stage2 = calls
    assert "grammar" not in stage1 or stage1.get("grammar") is None  # free reasoning
    assert "Reason step by step" in stage1["prompt"]
    assert stage2["grammar"].startswith("root ::=")  # constrained fill
    assert "Draft reasoning:" in stage2["prompt"]
    assert stage1["id_slot"] == stage2["id_slot"]  # same cache slot


def test_below_tau_gates_out_and_logs_fallback(fastpath) -> None:
    fp, records = fastpath
    result = fp.run("order me a pizza with extra pineapple tonight please")
    assert result is None
    assert fp.client.calls == []
    fallbacks = [p for _, p, _ in records if isinstance(p, dict) and "below confidence gate" in p.get("summary", "")]
    assert fallbacks and fallbacks[0]["tau"] == 0.75


def test_missing_template_gates_out(fastpath, tmp_path: Path) -> None:
    fp, records = fastpath
    for child in (tmp_path / "0").iterdir():
        child.unlink()
    (tmp_path / "0").rmdir()
    assert fp.run(_PROMPTS[0]) is None
    assert any(
        isinstance(p, dict) and "no template for cluster" in p.get("summary", "")
        for _, p, _ in records
    )


def test_errors_fall_back_and_eventually_queue_improvement(fastpath) -> None:
    fp, records = fastpath
    fp.client.fail = True
    for _ in range(3):
        assert fp.run(_PROMPTS[0]) is None
    queued = [r for r in records if r[0] == "queue"]
    assert len(queued) == 1
    assert "repeated hard errors" in queued[0][1]
    # Recovery resets the counter and the lane keeps working.
    fp.client.fail = False
    assert fp.run(_PROMPTS[0]) is not None


def test_templates_enabled_flag_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for value, expected in [
        (None, False), ("", False), ("0", False), ("off", False),
        ("1", True), ("true", True), ("YES", True), (" on ", True),
    ]:
        if value is None:
            monkeypatch.delenv("MUSE_TEMPLATES", raising=False)
        else:
            monkeypatch.setenv("MUSE_TEMPLATES", value)
        assert templates_enabled() is expected


def test_build_fastpath_returns_none_without_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSE_TEMPLATES_SERVER", raising=False)
    assert build_fastpath() is None


def test_build_fastpath_returns_none_without_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MUSE_TEMPLATES_SERVER", "http://127.0.0.1:9")
    monkeypatch.setenv("MUSE_TEMPLATES_DIR", str(tmp_path))  # empty: no model/
    assert build_fastpath() is None


def test_maybe_wrap_runner_identity_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSE_TEMPLATES", raising=False)

    def base(prompt: str) -> str:
        return prompt

    assert maybe_wrap_runner(base) is base


def test_wrapped_runner_falls_back_to_base(fastpath, monkeypatch: pytest.MonkeyPatch) -> None:
    fp, _ = fastpath
    monkeypatch.setenv("MUSE_TEMPLATES", "1")
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.template_fastpath.build_fastpath", lambda **kw: fp
    )
    wrapped = maybe_wrap_runner(lambda p: f"base:{p}")
    assert wrapped("order me a pizza with extra pineapple tonight") == (
        "base:order me a pizza with extra pineapple tonight"
    )
    assert wrapped(_PROMPTS[0]) == "# Reasoning: ok.\nanswer: 1\n"


def test_committed_artifacts_build_a_fastpath_against_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # End-to-end: committed model + templates + a real HTTP stub server.
    import threading

    from .test_llama_client import _StubHandler
    from http.server import ThreadingHTTPServer

    _StubHandler.slot_cache = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        monkeypatch.delenv("MUSE_TEMPLATES_DIR", raising=False)
        fp = build_fastpath(server_url=url)
        assert fp is not None
        result = fp.run("Write a Python function `sum_list` that returns the sum of a list of integers.")
        assert result is not None and result.used_fastpath
        assert isinstance(fp.client, LlamaServerClient)
    finally:
        server.shutdown()
