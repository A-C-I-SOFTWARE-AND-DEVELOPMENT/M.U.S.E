"""The reduction pipeline — apply a rule to tool output.

transforms → filters (skip/keep) → counters → summarize (head/tail, failure
aware) → counter summary → onEmpty / matchOutput. Pure and deterministic for a
given (rule, input).
"""

from __future__ import annotations

import re
from typing import Optional

from . import text as _text
from .types import JsonRule, ReduceOptions, RuleCounter, ToolExecutionInput


def _compile(pattern: str, flags: Optional[str]) -> Optional[re.Pattern]:
    f = 0
    if flags and "i" in flags.lower():
        f |= re.IGNORECASE
    try:
        return re.compile(pattern, f)
    except re.error:
        # Invalid regex in a rule must never crash reduction.
        return None


def _count(lines: list[str], counters: list[RuleCounter]) -> list[str]:
    out: list[str] = []
    for c in counters:
        rx = _compile(c.pattern, c.flags)
        if rx is None:
            continue
        n = sum(1 for ln in lines if rx.search(ln))
        if n:
            out.append(f"{n} {c.name}{'s' if n != 1 else ''}")
    return out


def reduce_output(rule: JsonRule, inp: ToolExecutionInput, opts: ReduceOptions) -> str:
    """Reduce ``inp.stdout`` per ``rule``. Returns the compacted text."""
    raw = inp.stdout or ""
    failed = bool(inp.exit_code)

    text = raw
    tr = rule.transforms
    if tr and tr.strip_ansi:
        text = _text.strip_ansi(text)
    if tr and tr.pretty_print_json:
        text = _text.maybe_pretty_print_json(text)

    lines = text.split("\n")
    if tr and tr.trim_empty_edges:
        lines = _text.trim_empty_edges(lines)
    if tr and tr.dedupe_adjacent:
        lines = _text.dedupe_adjacent(lines)

    # Counters sampled pre- or post-keep per counterSource (default postKeep).
    pre_keep_lines = list(lines)

    # Filters.
    if rule.filters:
        if rule.filters.skip_patterns:
            skips = [rx for p in rule.filters.skip_patterns if (rx := _compile(p, None))]
            lines = [ln for ln in lines if not any(rx.search(ln) for rx in skips)]
        if rule.filters.keep_patterns:
            keeps = [rx for p in rule.filters.keep_patterns if (rx := _compile(p, None))]
            if keeps:
                lines = [ln for ln in lines if any(rx.search(ln) for rx in keeps)]

    # matchOutput: canned messages mapped from patterns (checked against raw).
    if rule.match_output:
        for om in rule.match_output:
            rx = _compile(om.pattern, om.flags)
            if rx and rx.search(raw):
                return om.message

    counter_src = pre_keep_lines if rule.counter_source == "preKeep" else lines
    counter_summ = _count(counter_src, rule.counters) if rule.counters else []

    # Summarize (head/tail), failure-aware.
    if failed and opts.compact_failures and rule.failure and rule.failure.preserve_on_failure:
        head = rule.failure.head if rule.failure.head is not None else opts.failure_head_lines
        tail = rule.failure.tail if rule.failure.tail is not None else opts.failure_tail_lines
        lines = _text.head_tail(lines, head, tail)
    elif rule.summarize and (rule.summarize.head is not None or rule.summarize.tail is not None):
        head = rule.summarize.head or 0
        tail = rule.summarize.tail or 0
        lines = _text.head_tail(lines, head, tail)

    if not [ln for ln in lines if ln.strip()]:
        if rule.on_empty:
            return rule.on_empty
        if counter_summ:
            return f"({', '.join(counter_summ)})"

    body = "\n".join(lines)
    if counter_summ:
        body = f"{body}\n({', '.join(counter_summ)})" if body.strip() else f"({', '.join(counter_summ)})"
    return body
