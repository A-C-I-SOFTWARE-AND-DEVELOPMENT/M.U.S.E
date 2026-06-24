"""Phase-3 regression gate: MUSE_TEMPLATES off => gemma_runner byte-identical.

The strongest possible guarantee is object identity — flag off, the exact
runner object the invoke factory produced is returned, the fast-path module is
never imported, and a fixed prompt set produces identical output hashes.
"""

from __future__ import annotations

import sys

import pytest

from hermes_cli.jarvis_prime.bench.baseline import measure_runner
from hermes_cli.jarvis_prime.gemma_runner import build_gemma_runner

_OLLAMA_LIST = "NAME            ID    SIZE   MODIFIED\ngemma4:e2b      abc   2 GB   now\n"
_PROMPTS = ["alpha task", "beta task", "gamma task"]


def _sentinel_runner(prompt: str) -> str:
    return f"echo:{prompt}"


def _build(monkeypatch: pytest.MonkeyPatch):
    return build_gemma_runner(
        which=lambda name: "/usr/bin/ollama",
        list_runner=lambda: _OLLAMA_LIST,
        invoke_factory=lambda tag: _sentinel_runner,
    )


@pytest.mark.parametrize("flag_value", [None, "", "0", "false", "off", "no"])
def test_flag_off_returns_identical_runner_object(
    monkeypatch: pytest.MonkeyPatch, flag_value: str | None
) -> None:
    if flag_value is None:
        monkeypatch.delenv("MUSE_TEMPLATES", raising=False)
    else:
        monkeypatch.setenv("MUSE_TEMPLATES", flag_value)
    monkeypatch.delitem(sys.modules, "hermes_cli.jarvis_prime.template_fastpath", raising=False)

    runner = _build(monkeypatch)
    assert runner is _sentinel_runner
    # Flag off must not even import the fast-path module.
    assert "hermes_cli.jarvis_prime.template_fastpath" not in sys.modules


def test_flag_off_outputs_byte_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSE_TEMPLATES", raising=False)
    runner = _build(monkeypatch)
    assert runner is not None
    report = measure_runner(runner, _PROMPTS, label="flag-off")
    direct = measure_runner(_sentinel_runner, _PROMPTS, label="direct")
    assert report.output_hashes() == direct.output_hashes()


def test_flag_on_without_server_still_returns_base_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUSE_TEMPLATES", "1")
    monkeypatch.delenv("MUSE_TEMPLATES_SERVER", raising=False)
    runner = _build(monkeypatch)
    assert runner is _sentinel_runner


def test_flag_on_with_unreachable_server_still_returns_base_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MUSE_TEMPLATES", "1")
    # Port 9 (discard) — nothing listens; health() must fail closed fast.
    monkeypatch.setenv("MUSE_TEMPLATES_SERVER", "http://127.0.0.1:9")
    runner = _build(monkeypatch)
    assert runner is _sentinel_runner


def test_flag_off_when_ollama_missing_still_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MUSE_TEMPLATES", raising=False)
    assert build_gemma_runner(which=lambda name: None) is None
