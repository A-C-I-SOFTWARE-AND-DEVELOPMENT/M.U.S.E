"""GitHub integration adapter.

Thin façade over :mod:`muse_cli.github_publisher`, exposing the
uniform ``detect`` / ``plan`` / ``explain`` / ``execute`` shape that
every integration in this package follows. The heavy lifting (branch
creation, secret scanning, PR body rendering, ``gh`` argv building) is
delegated to the publisher runtime — this module is the contract the
rest of Hermes (orchestrator, gateway, skills) calls into.

Safety posture
--------------
* No destructive git operations are ever proposed.
* ``execute()`` refuses to run unless ``approve=True`` is explicit.
* PRs are always opened as drafts; merges are never automated.
* Secret-scanning is enforced by the publisher and is *not* opt-out.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .. import github_publisher as _gp

__all__ = [
    "Detection",
    "GitHubPlan",
    "GitHubExecutionResult",
    "detect",
    "plan",
    "explain",
    "execute",
]


@dataclass(frozen=True)
class Detection:
    cli_present: bool
    cli_path: Optional[str]
    git_present: bool
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GitHubPlan:
    job_id: str
    branch: str
    base_branch: str
    files: list[str]
    commit_message: str
    pr_title: str
    pr_body: str
    push_command: list[str]
    pr_create_command: Optional[list[str]]
    repo_slug: Optional[str]
    cli_present: bool
    rollback_notes: list[str]
    validation_steps: list[str]
    approval_required: bool = True
    dry_run: bool = True


@dataclass(frozen=True)
class GitHubExecutionResult:
    executed: bool
    pushed: bool
    errors: list[str]
    artifact_dir: Optional[Path]


def detect() -> Detection:
    """Probe for the ``gh`` and ``git`` CLIs without contacting GitHub."""
    gh_path = shutil.which("gh")
    git_path = shutil.which("git")
    notes: list[str] = []
    if gh_path is None:
        notes.append(
            "`gh` CLI not on PATH — PR creation will print a manual command."
        )
    if git_path is None:
        notes.append("`git` not on PATH — branch/commit/push steps will fail.")
    return Detection(
        cli_present=gh_path is not None,
        cli_path=gh_path,
        git_present=git_path is not None,
        notes=notes,
    )


def plan(
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
    base_branch: Optional[str] = None,
) -> GitHubPlan:
    """Build a dry-run plan for publishing ``files`` as a PR.

    Never touches the network and never mutates the repository. The
    plan returned can be re-rendered by :func:`explain` or handed to
    :func:`execute` once the operator has approved.
    """
    repo = _gp.get_repo_info(repo_root)
    base = base_branch or repo.default_branch or "main"
    branch = _gp.branch_name_for_job(job_id)
    title = (
        (pr_title or (commit_message.splitlines()[0] if commit_message else f"hermes: job {job_id}"))
        .strip()
    )
    body = _gp.prepare_pr_body(
        job_id,
        summary=pr_summary,
        changes=pr_changes,
        test_plan=pr_test_plan,
        notes=pr_notes,
    )

    cli_present = _gp.gh_available()
    push_cmd = ["git", "push", "-u", "origin", branch]
    pr_cmd: Optional[list[str]] = None
    if cli_present and repo.slug:
        pr_cmd = _gp.build_gh_pr_create_command(
            title=title, body=body, base=base, head=branch, draft=True
        )

    rollback = [
        f"git push origin --delete {branch}  # only after a failed push, never on main",
        "git checkout -  # return to the prior local branch",
        f"git branch -D {branch}  # drop the local working branch once nothing depends on it",
    ]
    validation = [
        "Reviewer opens the draft PR and checks the diff matches expectations.",
        "CI on the PR passes (lint, type-check, tests).",
        "No secret-shaped strings appear in the diff (the publisher already scans, this is a double-check).",
    ]

    return GitHubPlan(
        job_id=str(job_id),
        branch=branch,
        base_branch=base,
        files=[f for f in files if f],
        commit_message=commit_message,
        pr_title=title,
        pr_body=body,
        push_command=push_cmd,
        pr_create_command=pr_cmd,
        repo_slug=repo.slug,
        cli_present=cli_present,
        rollback_notes=rollback,
        validation_steps=validation,
        approval_required=True,
        dry_run=True,
    )


def explain(p: GitHubPlan) -> str:
    """Render ``p`` as plain-English markdown for a human reviewer."""
    lines: list[str] = []
    lines.append(f"### GitHub publish plan for job `{p.job_id}`")
    lines.append("")
    lines.append(
        f"I want to push **{len(p.files)} file(s)** to "
        f"`{p.repo_slug or '(no GitHub remote)'}` on a fresh branch "
        f"named `{p.branch}` (base: `{p.base_branch}`) and open a draft PR."
    )
    lines.append("")
    lines.append(f"**Approval required:** {'yes' if p.approval_required else 'no'}")
    lines.append(f"**`gh` CLI present:** {'yes' if p.cli_present else 'no'}")
    lines.append("")
    lines.append("**Commands I would run (in order):**")
    lines.append("```bash")
    lines.append(f"git checkout -b {p.branch}")
    if p.files:
        lines.append("git add -- " + " ".join(p.files))
    lines.append("git commit -F github/commit-message.txt")
    lines.append(" ".join(p.push_command))
    if p.pr_create_command:
        lines.append(" ".join(p.pr_create_command))
    else:
        lines.append("# gh not present — open the PR manually using github/pr-title.txt + pr-body.md")
    lines.append("```")
    lines.append("")
    lines.append("**Rollback if something goes wrong:**")
    for note in p.rollback_notes:
        lines.append(f"- `{note}`")
    lines.append("")
    lines.append("**How you can validate it worked:**")
    for step in p.validation_steps:
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def execute(
    p: GitHubPlan,
    *,
    approve: bool = False,
    pr_summary: str = "",
    pr_changes: Optional[Sequence[str]] = None,
    pr_test_plan: Optional[Sequence[str]] = None,
    pr_notes: str = "",
    repo_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> GitHubExecutionResult:
    """Execute ``p`` against the local repo.

    Refuses to run unless ``approve=True`` is passed explicitly. Even
    with approval, the actual ``gh pr create`` step is *not* invoked —
    the operator is expected to run the printed command, keeping a
    human in the loop on PR publication.
    """
    if not approve:
        return GitHubExecutionResult(
            executed=False,
            pushed=False,
            errors=["approve=False — refused to execute"],
            artifact_dir=None,
        )

    result = _gp.run(
        job_id=p.job_id,
        files=p.files,
        commit_message=p.commit_message,
        pr_title=p.pr_title,
        pr_summary=pr_summary,
        pr_changes=pr_changes,
        pr_test_plan=pr_test_plan,
        pr_notes=pr_notes,
        repo_root=repo_root,
        output_dir=output_dir,
        base_branch=p.base_branch,
        approve=True,
    )
    return GitHubExecutionResult(
        executed=result.executed,
        pushed=result.pushed,
        errors=list(result.errors),
        artifact_dir=result.plan.output_dir,
    )
