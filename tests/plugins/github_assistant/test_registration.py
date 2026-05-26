"""Plugin registration goes through PluginContext.register_tool correctly.

We don't load the whole Hermes CLI here — that would pull in models,
config files, the credential pool. Instead we feed register() a small
stub PluginContext and confirm the 8 expected tools land with the
right toolset name, check_fn, and requires_env list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import plugins.github_assistant as plugin_pkg


@dataclass
class _StubContext:
    """Captures every register_tool call into a list for assertion."""

    registrations: list[dict] = field(default_factory=list)

    def register_tool(self, **kwargs: Any) -> None:
        self.registrations.append(kwargs)


def test_register_emits_all_eight_tools():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    names = [r["name"] for r in ctx.registrations]
    assert names == [
        "github_audit_repo",
        "github_get_repo_file",
        "github_list_branches",
        "github_list_issues",
        "github_create_issue",
        "github_list_pull_requests",
        "github_get_pull_request",
        "github_comment_on_issue_or_pr",
    ]


def test_every_tool_belongs_to_the_github_toolset():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    assert all(r["toolset"] == "github" for r in ctx.registrations)


def test_every_tool_shares_the_same_check_fn():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    funcs = {r["check_fn"] for r in ctx.registrations}
    assert len(funcs) == 1
    # And it must be the right one:
    fn = next(iter(funcs))
    assert callable(fn)
    assert fn.__name__ == "check_github_requirements"


def test_every_tool_declares_token_as_required_env():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    for r in ctx.registrations:
        assert r["requires_env"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]


def test_handlers_are_callable_and_accept_args_and_kwargs():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    for r in ctx.registrations:
        h: Callable = r["handler"]
        # The handler should accept positional args dict + **kwargs without raising on a dry call.
        # We pass an empty dict and a stub kwarg; the handler will return a JSON error string,
        # but it must NOT raise. Skip handlers that depend on a real config — the no-config
        # path here returns plugin_disabled cleanly.
        result = h({}, _hermes_runtime_context={})
        assert isinstance(result, str)
        # Should parse as JSON.
        import json

        parsed = json.loads(result)
        assert "success" in parsed


def test_schemas_have_required_fields():
    ctx = _StubContext()
    plugin_pkg.register(ctx)
    for r in ctx.registrations:
        s = r["schema"]
        assert s["name"] == r["name"]
        assert "description" in s and s["description"]
        assert s["parameters"]["type"] == "object"
        assert "properties" in s["parameters"]
