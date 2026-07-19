"""GitHub publisher runtime.

Executable local logic backing the ``github-pr-workflow`` skill: branch
creation, file staging, commit, and PR preparation. Everything that touches
the network or rewrites history is gated behind an explicit ``approve``
flag so the default path is a previewable plan.

Safety surface
--------------
Three concerns are handled at this layer (in addition to whatever the
caller does):

1. **Secret blocking.** ``.env`` and a small set of obviously-secret
   filenames are rejected outright. File *contents* are also scanned for
   tokens (GitHub PATs, AWS keys, OpenAI/Anthropic/Google/Slack keys,
   PEM blocks). The check is conservative — false negatives are
   possible, but the typical "oops, committed my .env" case is caught.
2. **No destructive git.** This module never runs ``--force``,
   ``reset --hard``, ``clean -f``, merges, or branch deletes. It only
   creates a new branch, stages whitelisted files, commits, and (with
   explicit approval) pushes the new branch.
3. **Branch-per-job.** Every publish creates a fresh
   ``hermes/job-<job_id>-<slug>`` branch — we never reuse one. Rollback
   is "checkout the previous branch and delete this one" (instructions
   are emitted into ``publish-plan.md``).

The default invocation produces a *plan* (files in ``github/``) but does
not push or open a PR. Pass ``approve=True`` to the runner to execute
the push step. PR creation always uses the ``gh`` CLI when available;
when it isn't, the runner emits the equivalent ``git push`` + a copy of
the ``gh pr create`` command for the operator to run manually.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from utils import is_truthy_value

from hermes_cli.decision_engine import (
    live_publish_input,
    merge_decision_inputs,
    secret_input,
)

__all__ = [
    "PublisherError",
    "SecretBlocked",
    "RepoInfo",
    "GitStatus",
    "PublishPlan",
    "PublishResult",
    "get_repo_info",
    "get_current_branch",
    "get_status",
    "create_branch",
    "stage_files",
    "commit",
    "prepare_pr_body",
    "gh_available",
    "build_gh_pr_create_command",
    "slugify",
    "branch_name_for_job",
    "scan_for_secrets",
    "write_publish_artifacts",
    "run",
]


# ── exceptions ───────────────────────────────────────────────────────────────


class PublisherError(RuntimeError):
    """Raised for any publisher failure that isn't a secret block."""


class SecretBlocked(PublisherError):
    """Raised when staging is refused because a file looks like a secret."""

    def __init__(
        self,
        path: str,
        reason: str,
        *,
        findings: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(f"refused to stage {path}: {reason}")
        self.path = path
        self.reason = reason
        self.findings: dict[str, str] = dict(findings) if findings else {path: reason}


# ── dataclasses ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoInfo:
    root: Path
    owner: Optional[str]
    repo: Optional[str]
    remote_url: Optional[str]
    default_branch: str = "main"

    @property
    def slug(self) -> Optional[str]:
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}"
        return None


@dataclass(frozen=True)
class GitStatus:
    branch: Optional[str]
    clean: bool
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)


@dataclass
class PublishPlan:
    job_id: str
    branch: str
    base_branch: str
    files: list[str]
    commit_message: str
    pr_title: str
    pr_body: str
    push_command: list[str]
    pr_create_command: Optional[list[str]]
    gh_present: bool
    dry_run: bool
    output_dir: Path
    repo: RepoInfo
    created_at: str
    decision_verdict: Optional[Mapping[str, Any]] = None

    def as_status(self, *, executed: bool, pushed: bool, errors: Sequence[str]) -> dict:
        return {
            "job_id": self.job_id,
            "branch": self.branch,
            "base_branch": self.base_branch,
            "pr_title": self.pr_title,
            "files": list(self.files),
            "gh_present": self.gh_present,
            "dry_run": self.dry_run,
            "executed": executed,
            "pushed": pushed,
            "errors": list(errors),
            "decision_verdict": self.decision_verdict,
            "created_at": self.created_at,
            "repo": {
                "owner": self.repo.owner,
                "repo": self.repo.repo,
                "remote_url": self.repo.remote_url,
            },
        }


@dataclass
class PublishResult:
    plan: PublishPlan
    executed: bool
    pushed: bool
    errors: list[str]
    artifacts: dict[str, Path]


# ── git plumbing ─────────────────────────────────────────────────────────────


def _run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        text=True,
        capture_output=capture,
    )


def _parse_remote(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (owner, repo) from a GitHub remote URL.

    Handles both ``git@github.com:owner/repo(.git)`` and
    ``https://github.com/owner/repo(.git)`` forms.
    """
    url = (url or "").strip()
    if not url:
        return None, None
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def get_repo_info(repo_root: Optional[Path] = None) -> RepoInfo:
    """Inspect the local git repo and return owner/repo + remote URL.

    Raises ``PublisherError`` when the directory is not a git checkout.
    Returns ``RepoInfo`` with ``owner``/``repo``/``remote_url`` set to
    ``None`` when the remote isn't a GitHub URL — the caller can still
    create branches/commits locally in that state.
    """
    root = (repo_root or Path.cwd()).resolve()
    try:
        toplevel = _run_git(
            ["rev-parse", "--show-toplevel"], cwd=root, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise PublisherError(f"not a git repository: {root}") from exc
    except FileNotFoundError as exc:
        raise PublisherError("git executable not found on PATH") from exc

    root = Path(toplevel)
    remote_url: Optional[str] = None
    try:
        remote_url = _run_git(
            ["remote", "get-url", "origin"], cwd=root, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        remote_url = None
    owner, repo = _parse_remote(remote_url or "")

    default_branch = "main"
    try:
        # symbolic-ref tells us what HEAD on origin points at
        out = _run_git(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=root,
            check=True,
        ).stdout.strip()
        if "/" in out:
            default_branch = out.split("/", 1)[1]
    except subprocess.CalledProcessError:
        pass

    return RepoInfo(
        root=root,
        owner=owner,
        repo=repo,
        remote_url=remote_url,
        default_branch=default_branch,
    )


def get_current_branch(repo_root: Optional[Path] = None) -> Optional[str]:
    root = (repo_root or Path.cwd()).resolve()
    try:
        out = _run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=root, check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    if not out or out == "HEAD":
        return None
    return out


def get_status(repo_root: Optional[Path] = None) -> GitStatus:
    """Return a structured view of ``git status --porcelain=v1``."""
    root = (repo_root or Path.cwd()).resolve()
    try:
        out = _run_git(
            ["status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise PublisherError("git status failed") from exc

    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:].strip()
        # rename: "R  old -> new"
        if "->" in path:
            path = path.split("->", 1)[1].strip()
        if code == "??":
            untracked.append(path)
            continue
        if code[0] not in (" ", "?"):
            staged.append(path)
        if code[1] not in (" ", "?"):
            unstaged.append(path)

    branch = get_current_branch(root)
    clean = not (staged or unstaged or untracked)
    return GitStatus(
        branch=branch,
        clean=clean,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
    )


# ── secret blocking ──────────────────────────────────────────────────────────


# Filenames or path fragments we always refuse. Lowercased; matched as a
# basename equality OR substring against the relative path.
_BLOCKED_BASENAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".envrc.local",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials",
    "credentials.json",
    "service-account.json",
    "secrets.yaml",
    "secrets.yml",
    "secrets.json",
    ".npmrc.local",
    ".pypirc",
    ".netrc",
})

_BLOCKED_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    ".jks",
)

# Path fragments that always look suspicious enough to block by default.
_BLOCKED_FRAGMENTS = (
    ".env.",  # matches .env.<anything>
    "secrets/",
    "private_keys/",
)

# Content scanners. Conservative — we only flag patterns that very rarely
# appear in non-secret code.
_CONTENT_SECRET_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("GitHub PAT", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("GitHub fine-grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("GitHub OAuth token", re.compile(r"gh[ousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack bot token", re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{30,}")),
    ("OpenAI API key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("Anthropic API key", re.compile(r"sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{20,}")),
    (
        "Private key PEM",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |)PRIVATE KEY-----"),
    ),
)

# Don't scan content of files larger than this (bytes) — they're almost
# certainly not source. Filename blocks still apply.
_MAX_SCAN_BYTES = 2 * 1024 * 1024


def _normalized_rel(path: str, repo_root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.relative_to(repo_root)
        except ValueError:
            return str(p).replace("\\", "/")
    return str(p).replace("\\", "/")


def _path_blocked(rel: str) -> Optional[str]:
    low = rel.lower()
    base = Path(low).name
    if base in _BLOCKED_BASENAMES:
        return f"blocked filename: {base}"
    for frag in _BLOCKED_FRAGMENTS:
        if frag in low:
            return f"blocked path fragment: {frag}"
    for suf in _BLOCKED_SUFFIXES:
        if low.endswith(suf):
            return f"blocked extension: {suf}"
    return None


def scan_for_secrets(
    files: Iterable[str],
    *,
    repo_root: Path,
    scan_contents: bool = True,
) -> dict[str, str]:
    """Return ``{rel_path: reason}`` for every file that should be blocked.

    An empty dict means staging is safe.
    """
    findings: dict[str, str] = {}
    for raw in files:
        rel = _normalized_rel(raw, repo_root)
        reason = _path_blocked(rel)
        if reason:
            findings[rel] = reason
            continue
        if not scan_contents:
            continue
        abs_path = repo_root / rel
        try:
            if not abs_path.is_file():
                continue
            if abs_path.stat().st_size > _MAX_SCAN_BYTES:
                continue
            with abs_path.open("rb") as fh:
                blob = fh.read()
        except OSError:
            continue
        try:
            text = blob.decode("utf-8", errors="replace")
        except Exception:
            continue
        for label, pattern in _CONTENT_SECRET_PATTERNS:
            if pattern.search(text):
                findings[rel] = f"content matched secret pattern: {label}"
                break
    return findings


# ── branch naming ────────────────────────────────────────────────────────────


_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_len: int = 40) -> str:
    s = _SLUG_BAD.sub("-", (value or "").lower()).strip("-")
    if not s:
        return "job"
    if len(s) > max_len:
        s = s[:max_len].rstrip("-") or s[:max_len]
    return s


def branch_name_for_job(job_id: str, *, prefix: str = "hermes/job-") -> str:
    """Compute a deterministic branch name for ``job_id``.

    Branches are namespaced under ``hermes/job-`` so they're trivially
    recognisable as agent-created and easy to filter or clean up later.
    """
    slug = slugify(str(job_id))
    return f"{prefix}{slug}"


def create_branch(
    job_id: str,
    *,
    repo_root: Optional[Path] = None,
    base_branch: Optional[str] = None,
    dry_run: bool = True,
) -> str:
    """Create (or compute) the branch name for ``job_id``.

    With ``dry_run=True`` (default) no git command runs — the name is
    just returned so the planner can preview it. With ``dry_run=False``
    the branch is created with ``git checkout -b``; the call fails if
    the branch already exists, which is intentional (branch-per-job).
    """
    root = (repo_root or Path.cwd()).resolve()
    name = branch_name_for_job(job_id)
    if dry_run:
        return name
    args = ["checkout", "-b", name]
    if base_branch:
        args.append(base_branch)
    try:
        _run_git(args, cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        raise PublisherError(
            f"failed to create branch {name}: {exc.stderr.strip() if exc.stderr else exc}"
        ) from exc
    return name


# ── staging / commit ─────────────────────────────────────────────────────────


def stage_files(
    file_list: Sequence[str],
    *,
    repo_root: Optional[Path] = None,
    scan_contents: bool = True,
    dry_run: bool = True,
) -> list[str]:
    """Stage the given files after secret-scanning them.

    Returns the list of cleaned, repo-relative paths that *would* be
    staged. With ``dry_run=False`` they are passed to ``git add`` as
    well. Raises ``SecretBlocked`` for the first file that fails the
    secret scan — the whole batch is refused (atomic).
    """
    root = (repo_root or Path.cwd()).resolve()
    cleaned: list[str] = []
    for raw in file_list:
        rel = _normalized_rel(raw, root)
        if not rel or rel == ".":
            continue
        cleaned.append(rel)

    findings = scan_for_secrets(cleaned, repo_root=root, scan_contents=scan_contents)
    if findings:
        # Block on the first finding (deterministic), but expose all.
        first_path, first_reason = next(iter(findings.items()))
        raise SecretBlocked(first_path, first_reason, findings=findings)

    if dry_run or not cleaned:
        return cleaned

    try:
        _run_git(["add", "--", *cleaned], cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        raise PublisherError(
            f"git add failed: {exc.stderr.strip() if exc.stderr else exc}"
        ) from exc
    return cleaned


def commit(
    message: str,
    *,
    repo_root: Optional[Path] = None,
    allow_empty: bool = False,
    dry_run: bool = True,
) -> Optional[str]:
    """Create a commit with ``message``.

    Returns the resulting commit SHA, or ``None`` in ``dry_run`` mode.
    Never amends, never bypasses hooks, never force-anything.
    """
    msg = (message or "").strip()
    if not msg:
        raise PublisherError("commit message is empty")
    root = (repo_root or Path.cwd()).resolve()
    if dry_run:
        return None
    args = ["commit", "-m", msg]
    if allow_empty:
        args.append("--allow-empty")
    try:
        _run_git(args, cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        raise PublisherError(
            f"git commit failed: {exc.stderr.strip() if exc.stderr else exc}"
        ) from exc
    sha = _run_git(["rev-parse", "HEAD"], cwd=root, check=True).stdout.strip()
    return sha or None


# ── gh CLI ───────────────────────────────────────────────────────────────────


def gh_available() -> bool:
    """Return True iff the ``gh`` CLI is on PATH."""
    return shutil.which("gh") is not None


def build_gh_pr_create_command(
    *,
    title: str,
    body: str,
    base: str,
    head: str,
    draft: bool = True,
) -> list[str]:
    """Build the argv for ``gh pr create``.

    Body is passed via ``--body`` directly; the caller is responsible
    for writing it to a file if it's large enough to overflow argv on
    the platform.
    """
    cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        base,
        "--head",
        head,
    ]
    if draft:
        cmd.append("--draft")
    return cmd


# ── PR body / plan rendering ─────────────────────────────────────────────────


def prepare_pr_body(
    job_id: str,
    *,
    summary: str = "",
    changes: Optional[Sequence[str]] = None,
    test_plan: Optional[Sequence[str]] = None,
    notes: str = "",
    verdict_id: Optional[str] = None,
    decision_tier: Optional[str] = None,
) -> str:
    """Render the PR body markdown for ``job_id``.

    The structure matches what reviewers in this repo expect: a short
    summary block, a bulleted changes list, a test-plan checklist, and
    an optional notes section. Empty sections are omitted so the body
    stays scannable.

    When ``verdict_id`` is provided (the unified decision verdict from the
    publish boundary), a ``## Decision`` block records it — closing the
    Sprint 5 "PR body lacks a verdict id" gap. Defaults preserve the prior
    output exactly for callers that don't pass it.
    """
    lines: list[str] = []
    lines.append(f"## Summary")
    if summary.strip():
        lines.append(summary.strip())
    else:
        lines.append(f"Automated change from muse job `{job_id}`.")
    lines.append("")

    change_items = [c.strip() for c in (changes or []) if c and c.strip()]
    if change_items:
        lines.append("## Changes")
        for item in change_items:
            lines.append(f"- {item}")
        lines.append("")

    tp_items = [t.strip() for t in (test_plan or []) if t and t.strip()]
    lines.append("## Test plan")
    if tp_items:
        for item in tp_items:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- [ ] Reviewer confirms automated changes.")
    lines.append("")

    if notes.strip():
        lines.append("## Notes")
        lines.append(notes.strip())
        lines.append("")

    if verdict_id:
        lines.append("## Decision")
        tier_note = f" (tier: {decision_tier})" if decision_tier else ""
        lines.append(f"- Verdict: `{verdict_id}`{tier_note}")
        lines.append("")

    lines.append("## Provenance")
    lines.append(f"- muse job id: `{job_id}`")
    lines.append(
        "- Generated by `hermes_cli.github_publisher` "
        "(see `docs/orchestration/github-publisher-runtime.md`)."
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_publish_plan(plan: PublishPlan, *, gh_present: bool) -> str:
    lines: list[str] = []
    lines.append(f"# Publish plan — job `{plan.job_id}`")
    lines.append("")
    lines.append(f"- **Repo:** {plan.repo.slug or '(no GitHub remote detected)'}")
    lines.append(f"- **Branch:** `{plan.branch}`")
    lines.append(f"- **Base:** `{plan.base_branch}`")
    lines.append(f"- **Files:** {len(plan.files)}")
    lines.append(f"- **gh CLI present:** {'yes' if gh_present else 'no'}")
    lines.append(f"- **Dry-run:** {'yes' if plan.dry_run else 'no'}")
    lines.append(f"- **Created at:** {plan.created_at}")
    lines.append("")
    lines.append("## Files to stage")
    if plan.files:
        for f in plan.files:
            lines.append(f"- `{f}`")
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Commands (preview)")
    lines.append("```bash")
    lines.append(f"git checkout -b {plan.branch}")
    if plan.files:
        lines.append("git add -- " + " ".join(plan.files))
    lines.append("git commit -F github/commit-message.txt")
    lines.append(" ".join(plan.push_command))
    if plan.pr_create_command:
        lines.append(" ".join(_shell_quote(p) for p in plan.pr_create_command))
    else:
        lines.append(
            "# gh not present — open the PR manually using github/pr-title.txt"
        )
        lines.append(
            "# and github/pr-body.md against base `{base}`.".format(
                base=plan.base_branch
            )
        )
    lines.append("```")
    lines.append("")
    lines.append("## Rollback")
    lines.append(
        "- If something looks wrong after the push, run: "
        f"`git push origin --delete {plan.branch}` to remove the remote branch "
        "(only the freshly created one — never main)."
    )
    lines.append(
        "- Locally: `git checkout -` to return to the prior branch, then "
        f"`git branch -D {plan.branch}` once you've confirmed nothing else "
        "depends on the local copy."
    )
    lines.append(
        "- This module never force-pushes, never merges, and never deletes the base branch."
    )
    lines.append("")
    return "\n".join(lines)


def _shell_quote(s: str) -> str:
    if not s:
        return "''"
    if re.fullmatch(r"[A-Za-z0-9_./:=@\-]+", s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


# ── artifact emission ────────────────────────────────────────────────────────


def write_publish_artifacts(
    plan: PublishPlan,
    *,
    output_dir: Optional[Path] = None,
    executed: bool = False,
    pushed: bool = False,
    errors: Sequence[str] = (),
) -> dict[str, Path]:
    """Write the six standard artifact files and return their paths."""
    out = output_dir or plan.output_dir
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    branch_path = out / "branch.txt"
    branch_path.write_text(plan.branch + "\n", encoding="utf-8")
    paths["branch"] = branch_path

    commit_msg_path = out / "commit-message.txt"
    commit_msg_path.write_text(plan.commit_message.rstrip() + "\n", encoding="utf-8")
    paths["commit_message"] = commit_msg_path

    title_path = out / "pr-title.txt"
    title_path.write_text(plan.pr_title.rstrip() + "\n", encoding="utf-8")
    paths["pr_title"] = title_path

    body_path = out / "pr-body.md"
    body_path.write_text(plan.pr_body, encoding="utf-8")
    paths["pr_body"] = body_path

    plan_path = out / "publish-plan.md"
    plan_path.write_text(
        _render_publish_plan(plan, gh_present=plan.gh_present), encoding="utf-8"
    )
    paths["publish_plan"] = plan_path

    status_path = out / "publish-status.json"
    status_path.write_text(
        json.dumps(
            plan.as_status(executed=executed, pushed=pushed, errors=errors),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["publish_status"] = status_path

    return paths


# ── top-level orchestration ──────────────────────────────────────────────────


def _load_allowed_repos() -> list[str]:
    """Repos a *live* publish (approve=True) may target, as ``owner/name``.

    Sourced from the ``github.allowed_repositories`` config block (shared with
    the github_assistant plugin) plus the ``HERMES_PUBLISH_ALLOWED_REPOS`` env
    var (comma/space separated). An **empty** list means no allowlist is
    enforced — dry-run is always safe regardless. Any failure degrades to empty.
    """
    repos: list[str] = []
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        block = cfg.get("github") if isinstance(cfg, dict) else None
        if isinstance(block, dict):
            for item in block.get("allowed_repositories") or []:
                if isinstance(item, str) and item.strip():
                    repos.append(item.strip())
    except Exception:
        pass
    for item in (
        os.environ.get("HERMES_PUBLISH_ALLOWED_REPOS", "").replace(",", " ").split()
    ):
        if item.strip():
            repos.append(item.strip())
    return repos


def run(
    *,
    job_id: str,
    files: Sequence[str],
    commit_message: str,
    pr_title: Optional[str] = None,
    pr_summary: str = "",
    pr_changes: Optional[Sequence[str]] = None,
    pr_test_plan: Optional[Sequence[str]] = None,
    pr_notes: str = "",
    repo_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    base_branch: Optional[str] = None,
    approve: bool = False,
    scan_contents: bool = True,
) -> PublishResult:
    """End-to-end: build a plan, write artifacts, optionally execute.

    ``approve=False`` (the default) produces only the artifacts under
    ``output_dir`` (default ``<repo_root>/github``). ``approve=True``
    additionally creates the branch, stages the files, makes the
    commit, and pushes to ``origin``. ``gh pr create`` is *never* run
    from inside this function — even with ``approve=True`` the PR is
    opened by the operator running the printed command, so the human is
    always in the loop on PR publication.
    """
    repo = get_repo_info(repo_root)
    base = base_branch or repo.default_branch or "main"
    out = (output_dir or (repo.root / "github")).resolve()

    cleaned = [_normalized_rel(f, repo.root) for f in files if f]
    cleaned = [c for c in cleaned if c and c != "."]
    findings = scan_for_secrets(
        cleaned, repo_root=repo.root, scan_contents=scan_contents
    )

    errors: list[str] = []
    if findings:
        for path, reason in findings.items():
            errors.append(f"blocked: {path} — {reason}")

    # Unified decision verdict for the publish boundary (Sprint 2 wiring):
    # secrets -> refuse; a live publish (approve=True) must target an
    # allowlisted repo and is owner-gated -> ask (allowlisted) / refuse (not);
    # a dry-run with no findings -> auto.
    allowed_repos = _load_allowed_repos()
    repo_allowlisted = (not allowed_repos) or (repo.slug in allowed_repos)
    _decision_inputs = [secret_input(list(findings))]
    if approve:
        _decision_inputs.append(
            live_publish_input(
                repo_allowlisted=repo_allowlisted, action_allowlisted=True
            )
        )
    verdict = merge_decision_inputs("github.publish_pr", _decision_inputs)

    if approve and not repo_allowlisted:
        errors.append(
            f"blocked: repo {repo.slug!r} is not in the publish allowlist "
            "(set github.allowed_repositories or HERMES_PUBLISH_ALLOWED_REPOS)"
        )

    branch = branch_name_for_job(job_id)
    title = (
        pr_title or commit_message.splitlines()[0]
        if commit_message
        else f"hermes: job {job_id}"
    ).strip()
    body = prepare_pr_body(
        job_id,
        summary=pr_summary,
        changes=pr_changes,
        test_plan=pr_test_plan,
        notes=pr_notes,
        verdict_id=verdict.id,
        decision_tier=verdict.tier.value,
    )

    gh_present = gh_available()
    push_cmd = ["git", "push", "-u", "origin", branch]
    pr_cmd: Optional[list[str]] = None
    if gh_present and repo.slug:
        pr_cmd = build_gh_pr_create_command(
            title=title, body=body, base=base, head=branch, draft=True
        )

    plan = PublishPlan(
        job_id=str(job_id),
        branch=branch,
        base_branch=base,
        files=cleaned,
        commit_message=commit_message,
        pr_title=title,
        pr_body=body,
        push_command=push_cmd,
        pr_create_command=pr_cmd,
        gh_present=gh_present,
        dry_run=not approve,
        output_dir=out,
        repo=repo,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        decision_verdict=verdict.to_redacted_dict(),
    )

    executed = False
    pushed = False

    # HERMES_PUBLISH_LIVE is the documented live-publish gate (see
    # docs/orchestration/release-checklist.md): no code path contacts the
    # network unless it is set. The local branch/stage/commit below run under
    # ``approve=True`` (they are offline); only the push — the single step that
    # reaches a remote — requires the env flag (and a token via git's own
    # credential layer). Default (env unset) stays local-only.
    publish_live = is_truthy_value(os.environ.get("HERMES_PUBLISH_LIVE"))

    if approve and not findings and repo_allowlisted:
        try:
            create_branch(job_id, repo_root=repo.root, base_branch=base, dry_run=False)
            stage_files(
                cleaned,
                repo_root=repo.root,
                scan_contents=scan_contents,
                dry_run=False,
            )
            commit(commit_message, repo_root=repo.root, dry_run=False)
            executed = True
            if publish_live:
                try:
                    _run_git(push_cmd[1:], cwd=repo.root, check=True)
                    pushed = True
                except subprocess.CalledProcessError as exc:
                    errors.append(
                        f"git push failed: {exc.stderr.strip() if exc.stderr else exc}"
                    )
            else:
                errors.append(
                    "live push skipped: HERMES_PUBLISH_LIVE=1 is required to push "
                    "to a remote (the commit is local-only without it)"
                )
        except SecretBlocked as exc:
            errors.append(str(exc))
        except PublisherError as exc:
            errors.append(str(exc))

    artifacts = write_publish_artifacts(
        plan,
        output_dir=out,
        executed=executed,
        pushed=pushed,
        errors=errors,
    )

    return PublishResult(
        plan=plan,
        executed=executed,
        pushed=pushed,
        errors=errors,
        artifacts=artifacts,
    )
