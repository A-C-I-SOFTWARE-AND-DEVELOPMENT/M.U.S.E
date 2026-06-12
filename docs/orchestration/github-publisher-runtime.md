# GitHub publisher runtime

The GitHub publisher is the executable counterpart to the
`github-pr-workflow` skill. The skill is a prose checklist; this module
is the code that runs the checklist for an agent — locally, with the
operator in the loop for anything that touches the network.

Source: [`hermes_cli/github_publisher.py`](../../hermes_cli/github_publisher.py).
Tests: [`tests/test_github_publisher.py`](../../tests/test_github_publisher.py).

## Goals

- Reduce a publish to a *previewable plan* that the operator can read
  before any push happens.
- Make the unsafe paths (force-push, merge, branch reuse, secret
  commits) structurally impossible, not just discouraged.
- Work the same whether the `gh` CLI is installed or not.
- Leave a paper trail (the six artifact files) so the operator can
  re-run, audit, or roll back without re-deriving anything.

## Surface

Top-level entry point:

```python
from hermes_cli.github_publisher import run

result = run(
    job_id="kanban-2026-05-23-001",
    files=["src/foo.py", "tests/test_foo.py"],
    commit_message="feat(foo): add bar\n\nFixes #123",
    pr_summary="Adds a bar to foo.",
    pr_changes=["Add bar() to foo", "Cover bar() with a unit test"],
    pr_test_plan=["pytest tests/test_foo.py", "manual smoke against staging"],
    approve=False,  # default — produces a plan, does not push
)
```

`approve=False` (the default) writes the artifact files into
`<repo_root>/github/` and stops. `approve=True` additionally:

1. creates the branch `hermes/job-<slug>`,
2. stages the listed files (after a secret scan),
3. commits with the supplied message,
4. pushes the new branch to `origin`.

`gh pr create` is *never* invoked from inside `run()` even with
`approve=True`. The exact argv is emitted into `publish-plan.md` and as
`PublishResult.plan.pr_create_command`; opening the PR is the operator's
call.

### Lower-level helpers

The orchestration entry point wraps these — they're public so the
agent can call them piecemeal when it needs to:

| Function | Purpose |
| --- | --- |
| `get_repo_info(repo_root)` | Resolves repo root, parses `origin` into `owner/repo`, detects default branch. |
| `get_current_branch(repo_root)` | Returns the current branch name, or `None` for detached HEAD. |
| `get_status(repo_root)` | Structured `git status --porcelain` (staged / unstaged / untracked). |
| `create_branch(job_id, dry_run=...)` | Computes (or creates) `hermes/job-<slug>`. |
| `stage_files(files, dry_run=...)` | Secret-scans, then `git add`s (or just returns the list in dry-run). |
| `commit(message, dry_run=...)` | `git commit -m <message>`. Never amends, never bypasses hooks. |
| `prepare_pr_body(job_id, ...)` | Renders the standard PR body markdown. |
| `gh_available()` | `True` iff `gh` is on PATH. |
| `build_gh_pr_create_command(...)` | Returns the argv list for `gh pr create` (always `--draft`). |
| `scan_for_secrets(files, repo_root=...)` | Returns `{path: reason}` for blocked files. |
| `write_publish_artifacts(plan, ...)` | Writes the six artifact files. |

## Safety properties

These are enforced at the module level — there is no caller-supplied
escape hatch:

1. **Branch-per-job.** `create_branch` always uses
   `git checkout -b <name>`, which fails if the branch already exists.
   Re-running a publish for the same `job_id` either re-uses the
   already-checked-out branch (caller's choice) or refuses — it cannot
   silently overwrite.
2. **No force-push.** The push command is fixed at
   `git push -u origin <branch>`. There's no `--force` parameter
   anywhere in this module.
3. **No merge / no destructive cleanup.** The module never runs
   `git merge`, `git reset --hard`, `git clean`, or any `--delete`
   variant. Rolling a publish back is explicitly the operator's job
   and the steps appear in `publish-plan.md`.
4. **`.env` and friends are refused.** A short blocklist of filenames
   (`.env`, `.env.*`, `id_rsa`, `*.pem`, `*.key`, `credentials.json`,
   etc.) and path fragments (`secrets/`, `private_keys/`) is enforced
   before any `git add`.
5. **Content secret scan.** Files smaller than 2 MiB are scanned for
   GitHub PATs, AWS access keys, Slack bot tokens, Google API keys,
   OpenAI / Anthropic keys, and PEM `BEGIN PRIVATE KEY` blocks. A hit
   aborts the entire batch — staging is atomic.
6. **PR opens are operator-driven.** Even with `approve=True`, the
   `gh pr create` command is printed, not executed. A human always
   ratifies the publish.

The full list of blocklisted basenames, suffixes, and content patterns
lives at the top of `hermes_cli/github_publisher.py` and is exercised
by `tests/test_github_publisher.py`.

## Outputs

Every run writes six files into the output directory (default
`<repo_root>/github/`):

| File | Contents |
| --- | --- |
| `branch.txt` | The branch name, one line. |
| `commit-message.txt` | The commit message, exactly as it will be passed to `git commit`. |
| `pr-title.txt` | One line, the PR title. |
| `pr-body.md` | Full PR body markdown — summary, changes, test plan, provenance. |
| `publish-plan.md` | Human-readable preview: repo, branch, files, the exact shell commands, and rollback instructions. |
| `publish-status.json` | Machine-readable status: did we execute, did we push, error list, timestamps, repo metadata. |

`publish-status.json` is the file the orchestrator polls — it's the
"ground truth" for whether a publish succeeded.

## `gh` missing fallback

If `gh` is not on `PATH`, `gh_available()` returns `False` and
`plan.pr_create_command` is `None`. The push command is unchanged
(plain `git push`). `publish-plan.md` notes that the PR has to be
opened manually and points at `pr-title.txt` / `pr-body.md` as the
inputs.

If `gh` is present but the remote isn't a GitHub URL (e.g., GitLab,
self-hosted Git, no remote at all) the PR command is also `None`.

## Rollback

The publish-plan emits these by default:

```bash
# remove the freshly-pushed remote branch (only the new one, never main)
git push origin --delete hermes/job-<slug>

# go back to the prior branch and drop the local copy once you've
# confirmed nothing depends on it
git checkout -
git branch -D hermes/job-<slug>
```

There is intentionally no module-level "rollback" function. The
operator runs the commands.

## Integration with the orchestrator

The local orchestrator (`docs/muse-local-orchestrator.md`) calls
`run(...)` with `approve=False` to attach a plan to a kanban card.
Reviewers see the artifacts in `github/`, sign off, and the
orchestrator re-runs with `approve=True`. The `publish-status.json`
delta is what flips the card from "publish-ready" to "pushed".
