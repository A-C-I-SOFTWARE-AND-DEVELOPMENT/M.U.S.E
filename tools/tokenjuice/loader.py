"""Rule loading with a three-layer overlay.

Priority (ascending): builtin (bundled MIT JSON) → user
(``~/.config/tokenjuice/rules/``) → project (``.tokenjuice/rules/`` under cwd).
A later layer overrides an earlier one with the same rule ``id``. The builtin
set is cached process-wide; user/project layers are cached per directory mtime
so on-disk edits are picked up without a restart.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .types import JsonRule

_RULES_DIR = Path(__file__).parent / "rules"


def _load_dir(directory: Path, origin: str) -> list[JsonRule]:
    rules: list[JsonRule] = []
    if not directory.is_dir():
        return rules
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Corrupt/unreadable rule file is skipped, never fatal.
            continue
        try:
            rules.append(JsonRule.from_dict(data, origin=origin))
        except (KeyError, TypeError):
            continue
    return rules


@lru_cache(maxsize=1)
def load_builtin_rules() -> tuple[JsonRule, ...]:
    return tuple(_load_dir(_RULES_DIR, "builtin"))


def _user_rules_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "tokenjuice" / "rules"


def _project_rules_dir() -> Path:
    return Path.cwd() / ".tokenjuice" / "rules"


def _dir_signature(directory: Path) -> float:
    try:
        return directory.stat().st_mtime
    except OSError:
        return -1.0


@lru_cache(maxsize=8)
def _load_overlay_cached(path_str: str, origin: str, _sig: float) -> tuple[JsonRule, ...]:
    return tuple(_load_dir(Path(path_str), origin))


def load_rules(builtin: bool = True, user: bool = True, project: bool = True) -> list[JsonRule]:
    """Return the overlaid rule set, last-wins by ``id``.

    Layers are merged in priority order so a project rule shadows a user rule
    shadows a builtin rule with the same ``id``.
    """
    by_id: dict[str, JsonRule] = {}
    if builtin:
        for r in load_builtin_rules():
            by_id[r.id] = r
    if user:
        d = _user_rules_dir()
        for r in _load_overlay_cached(str(d), "user", _dir_signature(d)):
            by_id[r.id] = r
    if project:
        d = _project_rules_dir()
        for r in _load_overlay_cached(str(d), "project", _dir_signature(d)):
            by_id[r.id] = r
    return list(by_id.values())
