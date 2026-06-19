#!/usr/bin/env bash
# ============================================================================
# nexus-up.sh — bring up the full MUSE NEXUS console at a clickable URL.
# ============================================================================
# Runs the MUSE cockpit (which serves the NEXUS PWA *same-origin* at /nexus/ —
# no CORS, no mixed-content) and exposes it publicly, then prints the URL + the
# pairing token you paste into the ConnectWizard. One command, end to end.
#
# THREE modes (auto-detected; override with a flag):
#   --tunnel   (default if no domain)  Public HTTPS via a Cloudflare quick
#              tunnel — NO domain, NO DNS, NO TLS setup. Prints a
#              https://<random>.trycloudflare.com/nexus/ URL. Ephemeral.
#   --domain D Stable HTTPS on your own hostname via Caddy (auto-TLS). DNS for D
#              must point at this box. Prints https://D/nexus/.
#   --local    No public exposure — just http://127.0.0.1:8765/nexus/.
#
# Usage (run on the box that has your ~/.hermes/.env keys):
#   bash scripts/nexus-up.sh                       # quick public tunnel
#   bash scripts/nexus-up.sh --domain muse.example.com
#   bash scripts/nexus-up.sh --local
#
# It is idempotent: re-run it freely. Stop everything with --stop.
# ============================================================================
set -eo pipefail
if [ -n "${PYTHONPATH:-}" ]; then unset PYTHONPATH; fi

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
say()  { echo -e "${CYAN}→${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PORT="${MUSE_PORT:-8765}"
MODE=""                      # tunnel | domain | local
DOMAIN=""
STOP=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_DIR="$HERMES_HOME/nexus-up"; mkdir -p "$RUN_DIR" "$HERMES_HOME/logs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tunnel) MODE="tunnel"; shift ;;
    --domain) MODE="domain"; DOMAIN="$2"; shift 2 ;;
    --local)  MODE="local"; shift ;;
    --port)   PORT="$2"; shift 2 ;;
    --stop)   STOP=true; shift ;;
    -h|--help) sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) err "Unknown option: $1"; exit 1 ;;
  esac
done

resolve_muse() {
  command -v muse 2>/dev/null && return 0
  command -v hermes 2>/dev/null && return 0
  for c in /usr/local/bin/muse "$HOME/.local/bin/muse" "$REPO_DIR/venv/bin/muse"; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done; echo ""
}
MUSE_BIN="$(resolve_muse)"

stop_all() {
  say "Stopping NEXUS processes…"
  for p in cockpit cloudflared caddy; do
    if [ -f "$RUN_DIR/$p.pid" ]; then kill "$(cat "$RUN_DIR/$p.pid")" 2>/dev/null || true; rm -f "$RUN_DIR/$p.pid"; fi
  done
  ok "Stopped."
}
[ "$STOP" = true ] && { stop_all; exit 0; }

[ -n "$MUSE_BIN" ] || { err "No 'muse' command found. Install first: bash scripts/quickstart.sh"; exit 1; }
[ -z "$MODE" ] && { [ -n "$DOMAIN" ] && MODE="domain" || MODE="tunnel"; }

# ---- 1. Ensure the NEXUS PWA is built (cockpit serves apps/nexus/dist) -------
if [ ! -f "$REPO_DIR/apps/nexus/dist/index.html" ]; then
  say "Building the NEXUS PWA (one-time)…"
  ( cd "$REPO_DIR/apps/nexus" && (npm ci --no-audit --no-fund || npm install) \
      && NEXUS_NO_PWA="${NEXUS_NO_PWA:-}" npm run build )
  ok "NEXUS built → apps/nexus/dist"
else
  ok "NEXUS build present."
fi

# ---- 2. Ensure the cockpit is serving on the loopback port -------------------
cockpit_up() { curl -fsS -o /dev/null "http://127.0.0.1:$PORT/nexus/" 2>/dev/null; }
if cockpit_up; then
  ok "Cockpit already serving on 127.0.0.1:$PORT."
else
  say "Starting cockpit (muse cockpit serve --port $PORT)…"
  nohup "$MUSE_BIN" cockpit serve --port "$PORT" >"$HERMES_HOME/logs/cockpit.log" 2>&1 &
  echo $! > "$RUN_DIR/cockpit.pid"
  for _ in $(seq 1 30); do cockpit_up && break; sleep 1; done
  cockpit_up && ok "Cockpit listening on 127.0.0.1:$PORT." || { err "Cockpit did not come up — see $HERMES_HOME/logs/cockpit.log"; exit 1; }
fi

TOKEN="$("$MUSE_BIN" cockpit token 2>/dev/null | grep -oE '[A-Za-z0-9_-]{40,}' | head -1 || true)"

# ---- 3. Expose it ------------------------------------------------------------
PUBLIC_URL=""
case "$MODE" in
  local)
    PUBLIC_URL="http://127.0.0.1:$PORT"
    ;;
  domain)
    [ -n "$DOMAIN" ] || { err "--domain requires a hostname"; exit 1; }
    command -v caddy >/dev/null 2>&1 || { err "caddy not installed. See https://caddyserver.com/docs/install"; exit 1; }
    local_pages="https://a-c-i-software-and-development.github.io"
    sed -e "s|__DOMAIN__|$DOMAIN|g" -e "s|__PAGES_ORIGIN__|$local_pages|g" \
        "$REPO_DIR/deploy/cockpit-https/Caddyfile" > "$RUN_DIR/Caddyfile"
    say "Starting Caddy (auto-TLS) for $DOMAIN…"
    nohup caddy run --config "$RUN_DIR/Caddyfile" --adapter caddyfile >"$HERMES_HOME/logs/caddy.log" 2>&1 &
    echo $! > "$RUN_DIR/caddy.pid"
    PUBLIC_URL="https://$DOMAIN"
    ;;
  tunnel)
    if ! command -v cloudflared >/dev/null 2>&1; then
      say "Fetching cloudflared (single binary)…"
      arch="$(uname -m)"; case "$arch" in x86_64|amd64) a=amd64;; aarch64|arm64) a=arm64;; *) a=amd64;; esac
      mkdir -p "$HOME/.local/bin"
      curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$a" \
        -o "$HOME/.local/bin/cloudflared" && chmod +x "$HOME/.local/bin/cloudflared"
      export PATH="$HOME/.local/bin:$PATH"
    fi
    command -v cloudflared >/dev/null 2>&1 || { err "cloudflared unavailable; use --domain or --local."; exit 1; }
    say "Opening a Cloudflare quick tunnel…"
    nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$HERMES_HOME/logs/cloudflared.log" 2>&1 &
    echo $! > "$RUN_DIR/cloudflared.pid"
    for _ in $(seq 1 30); do
      PUBLIC_URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$HERMES_HOME/logs/cloudflared.log" 2>/dev/null | head -1)"
      [ -n "$PUBLIC_URL" ] && break; sleep 1
    done
    [ -n "$PUBLIC_URL" ] || { err "Tunnel URL not detected — see $HERMES_HOME/logs/cloudflared.log"; exit 1; }
    ;;
esac

# ---- 4. Report ---------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}✓ NEXUS is up.${NC}"
echo ""
echo -e "  ${BOLD}Open this:${NC}  ${CYAN}$PUBLIC_URL/nexus/${NC}"
[ -n "$TOKEN" ] && echo -e "  ${BOLD}Pairing token:${NC}  $TOKEN"
echo ""
say "In the app: ConnectWizard → it's same-origin, so just paste the token → Connect."
say "Then use Chat, Fusion, and every pipeline page live."
[ "$MODE" = "tunnel" ] && warn "Quick tunnels are ephemeral/rate-limited — use --domain <host> for a stable URL."
[ "$MODE" = "local" ]  && warn "Local only. For remote access use the default (tunnel) or --domain."
echo ""
say "Stop everything:  bash scripts/nexus-up.sh --stop"
