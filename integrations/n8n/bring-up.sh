#!/usr/bin/env bash
# bring-up.sh — one-command MUSE↔n8n bring-up. Run in WSL2 (where Docker lives).
#   cd integrations/n8n && ./bring-up.sh
# Idempotent: safe to re-run. Does NOT start the cockpit (run `muse omni` for that).
set -euo pipefail
cd "$(dirname "$0")"

gen(){ openssl rand -hex 24; }

# 1) .env with fresh secrets (only on first run)
if [ ! -f .env ]; then
  echo "→ generating .env with fresh secrets"
  cp .env.example .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen)|" .env
  sed -i "s|^N8N_ENCRYPTION_KEY=.*|N8N_ENCRYPTION_KEY=$(gen)|" .env
  sed -i "s|^N8N_USER_MANAGEMENT_JWT_SECRET=.*|N8N_USER_MANAGEMENT_JWT_SECRET=$(gen)|" .env
  echo "  ⚠ back up N8N_ENCRYPTION_KEY (losing it makes saved credentials unreadable)"
else
  echo "→ .env exists — leaving it untouched"
fi

# 2) stage workflows where the n8n container can read them (./local-files -> /files)
mkdir -p local-files/workflows
cp workflows/*.json local-files/workflows/

# 3) up
echo "→ docker compose up -d"
docker compose up -d
echo "→ waiting for n8n /healthz ..."
for i in $(seq 1 60); do
  curl -fsS http://localhost:5678/healthz >/dev/null 2>&1 && { echo "  n8n healthy"; break; }
  sleep 2
done

# 4) import + activate via n8n CLI — no API key, no OS file-picker needed
echo "→ importing workflows (n8n CLI)"
docker compose exec -T n8n n8n import:workflow --separate --input=/files/workflows \
  || echo "  note: if this failed, open http://localhost:5678 once to create the owner account, then re-run"
echo "→ activating workflows"
docker compose exec -T n8n n8n update:workflow --all --active=true || true

# 5) echo smoke test (needs the MUSE Echo Test workflow active)
echo "→ echo round-trip smoke test"
python3 muse_n8n_bridge.py http://localhost:5678 || true

cat <<'NEXT'

── n8n side is up ─────────────────────────────────────────────
Next (cockpit + token):
  1) muse omni                      # starts cockpit :8765, prints the bearer token
  2) put that token in .env:        MUSE_COCKPIT_TOKEN=<token>
  3) docker compose up -d           # re-loads env into the n8n container
  4) test inbound:  curl -s -X POST http://localhost:5678/webhook/muse-run \
                       -H 'Content-Type: application/json' -d '{"prompt":"status?"}'
Open http://localhost:5678 to see the 4 imported workflows.
───────────────────────────────────────────────────────────────
NEXT
