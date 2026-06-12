"""Tests for the Gemma runner factory + runtime auto-wiring.

Deterministic: Ollama detection is fully injectable (which / list / invoke), and
the runtime auto-wiring uses an injected factory, so nothing touches a real
Ollama or the network.
"""

from muse_cli.jarvis_prime import gemma_runner as gr
from muse_cli.jarvis_prime.memory import MemoryStore
from muse_cli.jarvis_prime.memory_tree import MemoryTreeStore
from muse_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime

_OLLAMA_LIST = (
    "NAME              ID    SIZE    MODIFIED\n"
    "gemma4:e2b        aaa   1 GB    1 day ago\n"
    "gemma4:e4b        bbb   3 GB    1 day ago\n"
    "llama3:8b         ccc   5 GB    2 days ago\n"
)


def test_detect_prefers_e4b():
    assert gr.detect_installed_gemma_tag(list_runner=lambda: _OLLAMA_LIST) == "gemma4:e4b"


def test_detect_none_when_no_gemma():
    assert gr.detect_installed_gemma_tag(list_runner=lambda: "NAME\nllama3:8b\n") is None


def test_build_runner_none_without_ollama():
    assert gr.build_gemma_runner(which=lambda _c: None) is None


def test_build_runner_none_without_model():
    runner = gr.build_gemma_runner(
        which=lambda _c: "/usr/bin/ollama",
        list_runner=lambda: "NAME\nllama3:8b\n",
    )
    assert runner is None


def test_build_runner_returns_invoke_for_installed_gemma():
    captured = {}

    def invoke_factory(tag):
        captured["tag"] = tag
        return lambda prompt: f"[{tag}] {prompt}"

    runner = gr.build_gemma_runner(
        which=lambda _c: "/usr/bin/ollama",
        list_runner=lambda: _OLLAMA_LIST,
        invoke_factory=invoke_factory,
    )
    assert runner is not None
    assert captured["tag"] == "gemma4:e4b"
    assert runner("hi") == "[gemma4:e4b] hi"


def test_auto_runner_enabled_reads_env(monkeypatch):
    monkeypatch.delenv(gr.ENV_AUTO_RUNNER, raising=False)
    assert not gr.auto_runner_enabled()
    monkeypatch.setenv(gr.ENV_AUTO_RUNNER, "1")
    assert gr.auto_runner_enabled()
    monkeypatch.setenv(gr.ENV_AUTO_RUNNER, "off")
    assert not gr.auto_runner_enabled()


# --- runtime auto-wiring -----------------------------------------------------


def _config(tmp_path, **extra):
    return JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "tree.jsonl"),
        **extra,
    )


def test_runtime_auto_wires_via_factory(tmp_path):
    # An injected factory simulates a detected local Gemma — no env / Ollama needed.
    def fake_runner(_prompt):
        return (
            '[{"title": "Pref", "summary": "User prefers concise replies", '
            '"namespace": "jarvis/personal", "confidence": 0.95}]'
        )

    jp = JarvisPrime(config=_config(tmp_path, gemma_runner_factory=lambda: fake_runner))
    summary = jp.observe_turn("hello there", "hi")
    assert summary.get("gemma_proposed", 0) >= 1


def test_runtime_inert_when_factory_returns_none(tmp_path):
    jp = JarvisPrime(config=_config(tmp_path, gemma_runner_factory=lambda: None))
    summary = jp.observe_turn("hello there", "hi")
    assert "gemma_proposed" not in summary


def test_runtime_default_stays_inert(tmp_path, monkeypatch):
    # No explicit runner, no factory, env off => byte-identical (no auto-build).
    monkeypatch.delenv(gr.ENV_AUTO_RUNNER, raising=False)
    jp = JarvisPrime(config=_config(tmp_path))
    summary = jp.observe_turn("hello there", "hi")
    assert "gemma_proposed" not in summary


def test_explicit_runner_still_wins(tmp_path):
    # An explicit gemma_runner takes precedence over the factory.
    def explicit(_prompt):
        return '[{"title": "x", "summary": "y", "namespace": "jarvis/general"}]'

    def factory_should_not_run():
        raise AssertionError("factory must not be called when gemma_runner is set")

    jp = JarvisPrime(
        config=_config(tmp_path, gemma_runner=explicit, gemma_runner_factory=factory_should_not_run)
    )
    summary = jp.observe_turn("hello there", "hi")
    assert summary.get("gemma_proposed", 0) >= 1
