# Hermes user profile — {user_label}

_Built from the last {window_days} days of GitHub history (since
{since_iso}). Sources: {sources}._

This file is private to this machine. It exists so Hermes (and any
future AI assistant you point at this repo) can be useful from the
first prompt instead of needing to re-learn six months of habits.

## Snapshot

- Commits in window: **{commit_count}**
- PRs in window: **{pr_count}** (merged {pr_merged}, open {pr_open})
- Issues in window: **{issue_count}** (closed {issue_closed})
- Languages touched most: {top_languages}
- Repos most active in PRs: {top_repos}

## Preferred languages and frameworks

{language_bullets}

## Repeated project types

{project_type_bullets}

## Commit message style

- Average subject length: {avg_subject_length} characters
- Commits with an explanatory body: {bodies_with_explanation}
- Multi-line messages: {multi_line_messages}
- Fix-shaped messages: {fix_pct}%
- Feature-shaped messages: {feature_pct}%
- Refactor-shaped messages: {refactor_pct}%

## PR style

- Average PR title length: {avg_pr_title_length} characters
- PRs with a non-trivial body: {pr_body_usage_pct}%
- Frequent PR labels: {top_labels}

## Common bug categories

{bug_category_bullets}

## Testing habits

- Commits touching test files: {test_touches}
- Commits touching docs/Markdown: {docs_touches}

## Documentation habits

- Docs are written alongside code in this checkout's history. If
  you're an assistant editing here, update the relevant `docs/` page
  in the same PR as the code change.

## Mobile / Termux preferences

- Mobile-shaped commit messages in window: {mobile_intent}
- Treat Termux as a first-class target when the change touches the
  gateway, the Android cockpit, or anything under `apps/android/`.

## AI-agent workflow preferences

- AI-shaped commit messages in window: {ai_intent}
- Hermes / Claude / Codex appear regularly in commit context. Don't
  be shy about referencing the orchestration stack in PRs.

## Mistakes Hermes should watch for

See `common-mistakes.md` for the full breakdown. The headline
categories from this window are listed above under **Common bug
categories**.

## Plain-English notes for future assistants

- Read `AGENTS.md` and `CLAUDE.md` before touching anything.
- Prefer editing existing files to creating new ones.
- The user owns six months of muscle-memory in these repos; match
  their style, don't introduce a new one.
- Don't silently collect more profile data. Re-run
  `muse_cli.user_profile_builder` with `--approve` only when the
  user explicitly asks for an update.
