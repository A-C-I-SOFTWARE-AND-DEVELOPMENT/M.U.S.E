"""Skill router — pick at most N skills from context_engineering.yaml."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from hermes_cli.harness.config import HarnessSettings
from hermes_cli.harness.prefills import detect_task_type

logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("skill_router: failed to read %s: %s", path, exc)
        return {}
    return data if isinstance(data, Mapping) else {}


def route_skills(
    settings: HarnessSettings,
    prompt: str = "",
    task_type: Optional[str] = None,
    max_skills: Optional[int] = None,
) -> List[str]:
    """Return ordered skill names for the detected task (may be empty)."""
    if not settings.enabled or not settings.context_enabled or not settings.skill_router:
        return []
    cfg_path = settings.context_config
    if cfg_path is None or not cfg_path.is_file():
        return []
    data = _load_yaml(cfg_path)
    router = data.get("skill_router") if isinstance(data.get("skill_router"), Mapping) else {}
    if not router.get("enabled", True):
        return []
    cap = max_skills if max_skills is not None else int(router.get("max_skills") or 3)
    cap = max(1, min(cap, int(router.get("max_skills") or 3)))
    task = task_type or detect_task_type(prompt, settings)
    task_skills = router.get("task_skills") if isinstance(router.get("task_skills"), Mapping) else {}
    entry = task_skills.get(task) if isinstance(task_skills.get(task), Mapping) else {}
    names: List[str] = []
    for key in ("primary", "secondary"):
        bucket = entry.get(key)
        if isinstance(bucket, Sequence) and not isinstance(bucket, (str, bytes)):
            for item in bucket:
                name = str(item).strip()
                if name and name not in names:
                    names.append(name)
                if len(names) >= cap:
                    return names[:cap]
    return names[:cap]


def skill_hint_message(skills: Sequence[str]) -> Optional[Dict[str, Any]]:
    if not skills:
        return None
    joined = ", ".join(skills)
    return {
        "role": "system",
        "content": (
            f"[harness:skill_router] Prefer these skills for this task "
            f"(load via skill tools if needed): {joined}."
        ),
        "_harness_stage": "prefill",
        "_harness_skills": list(skills),
    }
