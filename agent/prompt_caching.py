"""Anthropic prompt caching strategy.

Single layout: ``system_and_3``. 4 cache_control breakpoints — system
prompt + last 3 non-system messages, all at the same TTL (5m or 1h).
Reduces input token costs by ~75% on multi-turn conversations within a
single session.

Pure functions -- no class state, no AIAgent dependency.
"""

import copy
from typing import Any, Dict, List


def _apply_cache_marker(msg: dict, cache_marker: dict, native_anthropic: bool = False) -> None:
    """Add cache_control to a single message, handling all format variations."""
    role = msg.get("role", "")
    content = msg.get("content")

    if role == "tool":
        if native_anthropic:
            msg["cache_control"] = cache_marker
        return

    if content is None or content == "":
        msg["cache_control"] = cache_marker
        return

    if isinstance(content, str):
        msg["content"] = [
            {"type": "text", "text": content, "cache_control": cache_marker}
        ]
        return

    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict):
            last["cache_control"] = cache_marker


def _build_marker(ttl: str) -> Dict[str, str]:
    """Build a cache_control marker dict for the given TTL ('5m' or '1h')."""
    marker: Dict[str, str] = {"type": "ephemeral"}
    if ttl == "1h":
        marker["ttl"] = "1h"
    return marker


def apply_anthropic_cache_control(
    api_messages: List[Dict[str, Any]],
    cache_ttl: str = "5m",
    native_anthropic: bool = False,
) -> List[Dict[str, Any]]:
    """Apply system_and_3 caching strategy to messages for Anthropic models.

    Places up to 4 cache_control breakpoints: system prompt + last 3 non-system
    messages, all at the same TTL.

    Returns:
        A new list with cache_control breakpoints injected. Only the (<=4)
        messages that receive a marker are deep-copied; the rest are shared by
        reference from ``api_messages`` (the caller already builds those as
        fresh per-turn shallow copies), so the input list is never mutated.
    """
    if not api_messages:
        return list(api_messages)

    # Shallow list copy; deep-copy ONLY the messages we actually mark, right
    # before mutating them. This avoids deep-copying the entire conversation
    # history on every turn (the previous ``copy.deepcopy(api_messages)`` cost
    # scaled linearly with history size and ran per-turn on the default Claude
    # path). The wire payload is byte-identical: marked messages are copied
    # before mutation, unmarked messages are unchanged.
    messages = list(api_messages)

    marker = _build_marker(cache_ttl)

    breakpoints_used = 0
    marked: List[int] = []

    if messages[0].get("role") == "system":
        marked.append(0)
        breakpoints_used += 1

    remaining = 4 - breakpoints_used
    non_sys = [i for i in range(len(messages)) if messages[i].get("role") != "system"]
    marked.extend(non_sys[-remaining:])

    for idx in marked:
        messages[idx] = copy.deepcopy(messages[idx])
        _apply_cache_marker(messages[idx], marker, native_anthropic=native_anthropic)

    return messages
