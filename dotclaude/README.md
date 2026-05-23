# Hermes / AOS / Nourish — global Claude Code install

This directory is the source of truth for the global Hermes operating layer
that lives in `~/.claude/` on a developer machine.

It is **not** picked up automatically by anything in this repo. It is meant
to be installed once on each machine where you run Claude Code.

## Install

```bash
bash dotclaude/install.sh
```

The installer:

- Backs up any existing `~/.claude/CLAUDE.md`, `agents/`, `skills/`,
  `commands/`, `hermes/`, `rules/` into
  `~/.claude/backups/pre-hermes-<timestamp>/`.
- Writes the tree from `dotclaude/` into `~/.claude/`.
- If `~/.claude/CLAUDE.md` already exists and does not import the Hermes
  layer, appends an `@~/.claude/hermes/HERMES_GLOBAL.md` import to it
  rather than overwriting.
- Is idempotent — re-running backs up the current state and overwrites
  with the version shipped in this repo.

## What gets installed

- `~/.claude/CLAUDE.md` — global memory entry point, imports the Hermes
  layer.
- `~/.claude/hermes/HERMES_GLOBAL.md` — authoritative Hermes operating
  contract.
- `~/.claude/agents/*.md` — 15 specialist subagents.
- `~/.claude/skills/<name>/SKILL.md` — 14 procedural skills.
- `~/.claude/commands/*.md` — 7 slash commands.
- `~/.claude/rules/*.md` — 5 hard rules referenced by the operating layer.

## Verify

```bash
ls -R ~/.claude | head -200
```

In a Claude Code session:

- `/agents` should list the 15 Hermes agents.
- `/hermes-audit`, `/hermes-build-plan`, `/hermes-launch-check`,
  `/hermes-master-prompt`, `/nourish-audit`, `/aos-audit`,
  `/codex-claude-sync` should be available as slash commands.

## Updating

Pull the latest of this repo, then re-run `bash dotclaude/install.sh`.
Your previous tree is backed up under
`~/.claude/backups/pre-hermes-<timestamp>/` each time.

## Customization

Put machine-local customizations in `~/.claude/local/` (a directory this
installer never touches). Reference them from your `~/.claude/CLAUDE.md`
with `@~/.claude/local/<file>.md` if you want them imported globally.
