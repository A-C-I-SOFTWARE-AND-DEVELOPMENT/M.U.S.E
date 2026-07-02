#!/usr/bin/env bash
# provision_user.sh — stand up (or tear down) ONE hosted muse cockpit container
# for a Pro user on the fleet VPS, and bind it to their account so the public
# cockpit's relay can reach it.
#
# This is an OWNER-GATED operation: it spends compute and creates a credential
# (the gateway token) + a Supabase row. Run it by hand per Pro signup; the
# happy-path automation (Supabase webhook -> provisioner) is intentionally left
# as a later step (documented in docs/deploy/hosted-fleet.md) so a human stays
# in the loop while the fleet is small.
#
# Usage:
#   scripts/fleet/provision_user.sh up   <slug> <supabase_user_id> [pub_port]
#   scripts/fleet/provision_user.sh down <slug>
#
# Env (required for `up` to write the account binding):
#   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   (service-role — never the anon key)
#   GW_DOMAIN                                 e.g. gw.musehq.io
# Optional:
#   MUSE_MEM_LIMIT (2g), MUSE_CPUS (1.5)
set -euo pipefail

ACTION="${1:-}"
SLUG="${2:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.hosted.yml"

die() { echo "error: $*" >&2; exit 1; }

[ -n "$ACTION" ] || die "usage: provision_user.sh {up|down} <slug> [args]"
[ -n "$SLUG" ] || die "a user slug is required"
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]{1,38}$ ]] || die "slug must be [a-z0-9-], 2-39 chars"

PROJECT="muse-${SLUG}"

case "$ACTION" in
  up)
    USER_ID="${3:-}"
    PUB_PORT="${4:-}"
    [ -n "$USER_ID" ] || die "up requires <supabase_user_id>"
    if [ -z "$PUB_PORT" ]; then
      # Deterministic port in a private range from the slug hash (8800-9799).
      PUB_PORT=$(( 8800 + $(printf '%s' "$SLUG" | cksum | cut -d' ' -f1) % 1000 ))
    fi
    GW_DOMAIN="${GW_DOMAIN:?set GW_DOMAIN, e.g. gw.musehq.io}"

    echo "==> Bringing up ${PROJECT} on 127.0.0.1:${PUB_PORT}"
    USER_SLUG="$SLUG" PUB_PORT="$PUB_PORT" \
      docker compose -p "$PROJECT" -f "$COMPOSE_FILE" up -d --build

    echo "==> Waiting for the cockpit to become healthy"
    for _ in $(seq 1 60); do
      if curl -fsS "http://127.0.0.1:${PUB_PORT}/v1/health" >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
    HEALTH="$(curl -fsS "http://127.0.0.1:${PUB_PORT}/v1/health" || true)"
    echo "    health: ${HEALTH:-<unreachable>}"
    case "$HEALTH" in
      *'"agent":"full"'*) : ;;
      *) die "cockpit did not come up in full-agent mode (check container logs: docker compose -p ${PROJECT} logs)";;
    esac

    echo "==> Reading the container's cockpit token"
    TOKEN="$(docker compose -p "$PROJECT" -f "$COMPOSE_FILE" exec -T cockpit muse cockpit token | tr -d '\r\n')"
    [ -n "$TOKEN" ] || die "could not read cockpit token from the container"

    GATEWAY_URL="https://${GW_DOMAIN}/u/${SLUG}"
    echo "==> Binding ${GATEWAY_URL} to Supabase user ${USER_ID}"
    : "${SUPABASE_URL:?set SUPABASE_URL}"
    : "${SUPABASE_SERVICE_ROLE_KEY:?set SUPABASE_SERVICE_ROLE_KEY}"
    HTTP_CODE=$(curl -sS -o /dev/null -w '%{http_code}' \
      -X POST "${SUPABASE_URL%/}/rest/v1/account_gateways" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Content-Type: application/json" \
      -H "Prefer: resolution=merge-duplicates,return=minimal" \
      -d "$(printf '{"user_id":"%s","gateway_url":"%s","gateway_token":"%s"}' "$USER_ID" "$GATEWAY_URL" "$TOKEN")")
    case "$HTTP_CODE" in
      2*) echo "    binding stored (HTTP ${HTTP_CODE})";;
      *)  die "failed to store account binding (HTTP ${HTTP_CODE})";;
    esac

    cat <<EOF

==> Provisioned '${SLUG}'.
    Add this route to deploy/hosted/Caddyfile (between the managed markers) and
    reload Caddy:

    handle_path /u/${SLUG}/* {
        reverse_proxy 127.0.0.1:${PUB_PORT} {
            flush_interval -1
        }
    }

    Then set a provider key in the container's ~/.hermes/.env if you haven't:
      docker compose -p ${PROJECT} -f docker-compose.hosted.yml exec cockpit \\
        sh -c 'echo "GROQ_API_KEY=..." >> /opt/data/.env'
EOF
    ;;

  down)
    echo "==> Tearing down ${PROJECT} (container + volume)"
    docker compose -p "$PROJECT" -f "$COMPOSE_FILE" down -v || true
    echo "    Remember to remove the /u/${SLUG}/ route from deploy/hosted/Caddyfile,"
    echo "    reload Caddy, and clear the account_gateways row for this user."
    ;;

  *)
    die "unknown action '$ACTION' (expected up|down)"
    ;;
esac
