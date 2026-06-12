"""Local GitHub activity collector for the user-profile builder.

This module is the *read-only*, local-first data layer behind
:mod:`muse_cli.user_profile_builder`. It gathers signals from three
sources, in order of decreasing trust and increasing cost:

1. **Local git history** in the current checkout (always available when
   inside a git repo). Parsed via ``git log --numstat``.
2. **GitHub CLI** (``gh``) for PR / issue titles + bodies when the user
   has it installed and authenticated.
3. **GitHub REST API** (HTTPS, no third-party libs) as a last resort
   when only ``GITHUB_TOKEN`` is configured.

Design rules
------------
- **Explicit opt-in.** Nothing here reads beyond the current repo unless
  the caller passes a remote slug. The builder wraps this with an
  approval prompt; this module does not.
- **No secrets stored.** Tokens are read from env / git-credentials at
  call time and never persisted to disk. Returned records contain
  titles, summaries, file paths, additions/deletions, and timestamps —
  not raw file blobs.
- **Defaults to six months.** The Phase 07 mission specifies the last
  six months as the rolling window; callers can override via
  ``since_days``.
- **Cheap to test.** All shell-outs and HTTP calls live behind small
  helper functions that the test suite monkey-patches.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "Commit",
    "PullRequest",
    "Issue",
    "HistorySnapshot",
    "compute_since",
    "iso_since",
    "have_git",
    "have_gh",
    "have_gh_auth",
    "get_github_token",
    "collect_local_commits",
    "collect_gh_pull_requests",
    "collect_gh_issues",
    "collect_api_pull_requests",
    "collect_api_issues",
    "collect_history",
    "summarize_commits",
    "summarize_pull_requests",
    "summarize_issues",
]

# The Phase 07 mission says "last six months" — keep the magic number
# in one place so the docs, the CLI, and the tests all agree.
DEFAULT_WINDOW_DAYS = 183


# ── dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class Commit:
    """One commit harvested from local ``git log``.

    ``additions``/``deletions`` come from ``--numstat`` and may be ``0``
    for binary files, which git reports as ``-``.
    """

    sha: str
    author: str
    email: str
    timestamp: str
    subject: str
    body: str = ""
    files: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0

    @property
    def first_line(self) -> str:
        return self.subject.strip().splitlines()[0] if self.subject else ""


@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    state: str
    created_at: str
    merged_at: Optional[str]
    author: str
    repo: str
    labels: list[str] = field(default_factory=list)
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None


@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str
    created_at: str
    closed_at: Optional[str]
    author: str
    repo: str
    labels: list[str] = field(default_factory=list)


@dataclass
class HistorySnapshot:
    """All the raw signal collected for a single profile-build run."""

    user: Optional[str]
    since: str
    window_days: int
    commits: list[Commit] = field(default_factory=list)
    pull_requests: list[PullRequest] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "user": self.user,
            "since": self.since,
            "window_days": self.window_days,
            "commits": [asdict(c) for c in self.commits],
            "pull_requests": [asdict(p) for p in self.pull_requests],
            "issues": [asdict(i) for i in self.issues],
            "sources_used": list(self.sources_used),
            "notes": list(self.notes),
        }


# ── time helpers ────────────────────────────────────────────────────────────


def compute_since(window_days: int = DEFAULT_WINDOW_DAYS, *, now: Optional[datetime] = None) -> datetime:
    """Return the cutoff datetime (UTC) for the window."""

    base = now if now is not None else datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base - timedelta(days=max(1, int(window_days)))


def iso_since(window_days: int = DEFAULT_WINDOW_DAYS, *, now: Optional[datetime] = None) -> str:
    """ISO-8601 form of the cutoff (used for ``git log --since`` etc.)."""

    return compute_since(window_days, now=now).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── environment probing ─────────────────────────────────────────────────────


def _which(cmd: str) -> bool:
    try:
        return subprocess.run(
            ["which", cmd], check=False, capture_output=True, text=True
        ).returncode == 0
    except FileNotFoundError:
        return False


def have_git() -> bool:
    return _which("git")


def have_gh() -> bool:
    return _which("gh")


def have_gh_auth() -> bool:
    if not have_gh():
        return False
    try:
        out = subprocess.run(
            ["gh", "auth", "status"], check=False, capture_output=True, text=True
        )
        return out.returncode == 0
    except FileNotFoundError:
        return False


def get_github_token(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Look up a GitHub token from environment without persisting it."""

    source: Mapping[str, str] = env if env is not None else os.environ
    for var in ("GITHUB_TOKEN", "GH_TOKEN", "HERMES_GITHUB_TOKEN"):
        token = source.get(var)
        if token:
            return token.strip() or None
    return None


# ── local git collector ────────────────────────────────────────────────────


# git log format: NUL-terminated records, '\x1e' field separator inside.
_GIT_LOG_FORMAT = "%H%x1e%an%x1e%ae%x1e%aI%x1e%s%x1e%b"


def _run_git(args: Sequence[str], *, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def collect_local_commits(
    repo_root: Path,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    author: Optional[str] = None,
    now: Optional[datetime] = None,
    max_commits: int = 2000,
) -> list[Commit]:
    """Parse ``git log --numstat`` output into :class:`Commit` records.

    The default ``max_commits`` cap keeps runtime bounded for repos with
    >10k commits in the window. The cap is intentionally generous;
    callers can lower it for fast paths.
    """

    if not repo_root.exists():
        return []

    since = iso_since(window_days, now=now)
    args = [
        "log",
        f"--since={since}",
        f"--pretty=format:%x1f{_GIT_LOG_FORMAT}",
        "--numstat",
        f"--max-count={max(1, max_commits)}",
    ]
    if author:
        args.insert(1, f"--author={author}")

    try:
        raw = _run_git(args, cwd=repo_root)
    except RuntimeError:
        return []

    commits: list[Commit] = []
    # Records are separated by '\x1f' (the prefix we forced via pretty format).
    records = raw.split("\x1f")
    for record in records:
        record = record.strip("\n")
        if not record:
            continue
        # First line = header (the six fields). Remaining lines = numstat rows.
        first_nl = record.find("\n")
        header = record if first_nl == -1 else record[:first_nl]
        rest = "" if first_nl == -1 else record[first_nl + 1 :]
        parts = header.split("\x1e")
        if len(parts) < 5:
            continue
        sha, author_name, email, ts, subject = parts[0], parts[1], parts[2], parts[3], parts[4]
        body = parts[5] if len(parts) > 5 else ""

        files: list[str] = []
        additions = 0
        deletions = 0
        for line in rest.splitlines():
            line = line.strip()
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            add_s, del_s, path = cols[0], cols[1], cols[2]
            files.append(path)
            try:
                additions += int(add_s)
            except ValueError:
                pass
            try:
                deletions += int(del_s)
            except ValueError:
                pass

        commits.append(
            Commit(
                sha=sha,
                author=author_name,
                email=email,
                timestamp=ts,
                subject=subject,
                body=body,
                files=files,
                additions=additions,
                deletions=deletions,
            )
        )

    return commits


# ── gh CLI collectors ──────────────────────────────────────────────────────


def _run_gh_json(args: Sequence[str]) -> Optional[list[dict]]:
    """Invoke ``gh`` with ``--json`` and return the parsed JSON list.

    Returns ``None`` on any failure so callers can fall through to the
    next data source.
    """

    try:
        proc = subprocess.run(
            ["gh", *args], check=False, capture_output=True, text=True
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return data
    return None


def collect_gh_pull_requests(
    user: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 200,
    now: Optional[datetime] = None,
) -> list[PullRequest]:
    """Use ``gh search prs --author <user>`` to list recent PRs."""

    since = compute_since(window_days, now=now).strftime("%Y-%m-%d")
    json_fields = "number,title,body,state,createdAt,closedAt,author,labels,repository,additions,deletions,changedFiles"
    rows = _run_gh_json(
        [
            "search",
            "prs",
            f"--author={user}",
            f"--created=>={since}",
            f"--limit={max(1, limit)}",
            f"--json={json_fields}",
        ]
    )
    if rows is None:
        return []
    prs: list[PullRequest] = []
    for row in rows:
        labels = [lbl.get("name", "") for lbl in (row.get("labels") or [])]
        repo = (row.get("repository") or {}).get("nameWithOwner", "")
        author = (row.get("author") or {}).get("login", user)
        prs.append(
            PullRequest(
                number=int(row.get("number", 0)),
                title=row.get("title", "") or "",
                body=row.get("body", "") or "",
                state=(row.get("state") or "").lower(),
                created_at=row.get("createdAt", "") or "",
                merged_at=row.get("closedAt"),
                author=author,
                repo=repo,
                labels=labels,
                additions=row.get("additions"),
                deletions=row.get("deletions"),
                changed_files=row.get("changedFiles"),
            )
        )
    return prs


def collect_gh_issues(
    user: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 200,
    now: Optional[datetime] = None,
) -> list[Issue]:
    since = compute_since(window_days, now=now).strftime("%Y-%m-%d")
    json_fields = "number,title,body,state,createdAt,closedAt,author,labels,repository"
    rows = _run_gh_json(
        [
            "search",
            "issues",
            f"--author={user}",
            f"--created=>={since}",
            f"--limit={max(1, limit)}",
            f"--json={json_fields}",
            "--include-prs=false",
        ]
    )
    if rows is None:
        return []
    issues: list[Issue] = []
    for row in rows:
        labels = [lbl.get("name", "") for lbl in (row.get("labels") or [])]
        repo = (row.get("repository") or {}).get("nameWithOwner", "")
        author = (row.get("author") or {}).get("login", user)
        issues.append(
            Issue(
                number=int(row.get("number", 0)),
                title=row.get("title", "") or "",
                body=row.get("body", "") or "",
                state=(row.get("state") or "").lower(),
                created_at=row.get("createdAt", "") or "",
                closed_at=row.get("closedAt"),
                author=author,
                repo=repo,
                labels=labels,
            )
        )
    return issues


# ── REST API fallback ──────────────────────────────────────────────────────


def _api_get(url: str, token: str, *, timeout: float = 15.0) -> Optional[dict]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hermes-user-profile-builder",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError):
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def collect_api_pull_requests(
    user: str,
    token: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 100,
    now: Optional[datetime] = None,
) -> list[PullRequest]:
    """REST search fallback when ``gh`` is unavailable."""

    since = compute_since(window_days, now=now).strftime("%Y-%m-%d")
    query = f"type:pr+author:{user}+created:>={since}"
    url = f"https://api.github.com/search/issues?q={query}&per_page={min(100, max(1, limit))}"
    payload = _api_get(url, token)
    if not payload or not isinstance(payload, dict):
        return []
    out: list[PullRequest] = []
    for item in payload.get("items", []):
        repo_url = item.get("repository_url", "")
        repo = repo_url.split("repos/", 1)[-1] if repo_url else ""
        out.append(
            PullRequest(
                number=int(item.get("number", 0)),
                title=item.get("title", "") or "",
                body=item.get("body", "") or "",
                state=(item.get("state") or "").lower(),
                created_at=item.get("created_at", "") or "",
                merged_at=item.get("closed_at"),
                author=(item.get("user") or {}).get("login", user),
                repo=repo,
                labels=[lbl.get("name", "") for lbl in (item.get("labels") or [])],
            )
        )
    return out


def collect_api_issues(
    user: str,
    token: str,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = 100,
    now: Optional[datetime] = None,
) -> list[Issue]:
    since = compute_since(window_days, now=now).strftime("%Y-%m-%d")
    query = f"type:issue+author:{user}+created:>={since}"
    url = f"https://api.github.com/search/issues?q={query}&per_page={min(100, max(1, limit))}"
    payload = _api_get(url, token)
    if not payload or not isinstance(payload, dict):
        return []
    out: list[Issue] = []
    for item in payload.get("items", []):
        repo_url = item.get("repository_url", "")
        repo = repo_url.split("repos/", 1)[-1] if repo_url else ""
        out.append(
            Issue(
                number=int(item.get("number", 0)),
                title=item.get("title", "") or "",
                body=item.get("body", "") or "",
                state=(item.get("state") or "").lower(),
                created_at=item.get("created_at", "") or "",
                closed_at=item.get("closed_at"),
                author=(item.get("user") or {}).get("login", user),
                repo=repo,
                labels=[lbl.get("name", "") for lbl in (item.get("labels") or [])],
            )
        )
    return out


# ── top-level orchestrator ─────────────────────────────────────────────────


def collect_history(
    repo_root: Path,
    *,
    user: Optional[str] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    allow_gh: bool = True,
    allow_api: bool = True,
    now: Optional[datetime] = None,
    max_commits: int = 2000,
) -> HistorySnapshot:
    """Gather all signal we can within the requested window.

    No data source raises — each falls back silently with a note appended
    to :attr:`HistorySnapshot.notes` so the caller can surface why a
    particular source was skipped.
    """

    snapshot = HistorySnapshot(
        user=user,
        since=iso_since(window_days, now=now),
        window_days=window_days,
    )

    if have_git():
        commits = collect_local_commits(
            repo_root,
            window_days=window_days,
            author=user,
            now=now,
            max_commits=max_commits,
        )
        snapshot.commits = commits
        snapshot.sources_used.append("local-git")
        if not commits:
            snapshot.notes.append("local git returned no commits in window")
    else:
        snapshot.notes.append("git not on PATH; skipped local commits")

    if user and allow_gh and have_gh_auth():
        prs = collect_gh_pull_requests(user, window_days=window_days, now=now)
        issues = collect_gh_issues(user, window_days=window_days, now=now)
        snapshot.pull_requests = prs
        snapshot.issues = issues
        snapshot.sources_used.append("gh-cli")
    elif user and allow_api:
        token = get_github_token()
        if token:
            snapshot.pull_requests = collect_api_pull_requests(
                user, token, window_days=window_days, now=now
            )
            snapshot.issues = collect_api_issues(
                user, token, window_days=window_days, now=now
            )
            snapshot.sources_used.append("github-api")
        else:
            snapshot.notes.append(
                "no gh auth and no GITHUB_TOKEN; PRs/issues unavailable"
            )
    elif not user:
        snapshot.notes.append("no --user provided; PRs/issues unavailable")

    return snapshot


# ── summarisers ────────────────────────────────────────────────────────────


_LANG_BY_EXT = {
    ".py": "Python",
    ".pyi": "Python",
    ".rs": "Rust",
    ".go": "Go",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".lua": "Lua",
    ".sql": "SQL",
    ".md": "Markdown",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".json": "JSON",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".dart": "Dart",
}


_BUG_CATEGORY_PATTERNS = {
    "off-by-one": re.compile(r"\boff[- ]by[- ]one\b", re.IGNORECASE),
    "race-condition": re.compile(r"\brace\s+condition|\bdata\s+race\b", re.IGNORECASE),
    "null-handling": re.compile(r"\bnone\s*type|\bnullpointer|\bnpe\b|\bnone-?check\b", re.IGNORECASE),
    "encoding": re.compile(r"\bencoding|\butf-?8\b|\bunicode\b", re.IGNORECASE),
    "timezone": re.compile(r"\btimezone|\btz[\s_-]?aware\b|\butc\b", re.IGNORECASE),
    "import-order": re.compile(r"\bimport\s+order|\bcircular\s+import\b", re.IGNORECASE),
    "config-loading": re.compile(r"\b\.env\b|\bconfig(uration)?\b.*\bload", re.IGNORECASE),
    "test-flake": re.compile(r"\bflaky\b|\bflakey\b|\bintermittent\b", re.IGNORECASE),
    "permission": re.compile(r"\bpermission|\bchmod|\bpermissions?\s+denied\b", re.IGNORECASE),
    "secret-leak": re.compile(r"\bleaked\s+(token|secret|key)|\bredact\b", re.IGNORECASE),
}


_TESTING_HINTS = re.compile(r"\btest|\bpytest|\bunittest|\bjest|\bvitest|\bmocha\b", re.IGNORECASE)
_DOCS_HINTS = re.compile(r"\bdoc|\breadme|\bchangelog|\bcomment\b", re.IGNORECASE)
_FIX_HINTS = re.compile(r"\bfix|\bbug|\bregression|\brevert\b|\bhotfix\b", re.IGNORECASE)
_FEATURE_HINTS = re.compile(r"\badd|\bintroduce|\bsupport for|\bnew\s+feature\b", re.IGNORECASE)
_REFACTOR_HINTS = re.compile(r"\brefactor|\bcleanup|\brename|\brestructure\b", re.IGNORECASE)
_MOBILE_HINTS = re.compile(r"\btermux|\bandroid|\bphone\b|\bmobile\b", re.IGNORECASE)
_AI_HINTS = re.compile(r"\bclaude|\bgpt|\bllm|\bagent|\bhermes\b|\bcodex\b", re.IGNORECASE)


def _ext_of(path: str) -> str:
    dot = path.rfind(".")
    slash = max(path.rfind("/"), path.rfind("\\"))
    if dot <= slash:
        return ""
    return path[dot:].lower()


def summarize_commits(commits: Sequence[Commit]) -> dict:
    """Roll commits up into language, intent and habit counts."""

    total = len(commits)
    languages: dict[str, int] = {}
    test_touch = 0
    docs_touch = 0
    fix_intent = 0
    feature_intent = 0
    refactor_intent = 0
    mobile_intent = 0
    ai_intent = 0
    subject_lengths: list[int] = []
    bodies_with_explanation = 0
    multi_line_messages = 0
    additions = 0
    deletions = 0
    bug_categories: dict[str, int] = {}
    top_files: dict[str, int] = {}

    for commit in commits:
        subject_lengths.append(len(commit.first_line))
        if commit.body.strip():
            bodies_with_explanation += 1
        if "\n" in commit.subject or commit.body.strip():
            multi_line_messages += 1
        additions += commit.additions
        deletions += commit.deletions
        text = f"{commit.subject}\n{commit.body}"
        if _FIX_HINTS.search(text):
            fix_intent += 1
        if _FEATURE_HINTS.search(text):
            feature_intent += 1
        if _REFACTOR_HINTS.search(text):
            refactor_intent += 1
        if _MOBILE_HINTS.search(text):
            mobile_intent += 1
        if _AI_HINTS.search(text):
            ai_intent += 1
        for label, pattern in _BUG_CATEGORY_PATTERNS.items():
            if pattern.search(text):
                bug_categories[label] = bug_categories.get(label, 0) + 1
        for path in commit.files:
            top_files[path] = top_files.get(path, 0) + 1
            if _TESTING_HINTS.search(path):
                test_touch += 1
            if _DOCS_HINTS.search(path) or path.lower().endswith(".md"):
                docs_touch += 1
            ext = _ext_of(path)
            lang = _LANG_BY_EXT.get(ext)
            if lang:
                languages[lang] = languages.get(lang, 0) + 1

    avg_subject = (sum(subject_lengths) / len(subject_lengths)) if subject_lengths else 0.0
    top_languages = sorted(languages.items(), key=lambda kv: kv[1], reverse=True)
    hot_files = sorted(top_files.items(), key=lambda kv: kv[1], reverse=True)[:15]

    return {
        "total_commits": total,
        "additions": additions,
        "deletions": deletions,
        "languages": top_languages,
        "test_touches": test_touch,
        "docs_touches": docs_touch,
        "fix_intent": fix_intent,
        "feature_intent": feature_intent,
        "refactor_intent": refactor_intent,
        "mobile_intent": mobile_intent,
        "ai_intent": ai_intent,
        "avg_subject_length": round(avg_subject, 1),
        "bodies_with_explanation": bodies_with_explanation,
        "multi_line_messages": multi_line_messages,
        "bug_categories": bug_categories,
        "hot_files": hot_files,
    }


def summarize_pull_requests(prs: Sequence[PullRequest]) -> dict:
    if not prs:
        return {
            "total": 0,
            "merged": 0,
            "open": 0,
            "avg_title_length": 0.0,
            "body_usage_pct": 0.0,
            "top_repos": [],
            "common_labels": [],
        }
    merged = sum(1 for p in prs if (p.merged_at or "") and p.state in ("closed", "merged"))
    open_ = sum(1 for p in prs if p.state == "open")
    title_lens = [len(p.title) for p in prs if p.title]
    body_usage = sum(1 for p in prs if p.body and len(p.body.strip()) > 20)
    repos: dict[str, int] = {}
    labels: dict[str, int] = {}
    for p in prs:
        if p.repo:
            repos[p.repo] = repos.get(p.repo, 0) + 1
        for lbl in p.labels:
            labels[lbl] = labels.get(lbl, 0) + 1
    return {
        "total": len(prs),
        "merged": merged,
        "open": open_,
        "avg_title_length": round(sum(title_lens) / len(title_lens), 1) if title_lens else 0.0,
        "body_usage_pct": round(100.0 * body_usage / len(prs), 1),
        "top_repos": sorted(repos.items(), key=lambda kv: kv[1], reverse=True)[:10],
        "common_labels": sorted(labels.items(), key=lambda kv: kv[1], reverse=True)[:10],
    }


def summarize_issues(issues: Sequence[Issue]) -> dict:
    if not issues:
        return {"total": 0, "closed": 0, "top_repos": [], "common_labels": []}
    closed = sum(1 for i in issues if (i.closed_at or "") or i.state == "closed")
    repos: dict[str, int] = {}
    labels: dict[str, int] = {}
    for i in issues:
        if i.repo:
            repos[i.repo] = repos.get(i.repo, 0) + 1
        for lbl in i.labels:
            labels[lbl] = labels.get(lbl, 0) + 1
    return {
        "total": len(issues),
        "closed": closed,
        "top_repos": sorted(repos.items(), key=lambda kv: kv[1], reverse=True)[:10],
        "common_labels": sorted(labels.items(), key=lambda kv: kv[1], reverse=True)[:10],
    }
