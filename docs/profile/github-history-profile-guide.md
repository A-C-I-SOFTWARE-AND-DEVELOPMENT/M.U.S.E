# GitHub history profile guide

M.U.S.E. builds a **persistent profile** of how you work over time —
your repositories, your typical PR patterns, the projects you care
about, your usual reviewers. The richest input to that profile is
your GitHub history.

This guide explains what the profile is, what data it pulls,
where it's stored, what it does with it, and how to control it.

---

## What "profile" means here

Two unrelated senses, disambiguated:

- **Worker profile.** A YAML configuration that defines a worker
  (model + tools + skills + environment). See
  [orchestration/worker-adapters.md](../orchestration/worker-adapters.md).
- **User profile.** A persistent model of you, the human, built from
  memory + session history + (optionally) your GitHub history. This
  page is about the user-profile sense.

When this guide says "profile" without qualification it means **user
profile**.

---

## What the profile contains

The user profile is a small structured store under
`~/.hermes/memory/` (default SQLite) plus an optional cache of
GitHub-derived facts at `~/.hermes/profile/github/`. It includes:

| Field | Where it comes from |
|-------|---------------------|
| GitHub username | You tell M.U.S.E. once, or `github_assistant` derives it from your PAT. |
| Repositories you own / collaborate on | `GET /user/repos` via `github_assistant`. |
| Languages you write | Aggregated from repo `language` fields and the orchestrator's observations. |
| Repos you've worked on recently | From `GET /users/{user}/events` + your job history. |
| PR patterns (typical title format, commit style, draft-first?) | Derived from your last N PRs. |
| Usual reviewers / co-authors | From PR history. |
| Repos you starred or watched | Stars + watch list. |
| Issue patterns (open vs assigned, labels you use) | From issues you've opened. |
| Preferred branch naming | From past branches. |
| Memories you've stated explicitly | E.g. *"Remember: I always open PRs as drafts."* |

The profile is **a curated cache, not a copy of GitHub**. It stores
facts derived from your history, with timestamps and rationale; the
raw events live on GitHub.

---

## Where the data lives

- **The memory backend** (`~/.hermes/memory/*.db` by default, or your
  configured Honcho / Mem0 / Supermemory backend) holds structured
  facts ("Jeremiah's GitHub username is `echerd27`", "Jeremiah
  prefers draft PRs", etc.).
- **The profile cache** (`~/.hermes/profile/github/`) holds the
  raw-ish aggregates used to derive facts: repo lists, recent PR
  summaries, label histograms.
- **The sessions DB** (`~/.hermes/sessions.db`) holds the
  conversations the profile was learned from.

The agent does **not** see raw API responses by default — the
`github_assistant` plugin runs the queries, aggregates them, and
hands the agent the summaries it needs. Raw bytes stay in the
profile cache.

---

## How the profile gets built

Three loops, all running quietly when you ask M.U.S.E. to do GitHub
work.

### 1. Initial backfill

The first time you run a GitHub-touching workflow (or explicitly
`/profile sync github`), M.U.S.E.:

1. Lists your accessible repos.
2. Pulls the most recent N (default 25) PRs and their reviewers,
   labels, statuses.
3. Pulls the most recent N issues you've opened or been assigned to.
4. Aggregates the above into the profile cache.
5. Writes derived facts to memory ("most-touched repo: X", "default
   branch convention: Y", etc.).

You can see what it derived:

```bash
muse profile show github
```

```
GitHub profile for echerd27 (synced 5m ago)
├── Repos (12 owned, 87 collab)
│   most recent activity: echerd27-design/hermes-agent (today)
│   primary languages:    Python (62%), Kotlin (14%), TypeScript (12%)
├── PR style
│   default draft:        true   (24/25 recent PRs were drafts)
│   title convention:     conventional commits (chore:, feat:, fix:)
│   typical reviewers:    @aaronwong1999, @avifenesh
├── Issue patterns
│   labels you open with: bug (40%), enhancement (35%), question (10%)
└── Branches
    naming convention:    {scope}/{kebab-name}
```

### 2. Ambient updates

While you work, the agent observes:

- Which repos you point it at.
- Which prompts mention "open a PR" vs "open an issue" vs "comment".
- Whether you approve or override its suggestions.

These become small profile updates over time. The curator
(`enterprise/monitor.py`) accepts or discards proposed updates, so
the profile doesn't drift on a single bad observation.

### 3. Scheduled refresh

If you've enabled the AI radar or a profile-refresh cron job, the
profile re-syncs from GitHub on schedule (default: weekly). You can
trigger manually with `/profile sync github` or
`muse profile sync github`.

---

## What M.U.S.E. does with the profile

The profile is **input** to the orchestrator and the worker skills.
Concretely:

- **Default branch / repo guesses.** When you say *"open a PR with
  the cleanup,"* the orchestrator uses the profile to pick a sensible
  default branch name and target repo. It still asks for approval —
  the profile just makes the suggestion better.
- **Reviewer suggestions.** When the publishing phase opens a PR, it
  suggests reviewers from your usual list (you approve / change).
- **Style matching.** When the worker writes a PR title or commit
  message, it tries to match your existing convention.
- **Skill loading.** If the profile knows you work mostly in Python,
  the orchestrator preloads Python-relevant skills first.
- **Routing.** If the profile knows you've capped certain repos
  for "drafts only," the orchestrator routes those phases to a
  draft-only publishing config.

If you'd rather M.U.S.E. ignore the profile and ask you every time,
disable it (see [Controls](#controls) below).

---

## Setup

### 1. Enable `github_assistant`

The profile pulls from GitHub via the `github_assistant` plugin.
See [`../github-integration.md`](../github-integration.md) and
[`../integrations/github-supabase-vercel-guide.md`](../integrations/github-supabase-vercel-guide.md)
for the canonical setup. You need a fine-grained PAT scoped to the
repositories you want M.U.S.E. to know about.

```bash
muse plugin enable github_assistant
muse config set github.allowed_repositories "owner1/repo1,owner2/repo2"
# Or grant access to all of your repos:
muse config set github.allowed_repositories "@me"
echo "GITHUB_PERSONAL_ACCESS_TOKEN=ghp_..." >> ~/.hermes/.env
```

### 2. Trigger the initial sync

```bash
muse profile sync github
```

The first sync can take a minute on large accounts; it streams
progress.

### 3. Confirm

```bash
muse profile show github
```

You should see the structured summary shown above.

---

## Controls

### Pause profile updates

```bash
muse profile pause github
```

The cache stays; ambient updates stop. Resume with
`muse profile resume github`.

### Wipe the profile

```bash
muse profile wipe github                # interactive confirm
muse profile wipe github --yes          # no confirm
```

Deletes `~/.hermes/profile/github/` and removes GitHub-derived facts
from memory. The next time you do GitHub work, M.U.S.E. will rebuild
from scratch unless paused.

### Restrict scope

By default M.U.S.E. pulls history only for repositories in
`github.allowed_repositories`. To exclude specific ones:

```yaml
profile:
  github:
    excluded_repositories:
      - personal/private-journal
      - work/sensitive-internal
```

### Turn it off entirely

```yaml
profile:
  github:
    enabled: false
```

M.U.S.E. still uses `github_assistant` for live work (PRs, issues,
comments). It just won't aggregate history into the profile.

### Disable ambient updates only

```yaml
profile:
  github:
    enabled: true
    ambient_updates: false   # only manual `/profile sync github`
```

---

## How the profile interacts with memory

The profile **publishes facts to memory** so the rest of the agent
can use them naturally. Example: after the initial sync, you'll see
memories like:

```
- "Jeremiah's GitHub username is echerd27." (source: profile.github)
- "Jeremiah opens 96% of PRs as drafts." (source: profile.github)
- "Jeremiah's most recently active repo is echerd27-design/hermes-agent." (source: profile.github)
```

These appear in `muse memory list` like any other memory. Editing
or deleting them is fine — the next profile sync will repropose
them, but the curator will respect a deletion if it understands you
explicitly removed it.

Override behavior: if you state a contradicting memory directly
("Remember: I do not use draft PRs anymore"), the curator records
the user-stated memory with higher precedence than the
profile-derived one.

---

## How the profile interacts with orchestration

When the orchestrator decomposes a goal like *"Audit my-repo and
open a draft PR"*:

1. It reads the profile to get your draft-default, conventional-commit
   style, and reviewer list.
2. The decomposition includes a publishing phase whose body says
   *"open a draft PR titled `chore(audit): ...`, request review from
   `@aaron`, `@avi`."*
3. You still approve the publishing phase — the profile only makes
   the proposal better. Profile-derived defaults appear in the
   approval preview with the source tag `[profile]` so you know
   which fields came from history.

The orchestrator never *acts* directly on profile data — it always
goes through the same gates as a stranger's prompt would.

---

## Prompt examples

| You say | What the profile contributes |
|---------|------------------------------|
| *"Open a PR on the auth refactor."* | Defaults branch name from your convention, defaults draft to true. |
| *"Who usually reviews my Python changes?"* | Reads from the recorded reviewer histogram. |
| *"What did I ship last week?"* | Reads from the recent-PR cache; no live GitHub call needed. |
| *"Find similar PRs I've opened before."* | Searches the cache for PRs touching the same paths. |
| *"Use my preferred PR style."* | Pulls the conventional-commits pattern and your usual labels. |

Prompts you might want to use *against* the profile:

| You say | Effect |
|---------|--------|
| *"Don't draft this one."* | One-shot override; profile default for next PR is unchanged. |
| *"Forget what you know about my GitHub history."* | Wipes the cache (with confirmation). |
| *"Don't suggest reviewers from history."* | Disables the reviewer-suggestion field for the session. |

---

## Privacy

- **The profile is local.** Cache lives under `~/.hermes/profile/`.
  Nothing leaves that folder unless you've configured a cloud memory
  backend (Honcho / Mem0 / Supermemory) — and even then only the
  derived facts go, not the raw history.
- **Your PAT never leaves the gateway.** Tokens live in
  `~/.hermes/.env` and are read by the `github_assistant` plugin
  inside the same process; they are not sent to model providers,
  not logged in the ledger, not synced into memory.
- **Wipe is a real wipe.** `muse profile wipe github` deletes the
  cache and removes profile-sourced memories. The
  `~/.hermes/memory/*.db` file no longer contains them.

For the full lockdown, see
[../security/private-local-security-guide.md](../security/private-local-security-guide.md).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `profile show github` says "no data yet" | Initial sync never ran | `muse profile sync github`. |
| Sync errors with 401/403 | PAT scope insufficient | Regenerate PAT with `repo:read` (or `repo` if you also want write); update `~/.hermes/.env`. |
| Sync errors with 404 on a specific repo | Repo removed or you lost access | Edit `github.allowed_repositories` to drop it; re-sync. |
| Profile suggests the wrong default branch | Convention changed recently | `muse profile sync github` to refresh; then `muse memory update <fact-id>` if needed. |
| Reviewer suggestions feel stale | Your team changed | Re-sync; consider lowering `profile.github.history_window` to last 30 days. |
| You see a memory you didn't expect | Auto-derived from ambient observation | `muse memory rm <id>`; the curator respects deletions. |
| Sync is slow | Account has hundreds of repos | Set `profile.github.history_window` smaller; or limit `github.allowed_repositories`. |

Anything else: see
[../troubleshooting/hermes-orchestration-troubleshooting.md](../troubleshooting/hermes-orchestration-troubleshooting.md).

---

## See also

- [`../github-integration.md`](../github-integration.md) — the
  `github_assistant` plugin itself.
- [`../integrations/github-supabase-vercel-guide.md`](../integrations/github-supabase-vercel-guide.md)
  — wiring up GitHub end-to-end.
- [`../security/private-local-security-guide.md`](../security/private-local-security-guide.md)
  — keeping the profile fully on-device.
- [`../orchestration/getting-started.md`](../orchestration/getting-started.md)
  — how the profile feeds into orchestration.
