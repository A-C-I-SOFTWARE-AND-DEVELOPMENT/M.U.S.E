"""Task-aware prefill injection from ``~/.hermes/prefills/``."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from hermes_cli.harness.config import HarnessSettings

logger = logging.getLogger(__name__)

_TASK_PATTERNS: Dict[str, Sequence[re.Pattern[str]]] = {
    "debugging": (
        re.compile(r"\b(debug|bug|traceback|exception|fix|regress)\b", re.I),
    ),
    "review": (
        re.compile(r"\b(review|critique|pr\b|pull request|code review)\b", re.I),
    ),
    "research": (
        re.compile(r"\b(research|investigate|survey|compare|benchmark)\b", re.I),
    ),
    "planning": (
        re.compile(r"\b(plan|architect|design|roadmap|spec)\b", re.I),
    ),
    "orchestration": (
        re.compile(r"\b(orchestrat|delegat|swarm|subagent|parallel work)\b", re.I),
    ),
    "creative": (
        re.compile(r"\b(story|creative|narrative|brand|copywrit)\b", re.I),
    ),
    "coding": (
        re.compile(r"\b(code|implement|refactor|write|patch|typescript|python|react)\b", re.I),
    ),
}


def detect_task_type(prompt: str, settings: HarnessSettings) -> str:
    """Return the best-matching task key for *prompt*."""
    text = (prompt or "").strip()
    if not text:
        default_name = settings.prefill_default or "coding.md"
        return Path(default_name).stem
    for task, patterns in _TASK_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            return task
    return Path(settings.prefill_default or "coding.md").stem


def load_task_prefill(
    settings: HarnessSettings,
    task_type: Optional[str] = None,
    prompt: str = "",
) -> List[Dict[str, Any]]:
    """Load markdown task prefill as a single system message (empty if disabled)."""
    if not settings.enabled or not settings.prefill_enabled:
        return []
    task = task_type or (
        detect_task_type(prompt, settings) if settings.prefill_auto_detect else Path(settings.prefill_default).stem
    )
    filename = settings.task_prefills.get(task) or settings.prefill_default
    directory = settings.prefill_directory
    if directory is None or not filename:
        return []
    path = Path(directory) / filename
    if not path.is_file():
        logger.debug("harness prefill missing: %s", path)
        return []
    try:
        body = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("harness prefill read failed %s: %s", path, exc)
        return []
    if not body:
        return []
    return [
        {
            "role": "system",
            "content": f"[harness:{task}]\n{body}",
            "_harness_stage": "prefill",
            "_harness_task": task,
        }
    ]


def merge_prefills(
    base: Sequence[Dict[str, Any]],
    harness_msgs: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Prepend harness task prefills ahead of static prefill.json messages."""
    return list(harness_msgs) + list(base)
