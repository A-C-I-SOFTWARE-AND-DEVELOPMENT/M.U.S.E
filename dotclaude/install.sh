#!/usr/bin/env bash
# Hermes / AOS / Nourish global install for Claude Code.
#
# Installs the contents of this dotclaude/ directory into ~/.claude/.
# Backs up any existing files first into ~/.claude/backups/pre-hermes-<TS>/.
#
# Usage (from anywhere):
#   bash /path/to/hermes-agent/dotclaude/install.sh
#
# Idempotent: re-runs back up the current state and overwrite with the
# tree shipped in this repo. Customizations belong in ~/.claude/local/
# (which is never touched by this installer).

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_HOME:-$HOME/.claude}"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="$DEST/backups/pre-hermes-$TS"

echo "Hermes global install"
echo "  source: $SRC_DIR"
echo "  target: $DEST"
echo "  backup: $BACKUP"
echo

mkdir -p "$DEST" "$BACKUP"

# Back up anything that already exists at the targets we will write.
for p in CLAUDE.md agents skills commands hermes rules; do
  if [ -e "$DEST/$p" ]; then
    echo "  backing up: $p"
    cp -a "$DEST/$p" "$BACKUP/" 2>/dev/null || true
  fi
done

# Install. We do NOT delete existing per-skill / per-agent files outside
# the Hermes-named ones — owners may have local additions. We overwrite
# only the files this installer ships.
mkdir -p "$DEST/agents" "$DEST/skills" "$DEST/commands" "$DEST/hermes" "$DEST/rules"

# CLAUDE.md: if one exists and does not already reference HERMES_GLOBAL.md,
# append a Hermes import block at the end. Otherwise install ours fresh.
if [ -f "$DEST/CLAUDE.md" ]; then
  if grep -q "HERMES_GLOBAL.md" "$DEST/CLAUDE.md"; then
    echo "  CLAUDE.md already references HERMES_GLOBAL.md — leaving as-is"
  else
    echo "  CLAUDE.md exists — appending Hermes import block"
    {
      echo
      echo "## Hermes operating layer (appended by Hermes installer $TS)"
      echo
      echo "@~/.claude/hermes/HERMES_GLOBAL.md"
      echo
      echo "See ~/.claude/hermes/HERMES_GLOBAL.md for the full operating contract."
    } >> "$DEST/CLAUDE.md"
  fi
else
  echo "  installing fresh CLAUDE.md"
  cp "$SRC_DIR/CLAUDE.md" "$DEST/CLAUDE.md"
fi

# hermes/HERMES_GLOBAL.md always installed
cp "$SRC_DIR/hermes/HERMES_GLOBAL.md" "$DEST/hermes/HERMES_GLOBAL.md"
echo "  installed: hermes/HERMES_GLOBAL.md"

# Agents
for f in "$SRC_DIR/agents/"*.md; do
  name="$(basename "$f")"
  cp "$f" "$DEST/agents/$name"
  echo "  installed: agents/$name"
done

# Skills (each is a folder containing SKILL.md)
for d in "$SRC_DIR/skills/"*/; do
  name="$(basename "$d")"
  mkdir -p "$DEST/skills/$name"
  cp "$d/SKILL.md" "$DEST/skills/$name/SKILL.md"
  echo "  installed: skills/$name/SKILL.md"
done

# Commands
for f in "$SRC_DIR/commands/"*.md; do
  name="$(basename "$f")"
  cp "$f" "$DEST/commands/$name"
  echo "  installed: commands/$name"
done

# Rules
for f in "$SRC_DIR/rules/"*.md; do
  name="$(basename "$f")"
  cp "$f" "$DEST/rules/$name"
  echo "  installed: rules/$name"
done

echo
echo "Done."
echo
echo "Verify with:"
echo "  ls -R \"$DEST\" | head -200"
echo
echo "In a new Claude Code session:"
echo "  /agents            # should list the 15 Hermes agents"
echo "  /hermes-audit      # should be recognized as a slash command"
echo
echo "Backup: $BACKUP"
