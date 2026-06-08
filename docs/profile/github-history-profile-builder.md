# GitHub-history user-profile builder

The `github-history-profile-builder` skill (and its companion modules
`hermes_cli.user_profile_builder` + `hermes_cli.github_history`) read
the last **six months** of the user's GitHub activity and produce a
private, local profile that any future assistant can use to ramp up
fast.

This page is the long-form explainer. The terse "how do I run it"
version lives in
[`skills/github-history-profile-builder/SKILL.md`](../../skills/github-history-profile-builder/SKILL.md).

## Why it exists

M.U.S.E. is designed to work across sessions, machines, and models.
Without a profile, every new assistant has to re-discover the user's
preferred languages, commit conventions, recurring bug categories,
and tooling preferences. That re-discovery burns context and produces
generic, off-style code.

Phase 07's mission line:

> Implement a private local user profile builder that can analyze the
> last six months of Jeremiah's GitHub activity to learn coding style,
> recurring mistakes, preferred patterns, repo habits, commit style,
> and validation gaps.

This module is the implementation.

## What "private and local" means

- Output files live under `.hermes-profile/` inside the target repo.
- `.gitignore` is updated automatically so the artifacts do not get
  committed by accident.
- No file *contents* are uploaded anywhere. The only network calls
  are the user's own machine talking directly to GitHub via either
  `gh` or the REST API.
- Tokens are read from env (`GITHUB_TOKEN` / `GH_TOKEN` /
  `HERMES_GITHUB_TOKEN`) at call time and never persisted.
- Anything that pattern-matches a credential format in commit text
  is redacted to `[REDACTED]` before being written to a profile file.

## The approval gate

`hermes_cli.user_profile_builder.write_profile(..., approved=False)`
raises `ApprovalRequired`. The CLI front-end requires `--approve`
before it will write anything to disk. Without it, the CLI prints a
preview and exits.

This is the codification of the Phase 07 rule:

> Do not collect data silently. This must require explicit user
> approval.

Assistants invoking this skill are required to ask the user before
passing `--approve`.

## Data sources

The builder cascades through three sources, in order, falling back
silently if a source isn't available. Every source it actually
*used* is recorded in `snapshot.sources_used`.

1. **Local git** — `git log --since=<6mo> --numstat --pretty=...`
   parsed into structured records. Always tried when `git` is on
   PATH.
2. **GitHub CLI (`gh`)** — `gh search prs/issues` with the user's
   login. Used when `gh auth status` succeeds.
3. **GitHub REST API** — direct `urllib` request with `GITHUB_TOKEN`,
   only when `gh` isn't available.

PR file contents are never fetched. Only metadata (title, body,
labels, additions/deletions, changed file count) is collected.

## Time window

- Default: **183 days** (the six-month constant lives in
  `hermes_cli.github_history.DEFAULT_WINDOW_DAYS`).
- Override with `--since <days>` on the CLI or `window_days=` on the
  function call.

## Output files

| File | What's inside |
| --- | --- |
| `user-profile.md` | Top-level human summary. Section headers exactly match the Phase 07 spec. |
| `coding-style.md` | Language rank by commit count; subject-length stats; most-touched files. |
| `common-mistakes.md` | Recurring bug categories detected via regex on commit + PR + issue text. |
| `preferred-stack.md` | Languages, repos in rotation, frequent PR labels. |
| `validation-preferences.md` | Test/docs touch ratios; explicit checklist for "safe" PRs. |
| `github-history-summary.json` | The raw rollup. Useful for downstream tools. |

If `--include-snapshot` is passed, the full per-commit/per-PR list
is also written to `snapshot.json`. This is **off by default** —
the JSON summary is the canonical machine-readable output.

## Profile sections (mapping to spec)

The `user-profile.md` template covers every Phase 07 section:

- Preferred languages/frameworks
- Repeated project types
- Commit message style
- PR style
- Common bug categories
- Testing habits
- Documentation habits
- Mobile/Termux preferences
- AI-agent workflow preferences
- Mistakes M.U.S.E. should watch for
- Plain-English notes for future assistants

The exact wording for each section is held in
`templates/profile/user-profile.md` for review and customization.

## How assistants should use the profile

When a M.U.S.E. session starts in a repo that contains a
`.hermes-profile/` directory:

1. Read `user-profile.md` first. It's deliberately short and
   plain-English.
2. If the task touches an area covered by `common-mistakes.md`,
   read that file before editing.
3. Treat `validation-preferences.md` as a hard checklist for the PR
   you're about to open.
4. Don't quote the JSON file unless the user asks — it's for tools,
   not prose.

Assistants should **not** silently re-run the builder. If the
profile feels stale, ask the user to re-run it.

## Re-running and rotation

- The builder is idempotent — re-running overwrites the same files.
- `.gitignore` mutation only happens once (the line is added if
  missing, never duplicated).
- For a multi-repo user, run it once per repo. The output is
  per-repo and intentionally local.

## Failure modes

- **No git, no `gh`, no token.** The builder produces a near-empty
  profile and the JSON's `notes` array explains why. The exit code
  is still 0 — the artifacts are a useful "I tried" record.
- **Rate-limited API.** Search endpoints return empty; the
  `sources_used` list won't include `github-api`. Re-run later.
- **Repo isn't a git checkout.** `collect_local_commits` returns an
  empty list. The PR/issue sources still work if `--user` is set.

## Tests

`tests/test_user_profile_builder.py` exercises:

- The six-month default window math.
- The redactor (`redact_secrets`) on tokens, AWS keys, PEM blocks.
- The renderers, by handing them a synthetic `HistorySnapshot` and
  inspecting the produced Markdown.
- The approval gate (`write_profile` refuses without `approved=True`).
- The `.gitignore` mutator (idempotent, adds the line once).
- The CLI's preview mode (no disk writes when `--approve` is absent).

Run them with:

```bash
python -m pytest tests/test_user_profile_builder.py -q
```
