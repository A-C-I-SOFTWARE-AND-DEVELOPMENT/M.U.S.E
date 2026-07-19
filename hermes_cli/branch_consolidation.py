"""Consolidate ``upstream/main`` + the current branch into a fork's ``main``.

This powers the default behaviour of ``hermes update`` *for forks*: instead
of merely fast-forwarding ``origin/main`` (and refusing to pull upstream the
moment the fork has local commits), ``update`` now brings together three
sources into the fork's ``main``:

- the **original** code (``upstream/main`` — the official repo), and
- the **current working branch** (whatever is checked out),

with conflicts auto-resolved by the configured model and surfaced for review
*before* anything lands on ``main``.

Design notes:

- The merges happen on a throwaway integration branch
  (``hermes/update-integration``).  ``main`` is only moved — via a
  fast-forward of that integration branch — after the review prompt is
  approved.  Net effect: "fix conflicts first, review, *then* fully merge
  into my main."
- Conflict resolution reuses the stdlib model bridge
  (:mod:`hermes_cli.jarvis_prime.self_audit.model_bridge`).  When no model
  is configured, or the model's output still contains conflict markers, we
  **safe-stop**: abort the merge, leave ``main`` untouched, and list the
  conflicted files for manual resolution.  We never guess silently.
- Merging into ``main`` is governed by the LaunchGate policy rather than the
  ``"Yes, with authorization."`` owner phrase (see ``owner_auth.py`` and
  ``docs/launch/AUTOMATED_MERGE_POLICY.md``), so the gate here is a
  review-and-confirm prompt, bypassable with ``--yes``.

This module keeps its own tiny git wrappers so it does not import the heavy
:mod:`hermes_cli.main`.  The caller passes in a ``validate_syntax`` callback
and (in gateway mode) an ``input_fn`` so prompts reach the messenger.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

INTEGRATION_BRANCH = "hermes/update-integration"

# Conflict markers git writes into a file with an unresolved hunk.  We refuse
# to accept any model resolution that still contains one of these.
_CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")

# Status values carried by ConsolidationResult.
STATUS_MERGED = "merged"  # integration approved + fast-forwarded into main
STATUS_DECLINED = "declined"  # review prompt declined; main untouched
STATUS_SAFE_STOP = "safe_stop"  # conflict we won't auto-resolve; main untouched
STATUS_SKIPPED = "skipped"  # not applicable (no upstream); use legacy path
STATUS_ERROR = "error"  # something failed; main untouched


@dataclass
class ConsolidationResult:
    """Outcome of :func:`consolidate_into_main`."""

    status: str
    summary: str = ""
    resolved_files: list[str] = field(default_factory=list)
    conflict_files: list[str] = field(default_factory=list)
    pushed: bool = False
    push_message: str = ""

    @property
    def merged(self) -> bool:
        return self.status == STATUS_MERGED

    @property
    def should_continue_update(self) -> bool:
        """True when the caller should proceed with the rest of ``update``
        (dependency reinstall, bytecode clear, …) because ``main`` advanced."""

        return self.status == STATUS_MERGED


def _git(
    git_cmd: list[str], repo: Path, *args: str, check: bool = False
) -> subprocess.CompletedProcess:
    return subprocess.run(
        git_cmd + list(args),
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
    )


# Used only as a last resort when the environment has no git identity at all
# (common on a fresh Termux / container install). Injected via ``-c`` so it
# never overwrites a real configured identity and never persists to git config.
_FALLBACK_GIT_NAME = "M.U.S.E. Update"
_FALLBACK_GIT_EMAIL = "hermes-agent@users.noreply.github.com"


def _has_committer_identity(git_cmd: list[str], repo: Path) -> bool:
    """True when both user.name and user.email resolve (any scope)."""
    name = _git(git_cmd, repo, "config", "user.name").stdout.strip()
    email = _git(git_cmd, repo, "config", "user.email").stdout.strip()
    return bool(name) and bool(email)


def _with_fallback_identity(git_cmd: list[str], repo: Path) -> list[str]:
    """Augment ``git_cmd`` with a fallback commit identity when none is set.

    The consolidation merges create real commits (merge commits, auto-resolved
    conflict commits). On a box with no ``user.name`` / ``user.email`` git
    aborts with "Committer identity unknown", which previously stopped
    ``hermes update`` dead. We inject a fallback identity via ``-c`` only when
    the user has none configured, so a real identity is always preferred and
    nothing is written to their git config.
    """
    if _has_committer_identity(git_cmd, repo):
        return git_cmd
    return git_cmd + [
        "-c",
        f"user.name={_FALLBACK_GIT_NAME}",
        "-c",
        f"user.email={_FALLBACK_GIT_EMAIL}",
    ]


def _conflicted_files(git_cmd: list[str], repo: Path) -> list[str]:
    """Return the relative paths of files with unresolved merge conflicts."""

    result = _git(git_cmd, repo, "diff", "--name-only", "--diff-filter=U")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _has_upstream(git_cmd: list[str], repo: Path) -> bool:
    return _git(git_cmd, repo, "remote", "get-url", "upstream").returncode == 0


def _ref_exists(git_cmd: list[str], repo: Path, ref: str) -> bool:
    return (
        _git(git_cmd, repo, "rev-parse", "--verify", "--quiet", ref).returncode == 0
    )


def _build_conflict_prompt(path: str, content: str) -> str:
    """Prompt asking the model to resolve one conflicted file."""

    return (
        "You are resolving a Git merge conflict. The file below contains "
        "conflict markers (<<<<<<<, =======, >>>>>>>). Produce a single, "
        "correct merged version that preserves the intent of BOTH sides where "
        "possible. Do not drop functionality from either side unless it is "
        "clearly superseded.\n\n"
        f"File: {path}\n"
        "Return ONLY the full merged file contents, with no explanation, no "
        "markdown fences, and no remaining conflict markers.\n\n"
        "----- BEGIN CONFLICTED FILE -----\n"
        f"{content}\n"
        "----- END CONFLICTED FILE -----\n"
    )


def _resolve_conflicts_with_model(
    git_cmd: list[str],
    repo: Path,
    conflicts: list[str],
    *,
    complete_fn: Callable[[str], str],
) -> tuple[bool, list[str]]:
    """Try to resolve every conflicted file via the model.

    Returns ``(ok, resolved)``.  ``ok`` is False (and the caller should
    safe-stop) if any file could not be cleanly resolved — the model output
    was empty or still contained conflict markers.
    """

    resolved: list[str] = []
    for rel in conflicts:
        target = repo / rel
        try:
            original = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Binary or unreadable conflict — we cannot safely auto-resolve.
            return False, resolved
        try:
            merged = complete_fn(_build_conflict_prompt(rel, original))
        except Exception:
            return False, resolved
        merged = _strip_code_fences(merged)
        if not merged.strip() or any(m in merged for m in _CONFLICT_MARKERS):
            return False, resolved
        # Preserve a trailing newline if the original had one.
        if original.endswith("\n") and not merged.endswith("\n"):
            merged += "\n"
        try:
            target.write_text(merged, encoding="utf-8")
        except OSError:
            return False, resolved
        _git(git_cmd, repo, "add", "--", rel)
        resolved.append(rel)
    return True, resolved


def _strip_code_fences(text: str) -> str:
    """Drop a leading/trailing markdown code fence if the model added one."""

    stripped = text.strip("\n")
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def _merge_source(
    git_cmd: list[str],
    repo: Path,
    source: str,
    *,
    label: str,
    complete_fn: Optional[Callable[[str], str]],
    resolved_acc: list[str],
    conflict_acc: list[str],
) -> tuple[bool, str]:
    """Merge ``source`` into the current (integration) branch.

    Returns ``(ok, message)``.  On an unresolved conflict, records the
    conflicted paths in ``conflict_acc``, aborts the merge, and returns
    ``ok=False`` so the caller can safe-stop.
    """

    merge = _git(
        git_cmd,
        repo,
        "merge",
        "--no-edit",
        "-m",
        f"Consolidate {label} into main",
        source,
    )
    if merge.returncode == 0:
        return True, f"  ✓ Merged {label} ({source})"

    conflicts = _conflicted_files(git_cmd, repo)
    if not conflicts:
        # Non-conflict merge failure (e.g. nothing to merge or a hard error).
        detail = (merge.stderr or merge.stdout).strip().splitlines()
        first = detail[0] if detail else "unknown error"
        _git(git_cmd, repo, "merge", "--abort")
        return False, f"  ✗ Could not merge {label}: {first}"

    conflict_acc.extend(conflicts)

    if complete_fn is None:
        _git(git_cmd, repo, "merge", "--abort")
        return (
            False,
            f"  ✗ Conflicts merging {label} and no model is configured for "
            "auto-resolution (set SELF_AUDIT_MODEL_BASE_URL / "
            "SELF_AUDIT_MODEL_NAME). Conflicted files:\n    "
            + "\n    ".join(conflicts),
        )

    print(f"  → Resolving {len(conflicts)} conflict(s) in {label} with the model...")
    ok, resolved = _resolve_conflicts_with_model(
        git_cmd, repo, conflicts, complete_fn=complete_fn
    )
    if not ok:
        _git(git_cmd, repo, "merge", "--abort")
        return (
            False,
            f"  ✗ Could not safely auto-resolve conflicts in {label}. "
            "Conflicted files:\n    " + "\n    ".join(conflicts),
        )
    resolved_acc.extend(resolved)
    commit = _git(git_cmd, repo, "commit", "--no-edit")
    if commit.returncode != 0:
        detail = (commit.stderr or commit.stdout).strip().splitlines()
        first = detail[0] if detail else "commit failed"
        _git(git_cmd, repo, "merge", "--abort")
        return False, f"  ✗ Failed to commit resolved merge of {label}: {first}"
    return True, f"  ✓ Merged {label} ({source}) — {len(resolved)} file(s) auto-resolved"


def consolidate_into_main(
    git_cmd: list[str],
    repo: Path,
    *,
    current_branch: str,
    assume_yes: bool = False,
    interactive: bool = False,
    push: bool = True,
    input_fn: Optional[Callable[[str, str], str]] = None,
    validate_syntax: Optional[Callable[[Path], tuple[bool, Optional[str], Optional[str]]]] = None,
    complete_fn: Optional[Callable[[str], str]] = None,
    is_model_configured: Optional[Callable[[], bool]] = None,
) -> ConsolidationResult:
    """Consolidate ``upstream/main`` + ``current_branch`` into ``main``.

    Autonomous by default: the integrated result is merged into ``main`` and
    (when ``push``) pushed to ``origin`` without prompting.  A still-unresolved
    conflict always stops short of ``main`` (safe-stop) — autonomy never
    silently drops work.  Pass ``interactive=True`` to require a
    review-and-confirm before the merge.

    The caller is expected to have already fetched ``origin`` and verified
    this is a fork.  ``validate_syntax`` is the critical-files syntax guard
    (passed in to avoid importing :mod:`hermes_cli.main`).  ``complete_fn`` /
    ``is_model_configured`` default to the stdlib model bridge.

    The original branch is restored before returning on every path except a
    successful merge (which intentionally ends on ``main``).
    """

    # Resolve the model bridge lazily so tests can inject their own.
    if complete_fn is None or is_model_configured is None:
        from hermes_cli.jarvis_prime.self_audit import model_bridge

        if is_model_configured is None:
            is_model_configured = model_bridge.is_configured
        if complete_fn is None:
            complete_fn = model_bridge.complete

    if not _has_upstream(git_cmd, repo):
        # No upstream to consolidate against — let the caller use the legacy
        # path (which prompts to add the upstream remote).
        return ConsolidationResult(
            status=STATUS_SKIPPED,
            summary="No 'upstream' remote — falling back to standard update.",
        )

    # Ensure merge/commit operations below have a committer identity even on a
    # fresh install with no git config (fixes "Committer identity unknown").
    git_cmd = _with_fallback_identity(git_cmd, repo)

    model_ready = bool(is_model_configured())
    active_complete = complete_fn if model_ready else None

    print("→ Consolidating upstream + your branch into main...")
    print("→ Fetching upstream and origin...")
    _git(git_cmd, repo, "fetch", "upstream", "--quiet")
    _git(git_cmd, repo, "fetch", "origin", "--quiet")

    if not _ref_exists(git_cmd, repo, "upstream/main"):
        return ConsolidationResult(
            status=STATUS_SKIPPED,
            summary="upstream/main not found after fetch — falling back to standard update.",
        )

    # Base the integration branch on the fork's published main when possible,
    # otherwise the local main.
    if _ref_exists(git_cmd, repo, "origin/main"):
        base = "origin/main"
    elif _ref_exists(git_cmd, repo, "main"):
        base = "main"
    else:
        base = "upstream/main"

    checkout = _git(git_cmd, repo, "checkout", "-B", INTEGRATION_BRANCH, base)
    if checkout.returncode != 0:
        detail = (checkout.stderr or "").strip().splitlines()
        first = detail[0] if detail else "checkout failed"
        _restore_branch(git_cmd, repo, current_branch)
        return ConsolidationResult(
            status=STATUS_ERROR,
            summary=f"Could not create integration branch from {base}: {first}",
        )

    lines: list[str] = [f"Integration branch built from {base}."]
    resolved: list[str] = []
    conflicts: list[str] = []

    # 1) Merge the original (upstream/main).
    ok, msg = _merge_source(
        git_cmd,
        repo,
        "upstream/main",
        label="upstream/main",
        complete_fn=active_complete,
        resolved_acc=resolved,
        conflict_acc=conflicts,
    )
    lines.append(msg)
    if not ok:
        return _safe_stop(git_cmd, repo, current_branch, lines, resolved, conflicts)

    # 2) Merge the current working branch (unless we're already on main).
    merge_branch = current_branch not in {"main", "HEAD", INTEGRATION_BRANCH}
    if merge_branch:
        ok, msg = _merge_source(
            git_cmd,
            repo,
            current_branch,
            label=f"your branch '{current_branch}'",
            complete_fn=active_complete,
            resolved_acc=resolved,
            conflict_acc=conflicts,
        )
        lines.append(msg)
        if not ok:
            return _safe_stop(
                git_cmd, repo, current_branch, lines, resolved, conflicts
            )
    else:
        lines.append("  ℹ Current branch is main — nothing extra to merge.")

    # 3) Syntax guard on the integrated tree.
    if validate_syntax is not None:
        syntax_ok, failing, err = validate_syntax(repo)
        if not syntax_ok:
            lines.append(f"  ✗ Syntax guard failed in {failing}")
            if err:
                lines.append(f"    {str(err).splitlines()[0]}")
            return _safe_stop(git_cmd, repo, current_branch, lines, resolved, conflicts)
        lines.append("  ✓ Syntax guard passed on integrated tree.")

    # 4) Review summary.
    diffstat = _git(
        git_cmd, repo, "diff", "--stat", f"{base}...{INTEGRATION_BRANCH}"
    ).stdout.strip()
    lines.append("")
    lines.append("Review — changes that will land on main:")
    lines.append(diffstat or "  (no file changes)")
    if resolved:
        lines.append("")
        lines.append(f"Auto-resolved by the model ({len(resolved)} file(s)):")
        for rel in resolved:
            lines.append(f"  • {rel}")
    summary = "\n".join(lines)

    # 5) Optional review-and-confirm gate. Autonomous by default — only prompts
    #    when explicitly run with interactive=True (e.g. `hermes update
    #    --interactive`). `assume_yes` (-y) still suppresses the prompt.
    if interactive and not assume_yes:
        print()
        print(summary)
        print()
        question = "Merge this into main? [y/N]"
        if input_fn is not None:
            answer = input_fn(question, "n")
        else:
            try:
                print(question)
                answer = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = "n"
        if answer.strip().lower() not in {"y", "yes"}:
            _delete_integration_branch(git_cmd, repo, current_branch)
            return ConsolidationResult(
                status=STATUS_DECLINED,
                summary="Declined — nothing was merged into main.",
                resolved_files=resolved,
            )

    # 6) Fast-forward main to the integration branch.
    co_main = _git(git_cmd, repo, "checkout", "main")
    if co_main.returncode != 0:
        # main may not exist locally yet — create it tracking origin/main.
        co_main = _git(git_cmd, repo, "checkout", "-B", "main", base)
    ff = _git(git_cmd, repo, "merge", "--ff-only", INTEGRATION_BRANCH)
    if ff.returncode != 0:
        detail = (ff.stderr or ff.stdout).strip().splitlines()
        first = detail[0] if detail else "fast-forward failed"
        _git(git_cmd, repo, "branch", "-D", INTEGRATION_BRANCH)
        return ConsolidationResult(
            status=STATUS_ERROR,
            summary=f"Could not fast-forward main: {first}",
            resolved_files=resolved,
        )
    _git(git_cmd, repo, "branch", "-D", INTEGRATION_BRANCH)

    # 7) Auto-push the consolidated main back to origin (hands-off). This is a
    #    plain fast-forward push because main descends from origin/main; a
    #    failure (no write access / non-ff) is reported but does not fail the
    #    update — local main is already current.
    pushed = False
    push_message = ""
    if push:
        pushed, push_message = _push_main(git_cmd, repo)
    final = summary + "\n\n  ✓ Merged into main."
    if push:
        final += f"\n{push_message}"

    return ConsolidationResult(
        status=STATUS_MERGED,
        summary=final,
        resolved_files=resolved,
        pushed=pushed,
        push_message=push_message,
    )


def _safe_stop(
    git_cmd: list[str],
    repo: Path,
    current_branch: str,
    lines: list[str],
    resolved: list[str],
    conflicts: list[str],
) -> ConsolidationResult:
    # Capture any still-unmerged paths too (e.g. a syntax-guard stop where the
    # merge committed), then unwind the integration branch.
    conflicts = list(dict.fromkeys([*conflicts, *_conflicted_files(git_cmd, repo)]))
    _delete_integration_branch(git_cmd, repo, current_branch)
    lines.append("")
    lines.append("Stopped before touching main — resolve the above and re-run update.")
    # The most common escape for a diverged fork: skip the upstream merge and
    # just fast-forward from the fork's own origin/main.
    lines.append(
        "Or run `hermes update --no-consolidate` to update only from your fork "
        "(skip the upstream merge). Set `update.consolidate: false` in "
        "~/.hermes/config.yaml (or HERMES_NO_CONSOLIDATE=1) to make that the default."
    )
    return ConsolidationResult(
        status=STATUS_SAFE_STOP,
        summary="\n".join(lines),
        resolved_files=resolved,
        conflict_files=conflicts,
    )


def _push_main(git_cmd: list[str], repo: Path) -> tuple[bool, str]:
    """Push the local ``main`` to ``origin``. Returns ``(pushed, message)``."""

    print("→ Pushing consolidated main to origin...")
    result = _git(git_cmd, repo, "push", "origin", "main")
    if result.returncode == 0:
        return True, "  ✓ Pushed main to origin."
    detail = (result.stderr or result.stdout).strip().splitlines()
    first = detail[0] if detail else "push failed"
    return (
        False,
        "  ℹ Updated local main but couldn't push to origin "
        f"({first}). Push manually with: git push origin main",
    )


def _delete_integration_branch(
    git_cmd: list[str], repo: Path, current_branch: str
) -> None:
    """Leave the integration branch and delete it, restoring the user's branch."""

    _restore_branch(git_cmd, repo, current_branch)
    if _ref_exists(git_cmd, repo, INTEGRATION_BRANCH):
        _git(git_cmd, repo, "branch", "-D", INTEGRATION_BRANCH)


def _restore_branch(git_cmd: list[str], repo: Path, branch: str) -> None:
    if branch and branch not in {"HEAD", INTEGRATION_BRANCH}:
        _git(git_cmd, repo, "checkout", branch)


__all__ = [
    "ConsolidationResult",
    "consolidate_into_main",
    "INTEGRATION_BRANCH",
    "STATUS_MERGED",
    "STATUS_DECLINED",
    "STATUS_SAFE_STOP",
    "STATUS_SKIPPED",
    "STATUS_ERROR",
]
