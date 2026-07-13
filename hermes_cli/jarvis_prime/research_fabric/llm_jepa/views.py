"""(text, code) two-view builder for the LLM-JEPA objective.

LLM-JEPA needs paired views of the same knowledge. MUSE already generates two
such views in the course of ordinary work:

* **git issue -> diff** — a commit's message (natural-language intent) paired
  with the patch it produced (the code view).
* **prompt -> result** — a flywheel event's prompt paired with its result /
  produced diff.

This module assembles those pairs into a uniform :class:`TwoView` record,
dedupes them, and (de)serializes them to JSONL so the vendored ``train.py`` can
consume them inside a disposable workspace. It is stdlib-only and torch-free;
git access is via injected runners so it is fully testable offline.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

# A commit-log runner returns (sha, subject, body, diff) tuples. Injectable so
# tests never shell out to git.
GitLogRunner = Callable[[str, int], "list[tuple[str, str, str, str]]"]

# Minimum characters each view must have to be a useful training pair.
_MIN_TEXT = 8
_MIN_CODE = 8


@dataclass(frozen=True)
class TwoView:
    """One paired sample: a text view and a code view of the same knowledge."""

    text: str
    code: str
    source: str = ""  # "git" | "flywheel" | ...
    meta: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        return f"{self.text.strip()}\x00{self.code.strip()}"

    def is_usable(self) -> bool:
        return (
            len(self.text.strip()) >= _MIN_TEXT and len(self.code.strip()) >= _MIN_CODE
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "code": self.code,
            "source": self.source,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TwoView":
        return cls(
            text=str(d.get("text", "")),
            code=str(d.get("code", "")),
            source=str(d.get("source", "")),
            meta=dict(d.get("meta") or {}),
        )


def _default_git_runner(repo_root: str, limit: int) -> "list[tuple[str, str, str, str]]":
    """Read the last ``limit`` non-merge commits as (sha, subject, body, diff)."""

    try:
        shas_out = subprocess.run(
            ["git", "log", "--no-merges", f"-n{limit}", "--pretty=format:%H"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if shas_out.returncode != 0:
        return []
    rows: list[tuple[str, str, str, str]] = []
    for sha in [s for s in shas_out.stdout.splitlines() if s.strip()]:
        try:
            show = subprocess.run(
                [
                    "git",
                    "show",
                    "--no-color",
                    "--pretty=format:%s%x00%b%x00",
                    sha,
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if show.returncode != 0:
            continue
        parts = show.stdout.split("\x00", 2)
        subject = parts[0] if parts else ""
        body = parts[1] if len(parts) > 1 else ""
        diff = parts[2] if len(parts) > 2 else ""
        rows.append((sha, subject.strip(), body.strip(), diff.strip()))
    return rows


def from_git_log(
    repo_root: str = ".",
    *,
    limit: int = 200,
    runner: Optional[GitLogRunner] = None,
) -> "list[TwoView]":
    """Build (commit message, diff) views from git history."""

    run = runner or _default_git_runner
    views: list[TwoView] = []
    for sha, subject, body, diff in run(repo_root, limit):
        text = (subject + ("\n\n" + body if body else "")).strip()
        view = TwoView(
            text=text,
            code=diff,
            source="git",
            meta={"sha": sha},
        )
        if view.is_usable():
            views.append(view)
    return views


def from_flywheel(events: Iterable[dict[str, Any]]) -> "list[TwoView]":
    """Build (prompt, result) views from flywheel-style event dicts.

    Accepts the loose shape flywheel records use: a ``prompt``/``text`` field
    and a ``result``/``diff``/``code`` field, optionally nested under
    ``payload``. Records missing either view are skipped.
    """

    views: list[TwoView] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        raw_payload = ev.get("payload")
        payload = raw_payload if isinstance(raw_payload, dict) else ev
        text = str(
            payload.get("prompt")
            or payload.get("text")
            or payload.get("intent")
            or ""
        )
        code = str(
            payload.get("result")
            or payload.get("diff")
            or payload.get("code")
            or payload.get("patch")
            or ""
        )
        view = TwoView(
            text=text,
            code=code,
            source="flywheel",
            meta={"event": str(ev.get("event") or ev.get("kind") or "")},
        )
        if view.is_usable():
            views.append(view)
    return views


def build_views(
    *sources: Iterable[TwoView],
    max_pairs: Optional[int] = None,
) -> "list[TwoView]":
    """Merge view sources, drop duplicates (by text+code), and cap the count."""

    seen: set[str] = set()
    merged: list[TwoView] = []
    for source in sources:
        for view in source:
            if not view.is_usable():
                continue
            k = view.key()
            if k in seen:
                continue
            seen.add(k)
            merged.append(view)
            if max_pairs is not None and len(merged) >= max_pairs:
                return merged
    return merged


def views_to_jsonl(views: Iterable[TwoView], path: Path) -> Path:
    """Write ``views`` to ``path`` as JSONL and return the path."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(v.to_dict(), sort_keys=True) for v in views]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def views_from_jsonl(path: Path) -> "list[TwoView]":
    """Read a JSONL file of two-view records."""

    path = Path(path)
    if not path.exists():
        return []
    out: list[TwoView] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(TwoView.from_dict(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return out
