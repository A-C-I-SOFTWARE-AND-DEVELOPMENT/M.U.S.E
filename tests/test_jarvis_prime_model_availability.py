"""Tests for the model-availability report + fallback-walk primitive.

Fully injectable: provider specs, env, `ollama list`, and the policy file are
all supplied, so nothing touches the real registry, network, or Ollama.
"""

import json

from hermes_cli.jarvis_prime import model_availability as ma

_SPECS = [
    ("anthropic", ("ANTHROPIC_API_KEY",), "https://api.anthropic.com"),
    ("novita", ("NOVITA_API_KEY",), "https://api.novita.ai/openai/v1"),
    ("custom", (), "http://localhost:8000/v1"),
]


def test_installed_ollama_models_parses_and_skips_header():
    out = "NAME       ID   SIZE\ngemma4:e4b a 3GB\nllama3:8b b 5GB\n"
    assert ma.installed_ollama_models(lambda: out) == ["gemma4:e4b", "llama3:8b"]


def test_installed_ollama_models_empty_on_error():
    def boom():
        raise RuntimeError("no ollama")

    assert ma.installed_ollama_models(boom) == []


def test_cloud_provider_available_only_with_credential():
    by_name = {
        s.name: s
        for s in ma.provider_statuses(_SPECS, env={"ANTHROPIC_API_KEY": "k"}, installed_local_models=[])
    }
    assert by_name["anthropic"].available_now is True
    assert by_name["novita"].available_now is False
    assert "NOVITA_API_KEY" in by_name["novita"].detail


def test_local_provider_available_only_with_installed_model():
    none = {s.name: s for s in ma.provider_statuses(_SPECS, env={}, installed_local_models=[])}
    assert none["custom"].kind == "local"
    assert none["custom"].available_now is False
    have = {
        s.name: s
        for s in ma.provider_statuses(_SPECS, env={}, installed_local_models=["gemma4:e4b"])
    }
    assert have["custom"].available_now is True


def test_recommended_but_missing_normalizes_tags():
    # policy "gemma4-e4b" matches installed "gemma4:e4b"; llama3.2 is missing.
    assert ma.recommended_but_missing(["gemma4-e4b", "llama3.2"], ["gemma4:e4b"]) == ["llama3.2"]


def test_load_policy_recommended(tmp_path):
    policy = tmp_path / "model_policy.json"
    policy.write_text(
        json.dumps({"recommended_local_models": ["gemma4-e4b", "qwen3-8b"]}), encoding="utf-8"
    )
    assert ma.load_policy_recommended(policy) == ["gemma4-e4b", "qwen3-8b"]
    assert ma.load_policy_recommended(tmp_path / "absent.json") == []


def test_walk_fallback_chain_returns_first_success():
    calls = []

    def invoke(model):
        calls.append(model)
        if model == "down":
            raise RuntimeError("unavailable")
        return f"ok:{model}"

    assert ma.walk_fallback_chain(["down", "live", "third"], invoke) == ("live", "ok:live")
    assert calls == ["down", "live"]  # stops at the first success


def test_walk_fallback_chain_raises_when_all_fail():
    def invoke(_m):
        raise RuntimeError("nope")

    raised = False
    try:
        ma.walk_fallback_chain(["a", "b"], invoke)
    except RuntimeError:
        raised = True
    assert raised


def test_build_report_assembles(tmp_path):
    policy = tmp_path / "model_policy.json"
    policy.write_text(
        json.dumps({"recommended_local_models": ["gemma4-e4b", "llama3.2"]}), encoding="utf-8"
    )
    report = ma.build_report(
        specs=_SPECS,
        env={"ANTHROPIC_API_KEY": "k"},
        ollama_list=lambda: "NAME\ngemma4:e4b a 3GB\n",
        policy_path=policy,
    )
    assert len(report.available()) == 2  # anthropic (key) + custom (local gemma installed)
    assert report.recommended_missing == ["llama3.2"]
    data = report.to_dict()
    assert data["available_count"] == 2 and data["provider_count"] == 3
    assert "Model availability:" in report.render()
