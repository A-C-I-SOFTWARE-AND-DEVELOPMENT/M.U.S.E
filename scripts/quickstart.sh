#!/bin/bash
# ============================================================================
# M.U.S.E. Quickstart — one top-level installer for a 24/7 deployment
# ============================================================================
# Picks the right install path for the host and brings M.U.S.E. fully online:
#   • Docker track  → `docker compose up -d` (gateway + dashboard, restart-safe,
#                     model routing bootstrapped on first boot).
#   • Native track  → scripts/install.sh --jarvis-launch (installs deps, the
#                     gateway systemd service, and free-first model routing),
#                     then a loopback-only dashboard systemd service.
#
# It does NOT reimplement install.sh or the Dockerfile — it wraps them.
#
# Usage:
#   bash scripts/quickstart.sh                 # auto-detect (Docker if present)
#   bash scripts/quickstart.sh --docker        # force the Docker track
#   bash scripts/quickstart.sh --native        # force the native track
#   bash scripts/quickstart.sh --no-dashboard  # native: skip dashboard service
#
# Or standalone (no checkout needed — it will clone):
#   bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/quickstart.sh)
#
# "Make all models available": this wires every route the box can REACH —
# local OSS runtimes (Ollama/llama.cpp) + every hosted/free provider whose API
# key is present in ~/.hermes/.env.  Paid frontier models (Claude/GPT/Gemini/
# NIM) need YOUR keys in ~/.hermes/.env; add them and re-run the bootstrap line
# this script prints.  No fake keys are ever written.
# ============================================================================

set -e

if [ -n "${PYTHONPATH:-}" ]; then unset PYTHONPATH; fi
if [ -n "${PYTHONHOME:-}" ]; then unset PYTHONHOME; fi

# Colors
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'
MAGENTA='\033[0;35m'; BOLD='\033[1m'; NC='\033[0m'

log_info()    { echo -e "${CYAN}→${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
log_error()   { echo -e "${RED}✗${NC} $1"; }

REPO_URL_SSH="git@github.com:A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E.git"
REPO_URL_HTTPS="https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E.git"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DASHBOARD_PORT="${HERMES_DASHBOARD_PORT:-9119}"

# Options
TRACK="auto"            # auto | docker | native
INSTALL_DASHBOARD=true  # native track: install the dashboard systemd service
BRANCH="main"

print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│        ⚕ M.U.S.E. Quickstart — one-click deploy         │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker)       TRACK="docker"; shift ;;
        --native)       TRACK="native"; shift ;;
        --auto)         TRACK="auto"; shift ;;
        --no-dashboard) INSTALL_DASHBOARD=false; shift ;;
        --branch)       BRANCH="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            log_error "Unknown option: $1"
            log_info "Run with --help for usage."
            exit 1 ;;
    esac
done

# ----------------------------------------------------------------------------
# Locate (or obtain) a repo checkout. When run from inside a checkout we use it
# as-is; when piped from curl we clone to ~/.hermes/hermes-agent.
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
REPO_DIR=""

resolve_repo_dir() {
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/../docker-compose.yml" ] \
       && [ -f "$SCRIPT_DIR/install.sh" ]; then
        REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
        log_info "Using checkout at $REPO_DIR"
        return 0
    fi
    # Standalone (curl | bash): clone to the default install dir.
    REPO_DIR="$HERMES_HOME/hermes-agent"
    if [ -d "$REPO_DIR/.git" ]; then
        log_info "Updating existing checkout at $REPO_DIR"
        git -C "$REPO_DIR" fetch origin >/dev/null 2>&1 || true
        git -C "$REPO_DIR" checkout "$BRANCH" >/dev/null 2>&1 || true
        git -C "$REPO_DIR" pull --ff-only origin "$BRANCH" >/dev/null 2>&1 || true
        return 0
    fi
    log_info "Cloning M.U.S.E. to $REPO_DIR ..."
    mkdir -p "$(dirname "$REPO_DIR")"
    if GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=5" \
       git clone --branch "$BRANCH" "$REPO_URL_SSH" "$REPO_DIR" 2>/dev/null; then
        log_success "Cloned via SSH"
    else
        rm -rf "$REPO_DIR" 2>/dev/null || true
        if git clone --branch "$BRANCH" "$REPO_URL_HTTPS" "$REPO_DIR"; then
            log_success "Cloned via HTTPS"
        else
            log_error "Failed to clone repository"
            exit 1
        fi
    fi
}

have_docker() {
    command -v docker >/dev/null 2>&1 || return 1
    docker info >/dev/null 2>&1 || return 1
    docker compose version >/dev/null 2>&1 || return 1
    return 0
}

# Resolve a usable `muse` command (mirrors install.sh's resolution order).
resolve_muse_cmd() {
    if command -v muse >/dev/null 2>&1; then command -v muse; return 0; fi
    for c in "/usr/local/bin/muse" "$HOME/.local/bin/muse" \
             "$HERMES_HOME/hermes-agent/venv/bin/muse" "$REPO_DIR/venv/bin/muse"; do
        if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    echo ""
}

# ----------------------------------------------------------------------------
# Docker track
# ----------------------------------------------------------------------------
run_docker() {
    log_info "Docker track — building and starting the gateway + dashboard ..."
    cd "$REPO_DIR"
    mkdir -p "$HERMES_HOME"
    # HERMES_BOOTSTRAP_MODELS=1 (compose default) wires all reachable routes on
    # first boot. UID/GID keep volume files owned by the host user.
    HERMES_UID="$(id -u)" HERMES_GID="$(id -g)" \
        docker compose up -d --build
    echo ""
    log_success "Containers are up (restart: unless-stopped)."
    log_info "Gateway:    docker compose logs -f gateway"
    log_info "Dashboard:  http://127.0.0.1:${DASHBOARD_PORT}  (loopback only)"
    log_info "  Remote access:  ssh -L ${DASHBOARD_PORT}:localhost:${DASHBOARD_PORT} <user>@<this-host>"
    log_info "Add API keys:   edit ${HERMES_HOME}/.env  (never committed; agent never reads it)"
    log_info "Re-bootstrap after adding keys:"
    log_info "  docker compose exec gateway hermes models bootstrap --free-first --jarvis"
}

# ----------------------------------------------------------------------------
# Native track
# ----------------------------------------------------------------------------
install_dashboard_service() {
    [ "$INSTALL_DASHBOARD" = true ] || { log_info "Dashboard service skipped (--no-dashboard)."; return 0; }
    if ! command -v systemctl >/dev/null 2>&1; then
        log_info "systemd not present — skipping dashboard service."
        log_info "Run the dashboard manually:  muse dashboard --no-open"
        return 0
    fi
    local muse_bin; muse_bin="$(resolve_muse_cmd)"
    if [ -z "$muse_bin" ]; then
        log_warn "Could not resolve the muse command — skipping dashboard service."
        return 0
    fi
    local run_user; run_user="$(id -un)"
    local unit_dst="/etc/systemd/system/muse-dashboard.service"
    local sudo=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo="sudo"

    log_info "Installing loopback-only dashboard service (port ${DASHBOARD_PORT}) ..."
    local tmp; tmp="$(mktemp)"
    local template="$REPO_DIR/deploy/muse-dashboard.service"
    if [ -f "$template" ]; then
        sed -e "s|__MUSE_BIN__|${muse_bin}|g" \
            -e "s|__RUN_USER__|${run_user}|g" \
            -e "s|__HERMES_HOME__|${HERMES_HOME}|g" \
            "$template" > "$tmp"
    else
        cat > "$tmp" <<EOF
[Unit]
Description=M.U.S.E. web dashboard (loopback-only)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${run_user}
Environment=HERMES_HOME=${HERMES_HOME}
ExecStart=${muse_bin} dashboard --no-open --skip-build --host 127.0.0.1 --port ${DASHBOARD_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    fi
    if $sudo cp "$tmp" "$unit_dst" 2>/dev/null \
       && $sudo systemctl daemon-reload 2>/dev/null \
       && $sudo systemctl enable --now muse-dashboard 2>/dev/null; then
        log_success "Dashboard service running (muse-dashboard)."
        log_info "  Status:  systemctl status muse-dashboard   (or: muse dashboard --status)"
        log_info "  URL:     http://127.0.0.1:${DASHBOARD_PORT}  (tunnel in for remote access)"
    else
        log_warn "Could not install the dashboard service (need root/systemd)."
        log_info "Run it manually:  ${muse_bin} dashboard --no-open"
    fi
    rm -f "$tmp"
}

run_native() {
    log_info "Native track — running install.sh (deps + gateway service + model routing) ..."
    bash "$REPO_DIR/scripts/install.sh" --jarvis-launch --bootstrap-models --branch "$BRANCH"
    install_dashboard_service
}

# ----------------------------------------------------------------------------
# Closing summary: which models are live vs. need a key.
# ----------------------------------------------------------------------------
print_model_summary() {
    echo ""
    echo -e "${CYAN}${BOLD}🤖 Model routing (reachable routes — what's live vs. needs a key)${NC}"
    # `bootstrap --dry-run` plans without writing: it prints the detected local
    # runtimes and which providers are configured vs. missing a key.
    if [ "$TRACK" = "docker" ]; then
        docker compose exec -T gateway hermes models bootstrap \
            --free-first --jarvis --no-pull --dry-run 2>/dev/null | sed 's/^/   /' || \
            log_info "   Run 'docker compose exec gateway hermes models bootstrap --dry-run' to inspect routes."
    else
        local muse_bin; muse_bin="$(resolve_muse_cmd)"
        if [ -n "$muse_bin" ]; then
            "$muse_bin" models bootstrap --free-first --jarvis --no-pull --dry-run 2>/dev/null \
                | sed 's/^/   /' || \
                log_info "   Run 'muse models bootstrap --dry-run' to inspect routes."
        fi
    fi
    echo ""
    log_info "Want a provider that shows as missing? Add its key to ${HERMES_HOME}/.env, then re-run:"
    if [ "$TRACK" = "docker" ]; then
        log_info "  docker compose exec gateway hermes models bootstrap --free-first --jarvis"
    else
        log_info "  muse models bootstrap --free-first --jarvis"
    fi
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
main() {
    print_banner

    if [ "$TRACK" = "auto" ]; then
        if have_docker; then
            TRACK="docker"
            log_success "Docker detected → Docker track."
        else
            TRACK="native"
            log_info "Docker not available → native track."
        fi
    fi

    resolve_repo_dir

    case "$TRACK" in
        docker)
            if ! have_docker; then
                log_error "--docker was requested but Docker (with compose) is not available."
                log_info "Install Docker Engine + the compose plugin, or use --native."
                exit 1
            fi
            run_docker
            ;;
        native)
            run_native
            ;;
    esac

    print_model_summary

    echo ""
    echo -e "${GREEN}${BOLD}✓ M.U.S.E. is deployed.${NC}"
    log_info "Full guide: docs/deploy/vps-deployment-guide.md"
}

main
