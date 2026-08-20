"""TokenJuice configuration.

Defaults match the documented ``tool_output.compaction`` block in
``cli-config.yaml``. ``CompactionConfig.from_mapping`` builds a config from the
parsed YAML/dict so the loader in ``hermes_cli/config.py`` can pass through a
plain mapping without importing this package eagerly.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

# File-inspection tools whose output should pass through unchanged by default —
# the model usually needs the verbatim bytes (read_file/cat/sed/jq/...).
DEFAULT_SKIP_TOOLS: tuple[str, ...] = (
    "read_file",
    "view",
    "cat",
    "sed",
    "jq",
    "head",
    "tail",
    "read",
    "open_file",
)


@dataclass(frozen=True)
class CompactionConfig:
    enabled: bool = True
    min_input_chars: int = 512
    min_ratio_improvement: float = 0.05
    max_inline_chars: int = 1200
    preserve_raw: bool = True
    compact_failures: bool = True
    failure_head_lines: int = 80
    failure_tail_lines: int = 120
    builtin_rules: bool = True
    user_rules: bool = True
    project_rules: bool = True
    skip_tools: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_SKIP_TOOLS))
    debug: bool = False

    @staticmethod
    def from_mapping(data: Mapping[str, Any] | None) -> "CompactionConfig":
        """Build a config from a (possibly nested) mapping.

        Accepts either the inner ``compaction`` mapping or a ``tool_output``
        wrapper. Unknown keys are ignored; missing keys take defaults.
        """
        cfg = CompactionConfig()
        if not data:
            return cfg
        if "tool_output" in data and isinstance(data["tool_output"], Mapping):
            data = data["tool_output"]
        if "compaction" in data and isinstance(data["compaction"], Mapping):
            data = data["compaction"]

        skip = data.get("skip_tools")
        skip_set = frozenset(skip) if skip is not None else cfg.skip_tools
        return replace(
            cfg,
            enabled=bool(data.get("enabled", cfg.enabled)),
            min_input_chars=int(data.get("min_input_chars", cfg.min_input_chars)),
            min_ratio_improvement=float(data.get("min_ratio_improvement", cfg.min_ratio_improvement)),
            max_inline_chars=int(data.get("max_inline_chars", cfg.max_inline_chars)),
            preserve_raw=bool(data.get("preserve_raw", cfg.preserve_raw)),
            compact_failures=bool(data.get("compact_failures", cfg.compact_failures)),
            failure_head_lines=int(data.get("failure_head_lines", cfg.failure_head_lines)),
            failure_tail_lines=int(data.get("failure_tail_lines", cfg.failure_tail_lines)),
            builtin_rules=bool(data.get("builtin_rules", cfg.builtin_rules)),
            user_rules=bool(data.get("user_rules", cfg.user_rules)),
            project_rules=bool(data.get("project_rules", cfg.project_rules)),
            skip_tools=skip_set,
            debug=bool(data.get("debug", cfg.debug)),
        )


_CACHED: Optional[CompactionConfig] = None


def load_active_config(force_reload: bool = False) -> CompactionConfig:
    """Resolve the active compaction config once, cached for the process.

    Resolution order:
    1. ``HERMES_TOKENJUICE=off|0|false|disabled`` env var → a hard kill switch
       (returns a disabled config regardless of file config).
    2. ``tool_output.compaction.*`` from the Hermes config file via
       ``hermes_cli.config.load_config`` (lazy import; failures fall back).
    3. Built-in defaults.

    Kept self-contained so the tool loop doesn't need to thread config through
    the ``AIAgent`` constructor.
    """
    global _CACHED
    if _CACHED is not None and not force_reload:
        return _CACHED

    kill = (os.environ.get("HERMES_TOKENJUICE") or "").strip().lower()
    if kill in {"off", "0", "false", "disabled", "no"}:
        _CACHED = replace(CompactionConfig(), enabled=False)
        return _CACHED

    data: Mapping[str, Any] | None = None
    try:
        from hermes_cli.config import load_config  # lazy: avoid import cycles

        full = load_config()
        if isinstance(full, Mapping):
            data = full
    except Exception as err:  # config unavailable → defaults
        logger.debug("[tokenjuice] load_active_config: using defaults (%s)", err)

    _CACHED = CompactionConfig.from_mapping(data)
    return _CACHED
