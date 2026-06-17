#!/usr/bin/env bash
# ============================================================================
# NEXUS — one-command Vercel deploy.
#
#   VERCEL_TOKEN=xxxxx ./deploy.sh           # production deploy
#   VERCEL_TOKEN=xxxxx ./deploy.sh --preview # preview deploy
#
# Get a token at https://vercel.com/account/tokens (or paste it in the app's
# Settings → Connections & Credentials → Vercel, then export it here).
# First run auto-creates the Vercel project (framework Vite, root = this dir).
# ============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PROD="--prod"
[ "${1:-}" = "--preview" ] && PROD=""

if [ -z "${VERCEL_TOKEN:-}" ]; then
  echo "✗ VERCEL_TOKEN is not set."
  echo "  → Create one at https://vercel.com/account/tokens"
  echo "  → Then:  VERCEL_TOKEN=xxxxx ./deploy.sh"
  exit 1
fi

echo "▸ Building…"
npm ci --no-audit --no-fund
npm run build

echo "▸ Deploying to Vercel${PROD:+ (production)}…"
# --yes auto-confirms project creation; Vite is auto-detected; dist is output.
URL="$(npx --yes vercel deploy $PROD --yes --token "$VERCEL_TOKEN" --cwd "$HERE")"
echo "✓ Live at: $URL"
