"""Rule classification — pick the most specific matching rule.

A rule matches only when **every** declared constraint in its ``match`` block is
satisfied. Specificity is the weighted count of declared constraints; the
highest-specificity match wins, with the rule ``priority`` field as a tiebreak.
A rule with an empty ``match`` (e.g. ``generic/fallback``) matches everything at
specificity 0, so it is chosen only when nothing more specific matches.
"""

from __future__ import annotations

from typing import Optional

from .types import JsonRule, RuleMatch, ToolExecutionInput


def _argv(inp: ToolExecutionInput) -> list[str]:
    if inp.argv:
        return inp.argv
    if inp.command:
        return inp.command.split()
    return []


def _command(inp: ToolExecutionInput) -> str:
    if inp.command:
        return inp.command
    if inp.argv:
        return " ".join(inp.argv)
    return ""


def _group_in_argv(group: list[str], argv_set: set[str]) -> bool:
    return all(tok in argv_set for tok in group)


def _match_score(m: RuleMatch, inp: ToolExecutionInput) -> Optional[int]:
    """Return weighted specificity if the rule matches, else ``None``."""
    argv = _argv(inp)
    argv_set = set(argv)
    command = _command(inp)
    score = 0

    if m.tool_names is not None:
        if inp.tool_name not in m.tool_names:
            return None
        score += 3

    if m.argv0 is not None:
        if not argv or argv[0] not in m.argv0:
            return None
        score += 10

    if m.argv_includes is not None:
        if not all(_group_in_argv(g, argv_set) for g in m.argv_includes):
            return None
        score += 5 * len(m.argv_includes)

    if m.argv_includes_any is not None:
        if not any(_group_in_argv(g, argv_set) for g in m.argv_includes_any):
            return None
        score += 4

    if m.command_includes is not None:
        if not all(s in command for s in m.command_includes):
            return None
        score += 4 * len(m.command_includes)

    if m.command_includes_any is not None:
        if not any(s in command for s in m.command_includes_any):
            return None
        score += 3

    return score


def classify(inp: ToolExecutionInput, rules: list[JsonRule]) -> Optional[JsonRule]:
    """Return the best-matching rule, or ``None`` if none match."""
    best: Optional[JsonRule] = None
    best_key: tuple[int, int] = (-1, -1)
    for rule in rules:
        score = _match_score(rule.match, inp)
        if score is None:
            continue
        key = (score, rule.priority)
        if key > best_key:
            best_key = key
            best = rule
    return best
