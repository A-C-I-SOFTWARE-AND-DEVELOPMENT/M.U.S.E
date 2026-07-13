"""Contract tests for the post-turn plugin observability hook.

``post_turn`` is intentionally observer-only. It runs once after the agent has
assembled its complete result metadata, so a plugin can record quality signals
without influencing a user-visible answer or the core tool loop.
"""

import ast
from pathlib import Path

import yaml

from hermes_cli.plugins import PluginManager, VALID_HOOKS


REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_enabled_plugin(hermes_home: Path, name: str, register_body: str) -> None:
    plugin_dir = hermes_home / "plugins" / name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        yaml.safe_dump({"name": name, "version": "0.1.0"}), encoding="utf-8"
    )
    (plugin_dir / "__init__.py").write_text(
        "def register(ctx):\n" + f"    {register_body}\n", encoding="utf-8"
    )
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": [name]}}), encoding="utf-8"
    )


def test_post_turn_is_a_public_plugin_hook():
    assert "post_turn" in VALID_HOOKS


def test_post_turn_plugin_receives_quality_metrics(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _make_enabled_plugin(
        hermes_home,
        "turn_observer",
        'ctx.register_hook("post_turn", lambda **kw: '
        '(kw["turn_exit_reason"], kw["api_calls"], kw["tool_turns"], '
        'kw["completed"], kw["interrupted"]))',
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    manager = PluginManager()
    manager.discover_and_load()
    results = manager.invoke_hook(
        "post_turn",
        session_id="session-1",
        model="gpt-5.6-terra",
        provider="openai-codex",
        platform="cli",
        turn_exit_reason="text_response(finish_reason=stop)",
        completed=True,
        interrupted=False,
        api_calls=4,
        max_iterations=90,
        budget_used=4,
        budget_max=90,
        tool_turns=2,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        final_response="done",
    )

    assert results == [("text_response(finish_reason=stop)", 4, 2, True, False)]


def test_conversation_loop_wires_post_turn_after_result_is_built():
    source = (REPO_ROOT / "agent" / "conversation_loop.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    calls = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_invoke_hook"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "post_turn"
    ]

    assert len(calls) == 1
    keyword_names = {keyword.arg for keyword in calls[0].keywords}
    assert {
        "turn_exit_reason",
        "completed",
        "interrupted",
        "api_calls",
        "tool_turns",
        "total_tokens",
    } <= keyword_names
