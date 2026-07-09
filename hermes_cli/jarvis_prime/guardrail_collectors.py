"""Artifact collectors for verifiable guardrails.

Each collector observes reality and returns a content-addressed
:class:`~hermes_cli.jarvis_prime.guardrail_evidence.EvidenceArtifact`. Collectors
are deliberately conservative:

* **Read-only by default.** ``collect_git_diff_evidence`` only runs read-only
  git plumbing; ``collect_test_evidence`` executes nothing unless the caller sets
  ``run=True`` *and* the command passes a strict allowlist; ``collect_rollback_
  evidence`` validates a plan but never reverts anything.
* **Secret-safe.** ``collect_secret_scan_evidence`` records redacted snippets
  only — a raw credential never reaches an artifact or the ledger.
* **Crash-resistant.** Missing git / unreadable files degrade to a recorded
  fact (``git_available=False``), never an exception.

Stdlib-only.
"""

from __future__ import annotations

import fnmatch
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Mapping, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import (
    EvidenceArtifact,
    GitDiffEvidence,
    RollbackEvidence,
    ReviewEvidence,
    SecretScanEvidence,
    VerificationCommandResult,
    sha256_hex,
)

_OUTPUT_TAIL = 4096  # bytes of stdout/stderr kept per command
_DEFAULT_TIMEOUT = 120
_VERDICTS = frozenset({"approve", "request_changes", "blocked", "needs_owner"})

# Allowlist of first tokens a verification command may start with. Anything
# else is refused — collectors never become an arbitrary-shell primitive.
_SAFE_COMMAND_HEADS = (
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("python", "-m", "compileall"),
    ("python3", "-m", "compileall"),
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
    ("ruff",),
    ("mypy",),
    ("git",),
)
_FORBIDDEN_TOKENS = frozenset(
    {"rm", "curl", "wget", "ssh", "scp", "sudo", "chmod", "chown", "mv", "dd"}
)
_SHELL_METACHARS = set(";|&`$><\n")


# ---------------------------------------------------------------------------
# Git diff evidence
# ---------------------------------------------------------------------------


def _git(repo_root: str, args: Sequence[str], timeout: int = 15) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0 and not proc.stdout:
        # diff --check returns non-zero with findings on stdout; preserve those.
        return proc.stdout or ""
    return proc.stdout


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or path == pat:
            return True
        # Support ``dir/`` prefixes and ``**`` style allow entries.
        if pat.endswith("/**") and path.startswith(pat[:-3]):
            return True
        if "**" in pat:
            simplified = pat.replace("**/", "").replace("/**", "")
            if fnmatch.fnmatch(path, simplified) or fnmatch.fnmatch(
                path, f"*/{simplified}"
            ):
                return True
    return False


def collect_git_diff_evidence(
    repo_root: str,
    allowed_files: Sequence[str] = (),
    protected_files: Sequence[str] = (),
    *,
    author_id: str = "",
) -> EvidenceArtifact:
    """Capture the working-tree diff state without mutating the repo.

    ``author_id`` records the AGENT that authored the change under review, in
    the same identity namespace as a review's ``reviewer_id`` (see
    ``collect_review_evidence``). Callers that know the acting agent id must
    pass it so the strict review gate's C19 builder ≠ reviewer check can fire;
    left blank the gate fails open (see ``strict_review_gate``).
    """

    root = str(repo_root or ".")
    author = str(author_id or "").strip()
    branch_raw = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch_raw is None:
        return GitDiffEvidence(
            repo_root=root, git_available=False, author_id=author
        ).to_artifact()

    branch = branch_raw.strip()
    head = (_git(root, ["rev-parse", "HEAD"]) or "").strip()
    status = _git(root, ["status", "--porcelain"]) or ""
    name_only = _git(root, ["diff", "--name-only", "HEAD"]) or ""
    diff_check = _git(root, ["diff", "--check"]) or ""

    changed: list[str] = []
    for line in status.splitlines():
        # porcelain: XY<space>path  (handle rename "old -> new")
        entry = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry:
            changed.append(entry)
    for line in name_only.splitlines():
        if line.strip() and line.strip() not in changed:
            changed.append(line.strip())

    allowed = tuple(allowed_files)
    out_of_scope = (
        tuple(f for f in changed if not _matches_any(f, allowed)) if allowed else ()
    )
    protected_touched = tuple(
        f for f in changed if _matches_any(f, tuple(protected_files))
    )

    return GitDiffEvidence(
        repo_root=root,
        git_available=True,
        branch=branch,
        head_commit=head,
        changed_files=tuple(changed),
        out_of_scope_files=out_of_scope,
        protected_files_touched=protected_touched,
        working_tree_clean=not bool(status.strip()),
        diff_check_passed=not bool(diff_check.strip()),
        status_porcelain=status[:_OUTPUT_TAIL],
        author_id=author,
    ).to_artifact()


# ---------------------------------------------------------------------------
# Test execution evidence
# ---------------------------------------------------------------------------


def _is_safe_command(command: str) -> bool:
    if not command or any(c in _SHELL_METACHARS for c in command):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if not tokens:
        return False
    if any(t in _FORBIDDEN_TOKENS for t in tokens):
        return False
    for head in _SAFE_COMMAND_HEADS:
        if tuple(tokens[: len(head)]) == head:
            return True
    return False


def collect_test_evidence(
    repo_root: str,
    commands: Sequence[str],
    run: bool = False,
    timeout: int = _DEFAULT_TIMEOUT,
) -> list[EvidenceArtifact]:
    """Capture verification-command evidence.

    With ``run=False`` (default) each command is recorded as *planned* — an
    explicit non-pass marker, so a planned command can never satisfy the strict
    test gate. With ``run=True`` only allowlisted commands execute; anything else
    is recorded as refused (``passed=False``).
    """

    root = str(repo_root or ".")
    artifacts: list[EvidenceArtifact] = []
    for command in commands:
        command = str(command)
        if not run:
            artifacts.append(
                VerificationCommandResult(
                    command=command,
                    cwd=root,
                    exit_code=None,
                    passed=False,
                    duration_seconds=0.0,
                    executed=False,
                    skipped_reason="planned (not executed)",
                ).to_artifact()
            )
            continue
        if not _is_safe_command(command):
            artifacts.append(
                VerificationCommandResult(
                    command=command,
                    cwd=root,
                    exit_code=None,
                    passed=False,
                    duration_seconds=0.0,
                    executed=False,
                    skipped_reason="refused: command not in safety allowlist",
                ).to_artifact()
            )
            continue
        artifacts.append(_run_one(root, command, timeout))
    return artifacts


def _run_one(root: str, command: str, timeout: int) -> EvidenceArtifact:
    started = time.monotonic()
    timed_out = False
    exit_code: Optional[int] = None
    stdout = stderr = ""
    try:
        proc = subprocess.run(
            shlex.split(command),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=max(1, timeout),
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except (FileNotFoundError, OSError) as exc:
        stderr = f"failed to execute: {exc}"
    duration = time.monotonic() - started
    return VerificationCommandResult(
        command=command,
        cwd=root,
        exit_code=exit_code,
        passed=(exit_code == 0 and not timed_out),
        duration_seconds=duration,
        timed_out=timed_out,
        stdout_tail=stdout[-_OUTPUT_TAIL:],
        stderr_tail=stderr[-_OUTPUT_TAIL:],
        executed=True,
    ).to_artifact()


# ---------------------------------------------------------------------------
# Secret scan evidence
# ---------------------------------------------------------------------------


def _secret_patterns():
    """Return the canonical secret regex tuple (reused from the memory gate)."""

    try:
        from hermes_cli.jarvis_prime.memory_tree import _SECRET_PATTERNS

        return _SECRET_PATTERNS
    except Exception:  # pragma: no cover - defensive fallback
        import re

        return (
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
            re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
            re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
            re.compile(
                r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*\S{6,}"
            ),
        )


def _redact(text: str) -> str:
    try:
        from gateway.cockpit.redaction import redact_text

        return redact_text(text)
    except Exception:  # pragma: no cover - defensive fallback
        return "[REDACTED]"


def collect_secret_scan_evidence(
    repo_root: str,
    files: Sequence[str],
) -> EvidenceArtifact:
    """Scan only the supplied files for secrets, recording redacted snippets.

    Never scans the whole home directory; never stores a raw secret.
    """

    root = Path(repo_root or ".")
    patterns = _secret_patterns()
    findings: list[Mapping[str, object]] = []
    scanned: list[str] = []
    for rel in files:
        rel = str(rel)
        path = root / rel
        if not path.is_file():
            continue
        scanned.append(rel)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if any(p.search(line) for p in patterns):
                snippet = _redact(line).strip()
                findings.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "redacted_excerpt": snippet[:200],
                    }
                )
    return SecretScanEvidence(
        subject=str(repo_root or "."),
        files_scanned=tuple(scanned),
        findings=tuple(findings),
    ).to_artifact()


# ---------------------------------------------------------------------------
# Review evidence
# ---------------------------------------------------------------------------


def collect_review_evidence(
    review_text: str,
    reviewer_id: str,
    diff_hash: str,
    verdict: str = "approve",
    risk_class: str = "RC1",
    contrarian_notes: Sequence[str] = (),
) -> EvidenceArtifact:
    """Capture reviewer evidence; raise on an unusable review.

    A real review must have non-empty text and an explicit verdict. RC2+ work
    additionally requires at least one contrarian / risk note — a rubber-stamp
    "looks good" is not acceptable review evidence for code changes.
    """

    text = (review_text or "").strip()
    if not text:
        raise ValueError("review text must be non-empty")
    if verdict not in _VERDICTS:
        raise ValueError(
            f"verdict must be one of {sorted(_VERDICTS)}, got {verdict!r}"
        )
    notes = tuple(n for n in contrarian_notes if n and n.strip())
    rc = (risk_class or "RC1").upper()
    if rc >= "RC2" and verdict == "approve" and not notes:
        raise ValueError("RC2+ approval requires at least one contrarian/risk note")
    return ReviewEvidence(
        reviewer_id=reviewer_id or "unknown",
        verdict=verdict,
        diff_hash=diff_hash or "",
        review_hash=sha256_hex(text),
        summary=text[:500],
        contrarian_notes=notes,
    ).to_artifact()


def collect_reviewer_assignment_evidence(
    reviewer_id: str,
    diff_hash: str = "",
) -> Optional[EvidenceArtifact]:
    """Record the *planned reviewer assignment* as review evidence.

    This exists so the strict review gate's Clause C19 (builder ≠ reviewer)
    identity check is REACHABLE at assembly time even before a human/agent
    review has actually run. Assembly sites (``nlp_refine.run_execution_
    refinement``, ``guardrails_cli._collect``) know only *which* agent is
    assigned to review — never a real verdict.

    Safety: the verdict is fixed to ``needs_owner`` (a NON-approving, neutral
    verdict). It can NEVER cause the review gate to PASS — the gate maps
    ``needs_owner`` to ``NEEDS_OWNER_APPROVAL`` and only an explicit ``approve``
    verdict passes. So this never fabricates an approval; it only lets C19
    compare the assigned reviewer against the builder. When ``reviewer_id`` is
    blank (no reviewer assigned) it returns ``None`` and adds nothing — flows
    without a reviewer are unchanged.

    A real ``approve``/``request_changes`` verdict must still come from an
    actual review step via ``collect_review_evidence``; this assignment
    artifact is deliberately not a substitute for that.
    """

    reviewer = str(reviewer_id or "").strip()
    if not reviewer or reviewer.lower() == "unknown":
        return None
    summary = (
        "reviewer assignment recorded (no verdict yet); a real review verdict "
        "must come from an actual review step"
    )
    return ReviewEvidence(
        reviewer_id=reviewer,
        verdict="needs_owner",
        diff_hash=diff_hash or "",
        review_hash=sha256_hex(summary),
        summary=summary,
        contrarian_notes=(),
    ).to_artifact()


# ---------------------------------------------------------------------------
# Rollback evidence
# ---------------------------------------------------------------------------


def collect_rollback_evidence(
    repo_root: str,
    rollback_plan: Sequence[str],
    changed_files: Sequence[str] = (),
    commit_hash: str = "",
    branch: str = "",
    revert_instructions: str = "",
) -> EvidenceArtifact:
    """Validate a rollback plan's operational plausibility (never executes)."""

    plan = tuple(s for s in rollback_plan if s and str(s).strip())
    reasons: list[str] = []
    if not plan:
        reasons.append("rollback plan is empty")
    has_branch_path = bool(branch and changed_files)
    has_commit_path = bool(commit_hash and revert_instructions)
    if not has_branch_path and not has_commit_path:
        reasons.append(
            "need either (branch + changed_files) or (commit_hash + revert "
            "instructions) to be reversible"
        )
    return RollbackEvidence(
        repo_root=str(repo_root or "."),
        plan=plan,
        plausible=not reasons,
        branch=branch,
        commit_hash=commit_hash,
        changed_files=tuple(changed_files),
        revert_instructions=revert_instructions,
        reasons=tuple(reasons),
    ).to_artifact()


__all__ = [
    "collect_git_diff_evidence",
    "collect_test_evidence",
    "collect_secret_scan_evidence",
    "collect_review_evidence",
    "collect_reviewer_assignment_evidence",
    "collect_rollback_evidence",
]
