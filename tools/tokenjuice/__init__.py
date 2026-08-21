"""TokenJuice — terminal-output compaction for Hermes tool results.

Clean-room Python reimplementation of TokenJuice-style rule-based output
compaction (behavior from the public MIT upstream ``vincentkoc/tokenjuice``;
rule JSON is the MIT-licensed vendored set — see ``THIRD_PARTY_NOTICES.md``).
No GPL source is copied.

This package compacts **tool output** before it enters the model context, and
runs after credential scrubbing and before the existing size-threshold
persistence/budget layers in ``tools/tool_result_storage.py``.

(The original text here disambiguated this from a downstream *context
compiler* of the same name. That module is not part of this repo, so the
comparison pointed at nothing and has been removed.)

Public surface:

* :func:`compact_tool_output` — the entry point used by the tool loop.
* :func:`scrub_credentials` — redact secrets (call before compaction).
* :func:`record_raw_output` — preserve full pre-scrub output for debugging.
* :class:`CompactionConfig` / :func:`load_compaction_config` — configuration.
"""

from __future__ import annotations

from .config import CompactionConfig
from .integration import (
    compact_multimodal_text,
    compact_tool_output,
    extract_command_argv,
    scrub_and_compact_text,
)
from .raw_log import record as record_raw_output
from .scrub import scrub_credentials
from .types import CompactionStats

__all__ = [
    "compact_tool_output",
    "compact_multimodal_text",
    "scrub_and_compact_text",
    "extract_command_argv",
    "scrub_credentials",
    "record_raw_output",
    "CompactionConfig",
    "CompactionStats",
    "load_compaction_config",
]


def load_compaction_config(full_config: dict | None) -> CompactionConfig:
    """Build a :class:`CompactionConfig` from a parsed Hermes config mapping.

    Accepts the full config dict and reads ``tool_output.compaction.*``; missing
    keys fall back to safe defaults. Pass ``None`` for all-defaults.
    """
    return CompactionConfig.from_mapping(full_config)
