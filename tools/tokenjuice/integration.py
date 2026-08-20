"""TokenJuice entry point used by the agent tool loop.

``compact_tool_output`` is the single integration seam. It is:

* **pass-through safe** — outputs below ``min_input_chars`` or that fail to
  shrink past the ratio gate are returned unchanged;
* **fail-open** — any internal error returns the original text;
* **bounded** — the final inline output is clamped to ``max_inline_chars``.

It does *not* scrub credentials or persist raw output — the caller does that
first (see ``agent/tool_executor.py``). Keeping those concerns separate makes
each unit independently testable.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, cast

from .classify import classify
from .config import CompactionConfig
from .loader import load_rules
from .reduce import reduce_output
from .scrub import scrub_credentials
from .types import CompactionStats, ReduceOptions, ToolExecutionInput

logger = logging.getLogger(__name__)

_CLAMP_MARKER = "\n…[tokenjuice: clamped]"


def extract_command_argv(arguments: Any) -> tuple[Optional[str], Optional[list[str]]]:
    """Derive ``(command, argv)`` from a tool's arguments.

    Handles the common shapes: ``{"command": "git status"}``,
    ``{"command": "git", "args": ["status"]}``, ``{"argv": ["git","status"]}``,
    and ``{"cmd": "..."}``. Returns ``(None, None)`` when not shell-like.
    """
    if not isinstance(arguments, dict):
        return None, None

    argv = arguments.get("argv")
    if isinstance(argv, list) and argv and all(isinstance(x, str) for x in argv):
        # The all(isinstance(x, str)) guard above guarantees list[str].
        return " ".join(argv), cast("list[str]", list(argv))

    cmd = arguments.get("command")
    if not isinstance(cmd, str):
        cmd = arguments.get("cmd")
    if isinstance(cmd, str) and cmd:
        args = arguments.get("args")
        if isinstance(args, list) and all(isinstance(x, str) for x in args):
            full = [cmd, *args]
            return " ".join(full), full
        parts = cmd.split()
        return cmd, (parts or None)

    return None, None


def compact_tool_output(
    tool_name: str,
    arguments: Any,
    output: str,
    exit_code: Optional[int],
    config: Optional[CompactionConfig] = None,
) -> tuple[str, CompactionStats]:
    """Compact ``output`` for ``tool_name``. Returns ``(text, stats)``.

    When ``stats.applied`` is False the returned text is the untouched original.
    """
    cfg = config or CompactionConfig()
    started = time.perf_counter()
    original_chars = len(output or "")
    command, argv = extract_command_argv(arguments)

    def _passthrough(rule_id: str) -> tuple[str, CompactionStats]:
        return output, CompactionStats(
            tool_name=tool_name,
            rule_id=rule_id,
            original_chars=original_chars,
            compacted_chars=original_chars,
            applied=False,
            duration_ms=(time.perf_counter() - started) * 1000,
            command=command,
            exit_code=exit_code,
        )

    if not cfg.enabled:
        return _passthrough("disabled")
    if tool_name in cfg.skip_tools:
        return _passthrough("skip-tool")
    if original_chars < cfg.min_input_chars:
        return _passthrough("too-small")

    try:
        rules = load_rules(
            builtin=cfg.builtin_rules,
            user=cfg.user_rules,
            project=cfg.project_rules,
        )
        inp = ToolExecutionInput(
            tool_name=tool_name,
            command=command,
            argv=argv,
            stdout=output,
            exit_code=exit_code,
        )
        rule = classify(inp, rules)
        if rule is None:
            return _passthrough("no-match")

        opts = ReduceOptions(
            compact_failures=cfg.compact_failures,
            failure_head_lines=cfg.failure_head_lines,
            failure_tail_lines=cfg.failure_tail_lines,
        )
        compacted = reduce_output(rule, inp, opts)

        # Clamp to the configured inline ceiling (line-safe at a boundary).
        if len(compacted) > cfg.max_inline_chars:
            cut = compacted.rfind("\n", 0, cfg.max_inline_chars)
            if cut <= 0:
                cut = cfg.max_inline_chars
            compacted = compacted[:cut] + _CLAMP_MARKER

        compacted_chars = len(compacted)
        ratio = (compacted_chars / original_chars) if original_chars else 1.0
        # Keep the compacted form only if it meaningfully shrank the payload.
        applied = compacted_chars < original_chars and ratio <= (1.0 - cfg.min_ratio_improvement)

        if not applied:
            return _passthrough(rule.id)

        if cfg.debug:
            logger.debug(
                "[tokenjuice] tool=%s rule=%s %d->%d chars ratio=%.2f exit=%s",
                tool_name, rule.id, original_chars, compacted_chars, ratio, exit_code,
            )
        return compacted, CompactionStats(
            tool_name=tool_name,
            rule_id=rule.id,
            original_chars=original_chars,
            compacted_chars=compacted_chars,
            applied=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            command=command,
            exit_code=exit_code,
        )
    except Exception as err:  # fail open — never worse than the original
        logger.debug("[tokenjuice] compaction failed for %s, passing through: %s", tool_name, err)
        return _passthrough("error")


def scrub_and_compact_text(
    tool_name: str,
    arguments: Any,
    text: str,
    exit_code: Optional[int],
    config: Optional[CompactionConfig] = None,
) -> str:
    """Scrub credentials, then compact — returning just the text.

    Convenience for callers (string + multimodal-text paths) that don't need the
    stats. Credential scrubbing always applies; compaction is pass-through safe.
    Fail-open: any error returns the scrubbed (or original) text.
    """
    try:
        scrubbed = scrub_credentials(text)
    except Exception:  # scrubbing must never break the tool loop
        scrubbed = text
    compacted, _ = compact_tool_output(tool_name, arguments, scrubbed, exit_code, config)
    return compacted


def compact_multimodal_text(
    envelope: dict,
    tool_name: str,
    arguments: Any,
    exit_code: Optional[int],
    config: Optional[CompactionConfig] = None,
) -> tuple[dict, bool]:
    """Scrub + compact only the **text** parts of a multimodal tool result.

    The envelope shape is ``{"_multimodal": True, "content": [parts…],
    "text_summary": str?}``. Image (``type != "text"``) parts are preserved
    byte-for-byte; only ``type == "text"`` parts and ``text_summary`` are
    scrubbed/compacted. Returns ``(new_envelope, changed)``; the input is not
    mutated.
    """
    content = envelope.get("content") or []
    new_parts: list = []
    changed = False
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            original = str(part.get("text", ""))
            new_text = scrub_and_compact_text(tool_name, arguments, original, exit_code, config)
            if new_text != original:
                changed = True
            new_part = dict(part)
            new_part["text"] = new_text
            new_parts.append(new_part)
        else:
            new_parts.append(part)  # image / non-text parts untouched

    new_env = dict(envelope)
    new_env["content"] = new_parts

    summary = envelope.get("text_summary")
    if isinstance(summary, str) and summary:
        new_summary = scrub_and_compact_text(tool_name, arguments, summary, exit_code, config)
        if new_summary != summary:
            changed = True
        new_env["text_summary"] = new_summary

    return new_env, changed
