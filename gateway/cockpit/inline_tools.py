"""Bounded, read-only inline tools for the cockpit chat turn.

The chat responder (``gateway/cockpit/agent.py``) can run a *tiny,
allowlisted, strictly read-only* set of repo-inspection operations inline
so the mobile cockpit shows real tool activity ("searched 12 files",
"read run_agent.py", "git status: clean") instead of a blank pause.

This is deliberately **not** the worker execution engine and not the full
agent toolset:

* Every operation is read-only — no writes, no network, no shell beyond a
  fixed ``git status``/``git diff --stat`` read.
* Output is size-capped and secret-redacted before it leaves this module.
* Anything irreversible/external is **never** here — those stay owner
  gates surfaced by the JARVIS route, executed nowhere in the chat turn.

The result of each op is a :class:`ToolResult` the responder turns into a
``tool_call`` wire chunk. Callers decide *whether* to run a tool from the
JARVIS route; this module decides *how*, safely.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Hard caps so a chat turn can never spend real time or memory here.
# The file cap keeps a single chat turn well under ~half a second even on a
# large repo while still covering the source tree; results are best-effort
# "what did the agent look at" visibility, not an exhaustive index.
_MAX_FILES_SCANNED = 1500
_MAX_MATCHES = 20
_MAX_READ_BYTES = 4_000
_MAX_SUMMARY = 200
_GIT_TIMEOUT_S = 5

# Directories we never descend into (noise / large / not source).
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "build",
    ".gradle",
    "__pycache__",
    ".idea",
    "dist",
    "out",
    ".venv",
    "venv",
}

# Only inspect text-ish source files.
_TEXT_SUFFIXES = {
    ".py", ".kt", ".kts", ".java", ".md", ".txt", ".yaml", ".yml",
    ".json", ".toml", ".gradle", ".cfg", ".ini", ".sh", ".xml",
}


@dataclass
class ToolResult:
    """Outcome of one inline tool run, ready to become a ``tool_call`` chunk."""

    name: str
    summary: str
    status: str = "OK"  # OK | FAIL
    detail: str | None = None
    # Optional structured extras the responder may fold into prose.
    extras: dict = field(default_factory=dict)


def _repo_root() -> Path:
    """Best-effort repo root: env override, else this file's repo, else cwd."""
    override = os.environ.get("HERMES_REPO_ROOT")
    if override and Path(override).is_dir():
        return Path(override)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / "AGENTS.md").exists():
            return parent
    return Path.cwd()


def _scrub(text: str) -> str:
    if not text:
        return text
    try:
        from hermes_cli.secrets_policy import redact

        return redact(text)
    except Exception:  # pragma: no cover - redaction is best-effort
        return text


def _iter_source_files(root: Path):
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in place so os.walk doesn't descend them.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() not in _TEXT_SUFFIXES:
                continue
            scanned += 1
            if scanned > _MAX_FILES_SCANNED:
                return
            yield Path(dirpath) / name


def repo_grep(term: str) -> ToolResult:
    """Search source files for ``term`` (literal, case-insensitive).

    Bounded: at most ``_MAX_FILES_SCANNED`` files, ``_MAX_MATCHES`` hits.
    Returns relative paths only — never file contents.
    """
    term = (term or "").strip()
    if not term:
        return ToolResult("repo_grep", "no search term", status="FAIL")
    root = _repo_root()
    needle = term.lower()
    hits: list[str] = []
    files_with_hit = 0
    try:
        for path in _iter_source_files(root):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if needle in text.lower():
                files_with_hit += 1
                rel = str(path.relative_to(root))
                if len(hits) < _MAX_MATCHES:
                    hits.append(rel)
    except Exception as exc:  # pragma: no cover - defensive
        return ToolResult("repo_grep", f"search failed: {exc}", status="FAIL")
    summary = f'"{term}" → {files_with_hit} file(s)'
    detail = "\n".join(hits) if hits else "(no matches)"
    return ToolResult(
        "repo_grep",
        _scrub(summary)[:_MAX_SUMMARY],
        detail=_scrub(detail),
        extras={"files": files_with_hit},
    )


def repo_read(rel_path: str) -> ToolResult:
    """Read a bounded head slice of a single repo file.

    Path-traversal safe: the resolved target must stay under the repo root.
    """
    rel_path = (rel_path or "").strip()
    if not rel_path:
        return ToolResult("repo_read", "no path given", status="FAIL")
    root = _repo_root()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return ToolResult("repo_read", "path outside repo", status="FAIL")
    if not target.is_file():
        return ToolResult("repo_read", f"not a file: {rel_path}", status="FAIL")
    try:
        raw = target.read_bytes()[:_MAX_READ_BYTES]
        text = raw.decode("utf-8", errors="ignore")
    except OSError as exc:
        return ToolResult("repo_read", f"read failed: {exc}", status="FAIL")
    truncated = target.stat().st_size > _MAX_READ_BYTES
    summary = f"read {rel_path} ({len(raw)} bytes{', truncated' if truncated else ''})"
    return ToolResult(
        "repo_read",
        _scrub(summary)[:_MAX_SUMMARY],
        detail=_scrub(text),
    )


def git_status() -> ToolResult:
    """Read-only ``git status`` summary (porcelain). Never mutates."""
    root = _repo_root()
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--branch"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolResult("git_status", f"git unavailable: {exc}", status="FAIL")
    if proc.returncode != 0:
        return ToolResult(
            "git_status",
            "not a git repo" if "not a git" in proc.stderr.lower() else "git failed",
            status="FAIL",
        )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    branch = next((ln[3:] for ln in lines if ln.startswith("## ")), "?")
    changed = [ln for ln in lines if not ln.startswith("## ")]
    # Branch refs aren't secrets (and feature-branch names trip the
    # high-entropy redactor), so the summary is left unscrubbed; the file
    # list in ``detail`` can contain paths and is scrubbed.
    summary = f"{branch} — {'clean' if not changed else f'{len(changed)} change(s)'}"
    detail = "\n".join(changed[:_MAX_MATCHES]) if changed else "working tree clean"
    return ToolResult(
        "git_status",
        summary[:_MAX_SUMMARY],
        detail=_scrub(detail),
        extras={"changes": len(changed)},
    )


# ── Term extraction (turn a prompt into a safe grep term) ────────────────

_QUOTED = re.compile(r"[\"'`]([^\"'`]{2,60})[\"'`]")
_CODEISH = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{3,40})\b")
_STOPWORDS = {
    "audit", "this", "repo", "repository", "the", "fix", "bug", "run",
    "tests", "test", "review", "patch", "open", "please", "could", "would",
    "find", "search", "look", "where", "what", "show", "tell", "about",
}


def extract_grep_term(prompt: str) -> str | None:
    """Pick a safe, useful search term from a coding prompt, or ``None``.

    Prefers an explicitly quoted token; falls back to the first code-ish
    identifier that isn't a command stopword. Returns ``None`` when nothing
    sensible is found (the responder then skips the grep tool).
    """
    if not prompt:
        return None
    m = _QUOTED.search(prompt)
    if m:
        return m.group(1).strip()
    for token in _CODEISH.findall(prompt):
        if token.lower() not in _STOPWORDS:
            return token
    return None


__all__ = [
    "ToolResult",
    "repo_grep",
    "repo_read",
    "git_status",
    "extract_grep_term",
]
