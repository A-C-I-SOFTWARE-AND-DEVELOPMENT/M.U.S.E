---
name: github-history-profile-builder
description: "Build a private local user profile from six months of GitHub history."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Profile, GitHub, History, User-Profile, Local-First, Phase-07]
    related_skills: [github-auth, github-pr-workflow]
---

# GitHub-history user-profile builder

Reads the last **six months** of the user's GitHub activity (local
commits + PRs + issues) and writes a private profile under
`.hermes-profile/` so any future assistant — Hermes, Claude, Codex,
whatever — can be useful from the first prompt instead of re-learning
the user's habits.

## When to invoke

- The user asks for a "profile build", "learn my style", "remember my
  habits", "summarize my last six months", or anything similar.
- A fresh checkout of a repo the user has been working in heavily, and
  Hermes wants to bootstrap context without burning tokens on
  exploration.
- After a major behavior change (e.g. switched primary language,
  started a new project) — re-run to refresh.

## Hard rules

1. **Explicit user approval first.** The Python module raises
   `ApprovalRequired` unless the caller passes `--approve`. Don't
   bypass it. Phase 07 says: *"Do not collect data silently. This must
   require explicit user approval."*
2. **No private code leaves the machine.** This skill never uploads
   file contents anywhere. It uses local `git log`, then the local
   `gh` CLI, then a direct GitHub REST call from the user's own
   machine — in that order.
3. **Summaries, not blobs.** What gets stored is paths, counts, commit
   subjects, PR titles. Raw file contents stay out.
4. **No secrets stored.** `GITHUB_TOKEN` is read at call time and
   never persisted. Strings that look like tokens in commit subjects
   are redacted before render.
5. **Default window is six months** (`183` days). Override only when
   the user asks.

## Preview flow (no writes)

```bash
python -m hermes_cli.user_profile_builder \
  --repo "$PWD" \
  --user "<github-login>"
```

Prints a preview of every section to stdout. Nothing is written. Use
this to show the user what they'll get before asking to commit it.

## Approved build (writes to disk)

```bash
python -m hermes_cli.user_profile_builder \
  --repo "$PWD" \
  --user "<github-login>" \
  --approve
```

Writes:

| File | Purpose |
| --- | --- |
| `.hermes-profile/user-profile.md` | Plain-English summary for future assistants |
| `.hermes-profile/coding-style.md` | Language + commit-message conventions |
| `.hermes-profile/common-mistakes.md` | Recurring bug categories Hermes should watch for |
| `.hermes-profile/preferred-stack.md` | Languages, repos, labels in rotation |
| `.hermes-profile/validation-preferences.md` | Testing + docs habits, validation gaps |
| `.hermes-profile/github-history-summary.json` | Machine-readable rollup |

`.gitignore` is updated automatically to keep these artifacts local.

## Custom window

```bash
python -m hermes_cli.user_profile_builder --user <login> --since 90 --approve
```

`--since` is in days. Six months is the default because that's what
the Phase 07 mission specifies.

## Skipping data sources

- `--no-gh` — skip the `gh` CLI even if installed/authed.
- `--no-api` — skip the REST fallback even when `GITHUB_TOKEN` is set.

Both are useful for tests and air-gapped runs.

## What the profile covers

- Preferred languages & frameworks
- Repeated project types
- Commit message style + PR style
- Common bug categories
- Testing + documentation habits
- Mobile / Termux preferences
- AI-agent workflow preferences (Claude / Codex / Hermes)
- Mistakes Hermes should watch for
- Plain-English notes for future assistants

## Re-running

Safe to re-run. The output files are overwritten; nothing is
appended. The `.gitignore` line is only added once.

## Validation

```bash
python -m py_compile hermes_cli/user_profile_builder.py hermes_cli/github_history.py
python -m pytest tests/test_user_profile_builder.py -q
```
