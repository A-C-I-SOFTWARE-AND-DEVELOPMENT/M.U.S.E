"""Text primitives for TokenJuice reduction.

Pure functions: ANSI stripping, adjacent-dedupe, empty-edge trimming, JSON
pretty-printing, and Unicode-width-safe head/tail truncation. No external state.
"""

from __future__ import annotations

import json
import re

# CSI / SGR and other ANSI escape sequences.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences while preserving printable Unicode."""
    return _ANSI_RE.sub("", text)


def dedupe_adjacent(lines: list[str]) -> list[str]:
    """Collapse runs of identical adjacent lines to a single line."""
    out: list[str] = []
    prev: str | None = None
    for line in lines:
        if line != prev:
            out.append(line)
        prev = line
    return out


def trim_empty_edges(lines: list[str]) -> list[str]:
    """Drop leading and trailing blank/whitespace-only lines."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def maybe_pretty_print_json(text: str) -> str:
    """Pretty-print ``text`` if it is a single JSON document, else return as-is."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return text
    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        return text
    return json.dumps(parsed, indent=2, ensure_ascii=False, sort_keys=False)


def head_tail(lines: list[str], head: int, tail: int) -> list[str]:
    """Keep the first ``head`` and last ``tail`` lines with an elision marker.

    Width-safe: operates on whole lines, so it never splits a multi-byte or
    grapheme-cluster character. When the line count already fits, returns the
    input unchanged.
    """
    if head < 0:
        head = 0
    if tail < 0:
        tail = 0
    n = len(lines)
    if n <= head + tail or n <= 1:
        return lines
    elided = n - head - tail
    marker = f"… {elided} more line{'s' if elided != 1 else ''} …"
    return lines[:head] + [marker] + (lines[n - tail :] if tail else [])
