"""Build a private, local user profile from six months of GitHub history.

This is the orchestrator for Phase 07. It calls into
:mod:`hermes_cli.github_history` for raw signal, rolls the signal into
plain-English profile sections, and writes the result to
``.hermes-profile/`` inside the target repo (or a caller-chosen path).

Approval gate
-------------
``build_profile(..., approved=False)`` returns the rendered profile
*without writing anything to disk*. The CLI front-end is required to
prompt the user first and only call again with ``approved=True`` once
the user says yes. The Phase 07 mission line ("Do not collect data
silently. This must require explicit user approval.") is enforced
here by raising :class:`ApprovalRequired` from :func:`write_profile`
when the flag isn't set.

What gets written
-----------------
- ``user-profile.md``                  — top-level, human-first summary
- ``coding-style.md``                  — language / commit-style notes
- ``common-mistakes.md``               — recurring fix categories
- ``preferred-stack.md``               — languages & repos in rotation
- ``validation-preferences.md``        — testing & docs habits
- ``github-history-summary.json``      — machine-readable rollup

Plus ``.gitignore`` is updated to ignore ``.hermes-profile/`` so the
artifacts don't sneak into the next commit.

Security
~~~~~~~~
- Raw file contents are never stored; only paths and add/del counts.
- Secret-shaped strings in commit subjects are redacted before render.
- The token used to talk to GitHub is read from env at call time and
  never written back out.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from hermes_cli import github_history as gh_history

__all__ = [
    "ApprovalRequired",
    "PROFILE_DIR_NAME",
    "ProfileArtifacts",
    "build_profile",
    "render_user_profile",
    "render_coding_style",
    "render_common_mistakes",
    "render_preferred_stack",
    "render_validation_preferences",
    "render_history_summary_json",
    "write_profile",
    "ensure_gitignore",
    "redact_secrets",
    "main",
]

PROFILE_DIR_NAME = ".hermes-profile"


# Patterns that look like leaked secrets. We never want these in a
# rendered profile, even if the user copy-pasted a token into a commit.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github-app-token", re.compile(r"\bghs_[A-Za-z0-9]{20,}\b")),
    ("anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9-]{20,}\b")),
    ("openai", re.compile(r"\bsk-[A-Za-z0-9]{30,}\b")),
    ("aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("pem", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
]


class ApprovalRequired(RuntimeError):
    """Raised when an unapproved caller tries to write profile data."""


@dataclass
class ProfileArtifacts:
    output_dir: Path
    files: dict[str, Path]
    snapshot_path: Optional[Path]
    rendered: dict[str, str]


def redact_secrets(text: str) -> str:
    """Replace anything that looks like a credential with ``[REDACTED]``."""

    if not text:
        return text or ""
    cleaned = text
    for _label, pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def _fmt_pair(items: Sequence[tuple[str, int]], *, limit: int = 6) -> str:
    if not items:
        return "_none observed in window_"
    parts = [f"`{name}` ({count})" for name, count in items[:limit]]
    return ", ".join(parts)


def _fmt_bullet_pair(items: Sequence[tuple[str, int]], *, limit: int = 6) -> list[str]:
    if not items:
        return ["- _none observed in window_"]
    return [f"- `{name}` — {count}" for name, count in items[:limit]]


def _commit_intent_pct(summary: dict, key: str) -> float:
    total = summary.get("total_commits") or 0
    if total <= 0:
        return 0.0
    return round(100.0 * (summary.get(key) or 0) / total, 1)


# ── renderers ──────────────────────────────────────────────────────────────


def render_user_profile(
    *,
    snapshot: gh_history.HistorySnapshot,
    commit_summary: dict,
    pr_summary: dict,
    issue_summary: dict,
    user_label: str,
) -> str:
    """The flagship plain-English ``user-profile.md`` file."""

    sources = ", ".join(snapshot.sources_used) or "none"
    languages = _fmt_pair(commit_summary.get("languages", []))
    top_repos = _fmt_pair(pr_summary.get("top_repos", []))
    lines = [
        f"# muse user profile — {user_label}",
        "",
        f"_Built from the last {snapshot.window_days} days of GitHub history "
        f"(since {snapshot.since}). Sources: {sources}._",
        "",
        "This file is private to this machine. It exists so muse (and any "
        "future AI assistant you point at this repo) can be useful from the "
        "first prompt instead of needing to re-learn six months of habits.",
        "",
        "## Snapshot",
        "",
        f"- Commits in window: **{commit_summary.get('total_commits', 0)}**",
        f"- PRs in window: **{pr_summary.get('total', 0)}** "
        f"(merged {pr_summary.get('merged', 0)}, open {pr_summary.get('open', 0)})",
        f"- Issues in window: **{issue_summary.get('total', 0)}** "
        f"(closed {issue_summary.get('closed', 0)})",
        f"- Languages touched most: {languages}",
        f"- Repos most active in PRs: {top_repos}",
        "",
        "## Preferred languages and frameworks",
        "",
        *_fmt_bullet_pair(commit_summary.get("languages", [])),
        "",
        "## Repeated project types",
        "",
    ]

    repeated = _detect_project_types(snapshot, commit_summary)
    if repeated:
        for label, evidence in repeated:
            lines.append(f"- **{label}** — {evidence}")
    else:
        lines.append("- _Not enough signal yet; needs more commits/PRs to detect._")

    lines.extend([
        "",
        "## Commit message style",
        "",
        f"- Average subject length: {commit_summary.get('avg_subject_length', 0)} characters",
        f"- Commits with an explanatory body: {commit_summary.get('bodies_with_explanation', 0)}",
        f"- Multi-line messages: {commit_summary.get('multi_line_messages', 0)}",
        f"- Fix-shaped messages: {_commit_intent_pct(commit_summary, 'fix_intent')}%",
        f"- Feature-shaped messages: {_commit_intent_pct(commit_summary, 'feature_intent')}%",
        f"- Refactor-shaped messages: {_commit_intent_pct(commit_summary, 'refactor_intent')}%",
        "",
        "## PR style",
        "",
        f"- Average PR title length: {pr_summary.get('avg_title_length', 0)} characters",
        f"- PRs with a non-trivial body: {pr_summary.get('body_usage_pct', 0)}%",
        f"- Frequent PR labels: {_fmt_pair(pr_summary.get('common_labels', []))}",
        "",
        "## Common bug categories",
        "",
        *_fmt_bullet_pair(
            sorted(
                (commit_summary.get("bug_categories") or {}).items(),
                key=lambda kv: kv[1],
                reverse=True,
            )
        ),
        "",
        "## Testing habits",
        "",
        f"- Commits touching test files: {commit_summary.get('test_touches', 0)}",
        f"- Commits touching docs/Markdown: {commit_summary.get('docs_touches', 0)}",
        "",
        "## Documentation habits",
        "",
        "- Docs are written alongside code in this checkout's history. "
        "If you're an assistant editing here, update the relevant "
        "`docs/` page in the same PR as the code change.",
        "",
        "## Mobile / Termux preferences",
        "",
        f"- Mobile-shaped commit messages in window: "
        f"{commit_summary.get('mobile_intent', 0)}",
        "- Treat Termux as a first-class target when the change touches "
        "the gateway, the Android cockpit, or anything under `apps/android/`.",
        "",
        "## AI-agent workflow preferences",
        "",
        f"- AI-shaped commit messages in window: "
        f"{commit_summary.get('ai_intent', 0)}",
        "- muse / Claude / Codex appear regularly in commit context. "
        "Don't be shy about referencing the orchestration stack in PRs.",
        "",
        "## Mistakes muse should watch for",
        "",
        "See `common-mistakes.md` for the full breakdown. The headline "
        "categories from this window are listed above under "
        "**Common bug categories**.",
        "",
        "## Plain-English notes for future assistants",
        "",
        "- Read `AGENTS.md` and `CLAUDE.md` before touching anything.",
        "- Prefer editing existing files to creating new ones.",
        "- The user owns six months of muscle-memory in these repos; "
        "match their style, don't introduce a new one.",
        "- Don't silently collect more profile data. Re-run "
        "`hermes_cli.user_profile_builder` with `--approve` only when "
        "the user explicitly asks for an update.",
        "",
    ])

    if snapshot.notes:
        lines.append("## Build notes")
        lines.append("")
        for note in snapshot.notes:
            lines.append(f"- {redact_secrets(note)}")
        lines.append("")

    return redact_secrets("\n".join(lines))


def render_coding_style(commit_summary: dict, pr_summary: dict) -> str:
    languages = _fmt_bullet_pair(commit_summary.get("languages", []))
    repos = _fmt_bullet_pair(pr_summary.get("top_repos", []))
    lines = [
        "# Coding style",
        "",
        "_Derived from the last six months of commit + PR signal._",
        "",
        "## Languages by commit count",
        "",
        *languages,
        "",
        "## Most active repos",
        "",
        *repos,
        "",
        "## Commit message conventions",
        "",
        f"- Subjects average {commit_summary.get('avg_subject_length', 0)} chars",
        f"- {_commit_intent_pct(commit_summary, 'fix_intent')}% are framed as fixes",
        f"- {_commit_intent_pct(commit_summary, 'feature_intent')}% are framed as features",
        f"- {_commit_intent_pct(commit_summary, 'refactor_intent')}% are framed as refactors",
        "",
        "## Files touched most often",
        "",
    ]
    lines.extend(_fmt_bullet_pair(commit_summary.get("hot_files", []), limit=10))
    lines.append("")
    return redact_secrets("\n".join(lines))


def render_common_mistakes(commit_summary: dict, issue_summary: dict) -> str:
    categories = sorted(
        (commit_summary.get("bug_categories") or {}).items(),
        key=lambda kv: kv[1],
        reverse=True,
    )
    lines = [
        "# Common mistakes muse should watch for",
        "",
        "_Pattern-match on commit subjects + bodies + PR/issue titles. "
        "Counts are evidence, not absolutes — re-run the builder for "
        "fresher numbers._",
        "",
        "## Recurring categories",
        "",
        *_fmt_bullet_pair(categories),
        "",
        "## Issue labels that recur",
        "",
        *_fmt_bullet_pair(issue_summary.get("common_labels", [])),
        "",
        "## Suggested guardrails",
        "",
        "- Before changing a function that previously caused a regression, "
        "  re-read the most recent fix commit that touched the same file.",
        "- For any category above with a count ≥ 3, treat it as a "
        "  *known weak spot* — add a checklist item to the PR template.",
        "- If a category here is missing from `validation-preferences.md`, "
        "  open a follow-up to add a regression test.",
        "",
    ]
    return redact_secrets("\n".join(lines))


def render_preferred_stack(commit_summary: dict, pr_summary: dict) -> str:
    lines = [
        "# Preferred stack",
        "",
        "## Languages",
        "",
        *_fmt_bullet_pair(commit_summary.get("languages", [])),
        "",
        "## Repos in rotation",
        "",
        *_fmt_bullet_pair(pr_summary.get("top_repos", [])),
        "",
        "## Frequent PR labels (project signals)",
        "",
        *_fmt_bullet_pair(pr_summary.get("common_labels", [])),
        "",
        "## What to default to",
        "",
        "- When a language choice is open, pick from the list above.",
        "- When opening a PR, mirror the label set the user reaches for "
        "most often in recent history.",
        "",
    ]
    return redact_secrets("\n".join(lines))


def render_validation_preferences(commit_summary: dict) -> str:
    test_touches = commit_summary.get("test_touches", 0)
    docs_touches = commit_summary.get("docs_touches", 0)
    total = commit_summary.get("total_commits", 0) or 1
    test_ratio = round(100.0 * test_touches / total, 1)
    docs_ratio = round(100.0 * docs_touches / total, 1)
    lines = [
        "# Validation preferences",
        "",
        f"- ~{test_ratio}% of commits in window touched test files",
        f"- ~{docs_ratio}% of commits in window touched docs/Markdown",
        "",
        "## Gaps to watch",
        "",
        "- If a code change in this checkout doesn't touch a test file, "
        "  raise it explicitly before the PR is opened.",
        "- If a public API or behavior changes and no `docs/` file was "
        "  updated, that's a validation gap — fix in the same PR.",
        "- The orchestration stack has a validation gate; never push "
        "  past it by editing ledger entries directly.",
        "",
        "## Quick checklist for a 'safe' PR in this repo",
        "",
        "- [ ] Code change is paired with a test (or an explicit waiver)",
        "- [ ] Docs touched if behavior changed",
        "- [ ] No secrets staged (`.env` / API keys)",
        "- [ ] Commit subject ≤ 72 chars, body explains the *why*",
        "- [ ] PR body mentions the related issue / job / ledger entry",
        "",
    ]
    return redact_secrets("\n".join(lines))


def render_history_summary_json(
    snapshot: gh_history.HistorySnapshot,
    commit_summary: dict,
    pr_summary: dict,
    issue_summary: dict,
) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": snapshot.user,
        "since": snapshot.since,
        "window_days": snapshot.window_days,
        "sources_used": snapshot.sources_used,
        "notes": snapshot.notes,
        "commits": commit_summary,
        "pull_requests": pr_summary,
        "issues": issue_summary,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _detect_project_types(
    snapshot: gh_history.HistorySnapshot, commit_summary: dict
) -> list[tuple[str, str]]:
    """Heuristic mapping of file patterns -> project-type buckets."""

    file_hits: dict[str, int] = {}
    for sha_commit in snapshot.commits:
        for path in sha_commit.files:
            file_hits[path] = file_hits.get(path, 0) + 1

    matches: list[tuple[str, str]] = []
    rules = [
        ("Python tooling", re.compile(r"^(hermes_cli|tools|plugins|agent)/.*\.py$")),
        ("Android cockpit", re.compile(r"^apps/android/")),
        ("Gateway adapters", re.compile(r"^gateway/")),
        ("Orchestration", re.compile(r"^(docs/orchestration|hermes_cli/orchestrator)")),
        ("Skills authoring", re.compile(r"^skills/")),
        ("Docs / website", re.compile(r"^(docs|website|README)")),
        ("Tests", re.compile(r"^tests/")),
    ]
    for label, pat in rules:
        count = sum(n for path, n in file_hits.items() if pat.search(path))
        if count >= 3:
            matches.append((label, f"{count} touches"))
    return matches


# ── disk side-effects (gated by approval) ──────────────────────────────────


def ensure_gitignore(repo_root: Path) -> bool:
    """Add ``.hermes-profile/`` to ``.gitignore`` if not already present."""

    gitignore = repo_root / ".gitignore"
    line = f"{PROFILE_DIR_NAME}/"
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        if any(stripped == line for stripped in (s.strip() for s in existing.splitlines())):
            return False
        suffix = "" if existing.endswith("\n") else "\n"
        gitignore.write_text(
            existing + f"{suffix}# Local muse user profile (Phase 07 builder)\n{line}\n",
            encoding="utf-8",
        )
        return True
    gitignore.write_text(
        f"# Local muse user profile (Phase 07 builder)\n{line}\n",
        encoding="utf-8",
    )
    return True


def build_profile(
    repo_root: Path,
    *,
    user: Optional[str] = None,
    window_days: int = gh_history.DEFAULT_WINDOW_DAYS,
    snapshot: Optional[gh_history.HistorySnapshot] = None,
    allow_gh: bool = True,
    allow_api: bool = True,
    now: Optional[datetime] = None,
) -> dict[str, str]:
    """Render every profile file in-memory and return a name -> content map.

    No disk writes happen here. Pass the result to :func:`write_profile`
    after the caller has obtained user approval.
    """

    if snapshot is None:
        snapshot = gh_history.collect_history(
            repo_root,
            user=user,
            window_days=window_days,
            allow_gh=allow_gh,
            allow_api=allow_api,
            now=now,
        )

    commit_summary = gh_history.summarize_commits(snapshot.commits)
    pr_summary = gh_history.summarize_pull_requests(snapshot.pull_requests)
    issue_summary = gh_history.summarize_issues(snapshot.issues)

    user_label = user or "this user"
    return {
        "user-profile.md": render_user_profile(
            snapshot=snapshot,
            commit_summary=commit_summary,
            pr_summary=pr_summary,
            issue_summary=issue_summary,
            user_label=user_label,
        ),
        "coding-style.md": render_coding_style(commit_summary, pr_summary),
        "common-mistakes.md": render_common_mistakes(commit_summary, issue_summary),
        "preferred-stack.md": render_preferred_stack(commit_summary, pr_summary),
        "validation-preferences.md": render_validation_preferences(commit_summary),
        "github-history-summary.json": render_history_summary_json(
            snapshot, commit_summary, pr_summary, issue_summary
        ),
    }


def write_profile(
    repo_root: Path,
    rendered: dict[str, str],
    *,
    approved: bool,
    update_gitignore: bool = True,
    snapshot: Optional[gh_history.HistorySnapshot] = None,
) -> ProfileArtifacts:
    """Persist the rendered profile files. Refuses without ``approved=True``.

    The approval gate enforces the Phase 07 rule
    ``Do not collect data silently. This must require explicit user approval.``
    """

    if not approved:
        raise ApprovalRequired(
            "user-profile builder requires explicit approval before writing "
            "to disk (see SKILL.md / docs/profile/...)"
        )
    out_dir = repo_root / PROFILE_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    for name, content in rendered.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        files[name] = path
    snapshot_path: Optional[Path] = None
    if snapshot is not None:
        snapshot_path = out_dir / "snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot.as_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if update_gitignore:
        ensure_gitignore(repo_root)
    return ProfileArtifacts(
        output_dir=out_dir,
        files=files,
        snapshot_path=snapshot_path,
        rendered=rendered,
    )


# ── CLI front-end ──────────────────────────────────────────────────────────


def _format_preview(rendered: dict[str, str]) -> str:
    lines = ["# muse user-profile preview", ""]
    for name in sorted(rendered):
        body = rendered[name]
        head = "\n".join(body.splitlines()[:6])
        lines.append(f"## {name}")
        lines.append("")
        lines.append(head)
        lines.append("")
        lines.append("…")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.user_profile_builder",
        description=(
            "Build a private, local user profile from the last six months "
            "of GitHub history. Writes to .hermes-profile/ inside the repo."
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Git checkout to analyse (default: cwd).",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="GitHub login to filter PRs/issues by (and commit author).",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=gh_history.DEFAULT_WINDOW_DAYS,
        help=f"Window in days (default {gh_history.DEFAULT_WINDOW_DAYS} ≈ six months).",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Required to actually write .hermes-profile/ to disk.",
    )
    parser.add_argument(
        "--no-gh",
        action="store_true",
        help="Skip the gh CLI source even if available.",
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Skip the GitHub REST API fallback even if GITHUB_TOKEN is set.",
    )
    parser.add_argument(
        "--include-snapshot",
        action="store_true",
        help="Also write the raw snapshot.json (summaries, not file contents).",
    )
    args = parser.parse_args(argv)

    snapshot = gh_history.collect_history(
        args.repo,
        user=args.user,
        window_days=args.since,
        allow_gh=not args.no_gh,
        allow_api=not args.no_api,
    )
    rendered = build_profile(
        args.repo,
        user=args.user,
        window_days=args.since,
        snapshot=snapshot,
    )

    if not args.approve:
        print(_format_preview(rendered))
        print(
            "\n[approval required] pass --approve to write "
            f"{args.repo / PROFILE_DIR_NAME}",
            file=sys.stderr,
        )
        return 0

    artifacts = write_profile(
        args.repo,
        rendered,
        approved=True,
        snapshot=snapshot if args.include_snapshot else None,
    )
    print(f"wrote {len(artifacts.files)} files to {artifacts.output_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
