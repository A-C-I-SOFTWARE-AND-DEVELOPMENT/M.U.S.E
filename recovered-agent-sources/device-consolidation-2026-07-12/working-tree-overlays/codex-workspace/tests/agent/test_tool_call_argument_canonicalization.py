"""Regression tests for cached tool-call JSON canonicalization.

Repeated API turns replay earlier assistant tool calls in the request prefix.  The
normalizer must preserve canonical output while avoiding JSON reparsing for the
same immutable tool-call arguments on every turn.
"""

from agent import conversation_loop as loop


def test_canonicalizer_sorts_keys_and_compacts_json():
    assert loop._canonicalize_tool_call_arguments(
        '{"z": 1, "a": [true, null]}', "example_tool"
    ) == '{"a":[true,null],"z":1}'


def test_canonicalizer_reuses_cached_result_for_unchanged_arguments():
    loop._canonicalize_tool_call_arguments_cached.cache_clear()

    first = loop._canonicalize_tool_call_arguments('{"b":2,"a":1}', "tool")
    after_first = loop._canonicalize_tool_call_arguments_cached.cache_info()
    second = loop._canonicalize_tool_call_arguments('{"b":2,"a":1}', "tool")
    after_second = loop._canonicalize_tool_call_arguments_cached.cache_info()

    assert first == second == '{"a":1,"b":2}'
    assert after_first.misses == 1
    assert after_second.hits == 1


def test_canonicalizer_repairs_invalid_json_once(monkeypatch):
    loop._canonicalize_tool_call_arguments_cached.cache_clear()
    calls = []

    def repair(arguments, tool_name):
        calls.append((arguments, tool_name))
        return '{"repaired":true}'

    monkeypatch.setattr(loop, "_repair_tool_call_arguments", repair)

    assert loop._canonicalize_tool_call_arguments('{"broken"', "tool") == '{"repaired":true}'
    assert loop._canonicalize_tool_call_arguments('{"broken"', "tool") == '{"repaired":true}'
    assert calls == [('{"broken"', "tool")]
