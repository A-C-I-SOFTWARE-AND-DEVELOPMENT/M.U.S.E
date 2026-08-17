"""Characterization of the P3 NIM 70b → 49b timeout fallback.

Work Packet item 217 (§1 p4, §10, §11): ``meta/llama-3.3-70b-instruct``
read-timed-out repeatedly and the chain fell back to
``nvidia/llama-3.3-nemotron-super-49b-v1.5``. That status is MITIGATED, not
closed — live 70b is still queue-bound on free-tier NIM. This module pins the
*harness* behaviour that made mitigation possible:

* the documented chain order and the 70b bounded read timeout
* one retry on the 70b route, then escalation
* fallback is invoked when the 70b route times out

The provider is mocked. Nothing here hits integrate.api.nvidia.com, needs an
API key, or claims that live 70b currently answers. The recorded live log
(``.hermes/research_fabric/smoke/p3_run.log``) is the historical evidence
that 70b timed out twice and 49b answered; see
``test_baseline_model_field_names_the_head_of_chain_not_the_answering_model``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = REPO_ROOT / "scripts" / "research_fabric" / "p3_swe_bench.py"

NIM_70B = "meta/llama-3.3-70b-instruct"
NIM_NEMOTRON_49B = "nvidia/llama-3.3-nemotron-super-49b-v1.5"
NIM_8B = "meta/llama-3.1-8b-instruct"

# The recorded live error string from p3_run.log. Raised as-is so the
# harness log line stays byte-compatible with that artifact.
_READ_TIMEOUT = TimeoutError("The read operation timed out")


def _load_harness():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        "p3_swe_bench_escalation_under_test", HARNESS_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def harness():
    return _load_harness()


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ok(content: str) -> _FakeResp:
    return _FakeResp({"choices": [{"message": {"content": content}}]})


def _model_of(req) -> str:
    return json.loads(req.data.decode("utf-8"))["model"]


# --------------------------------------------------------------------------- #
# Chain shape — the documented fallback must not silently reorder
# --------------------------------------------------------------------------- #


def test_documented_chain_is_70b_then_nemotron_49b_then_8b(harness):
    """The packet names this chain. Reordering it is a different mitigation."""
    models = [model for model, _timeout in harness.NIM_CHAIN]
    assert models == [NIM_70B, NIM_NEMOTRON_49B, NIM_8B]
    assert harness.NIM_CHAIN[0] == (NIM_70B, harness.NIM_70B_READ_TIMEOUT_S)
    assert harness.NIM_70B_READ_TIMEOUT_S == 75
    assert harness.NIM_70B_RETRIES == 1
    assert harness.NIM_MODEL == NIM_70B


def test_70b_route_is_bounded_to_one_retry(harness):
    assert harness._attempts_for(NIM_70B) == 2
    # Later rungs keep the caller default; they are not given extra 70b retries.
    assert harness._attempts_for(NIM_NEMOTRON_49B) == 2
    assert harness._attempts_for(NIM_70B, default_attempts=5) == 2


# --------------------------------------------------------------------------- #
# Timeout → retry → fallback. Mocked. No live NIM.
# --------------------------------------------------------------------------- #


def test_70b_read_timeout_retries_once_then_falls_back_to_nemotron(
    harness, monkeypatch, capsys
):
    """The recorded failure, as a unit: 70b times out twice, 49b answers.

    This is the characterization item 217 asked for. It does **not** prove
    live 70b works — the mock never lets 70b succeed.
    """
    calls: list[tuple[str, float | None]] = []

    def fake_urlopen(req, timeout=None):
        model = _model_of(req)
        calls.append((model, timeout))
        if model == NIM_70B:
            raise _READ_TIMEOUT
        if model == NIM_NEMOTRON_49B:
            return _ok("def add(a, b):\n    return a + b\n")
        raise AssertionError(f"fallback walked past 49b to {model}")

    monkeypatch.setattr(harness, "_load_api_key", lambda: "test-key-not-live")
    monkeypatch.setattr(harness, "_nim_urlopen", fake_urlopen)
    monkeypatch.setattr(harness.time, "sleep", lambda _s: None)

    content = harness._nim_call("rewrite calc.py")

    assert content == "def add(a, b):\n    return a + b\n"
    assert calls == [
        (NIM_70B, 75),
        (NIM_70B, 75),  # one retry, same bounded read timeout
        (NIM_NEMOTRON_49B, 120),
    ]
    log = capsys.readouterr().out
    assert f"{NIM_70B} attempt 1/2: The read operation timed out" in log
    assert f"{NIM_70B} attempt 2/2: The read operation timed out" in log
    assert f"answered by {NIM_NEMOTRON_49B}" in log
    assert NIM_8B not in {model for model, _ in calls}


def test_70b_success_on_retry_does_not_call_fallback(harness, monkeypatch):
    """One retry is enough when the second 70b attempt returns content."""
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        model = _model_of(req)
        calls.append(model)
        if model == NIM_70B and calls.count(NIM_70B) == 1:
            raise _READ_TIMEOUT
        if model == NIM_70B:
            return _ok("ok-from-70b-retry")
        raise AssertionError(f"fallback should not have been reached: {model}")

    monkeypatch.setattr(harness, "_load_api_key", lambda: "test-key-not-live")
    monkeypatch.setattr(harness, "_nim_urlopen", fake_urlopen)
    monkeypatch.setattr(harness.time, "sleep", lambda _s: None)

    assert harness._nim_call("prompt") == "ok-from-70b-retry"
    assert calls == [NIM_70B, NIM_70B]


def test_wrapped_urlerror_read_timeout_also_escalates(harness, monkeypatch):
    """Windows urllib often wraps the socket timeout in URLError."""
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        model = _model_of(req)
        calls.append(model)
        if model == NIM_70B:
            raise URLError(TimeoutError("The read operation timed out"))
        return _ok("from-49b")

    monkeypatch.setattr(harness, "_load_api_key", lambda: "test-key-not-live")
    monkeypatch.setattr(harness, "_nim_urlopen", fake_urlopen)
    monkeypatch.setattr(harness.time, "sleep", lambda _s: None)

    assert harness._nim_call("prompt") == "from-49b"
    assert calls == [NIM_70B, NIM_70B, NIM_NEMOTRON_49B]


def test_nim_urlopen_is_not_called_against_live_host_in_these_tests(
    harness, monkeypatch
):
    """Guard: if the injectable opener is forgotten, fail closed — no network."""

    def forbidden(*_a, **_k):
        raise AssertionError("live NIM opener must not run in this module")

    monkeypatch.setattr(harness, "_load_api_key", lambda: "test-key-not-live")
    monkeypatch.setattr(harness, "_nim_urlopen", forbidden)
    monkeypatch.setattr(harness.time, "sleep", lambda _s: None)

    assert harness._nim_call("prompt") is None
