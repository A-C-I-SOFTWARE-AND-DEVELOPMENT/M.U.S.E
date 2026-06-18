#!/usr/bin/env bash
# ============================================================================
# M.U.S.E. — long-horizon VPS hardening
# ============================================================================
# Takes an ALREADY-DEPLOYED M.U.S.E. (you ran scripts/quickstart.sh first) and
# layers on the resilience a 24/7, long-horizon agentic run needs but a plain
# install does not:
#
#   1. Self-healing autostart  — gateway.auto_start=true + `gateway ensure`,
#                                 plus systemd linger so a user-scope gateway
#                                 comes back after reboot without a login.
#   2. Restart hardening        — a systemd drop-in that disables the start-rate
#                                 limiter (StartLimitIntervalSec=0) so transient
#                                 crashes always self-heal, with Restart=always
#                                 and an OOM-deprioritized score.
#   3. Watchdog timer           — runs `muse gateway ensure` every 5 min as the
#                                 slow backstop (recovers after a clean stop /
#                                 reboot, which Restart= alone does not).
#   4. Daily backups            — a timer that zips ~/.hermes (restore with
#                                 `muse import`) and prunes old archives.
#   5. Log rotation             — logrotate for ~/.hermes/logs so months of
#                                 24/7 logs never fill the disk.
#
# It is OPT-IN, IDEMPOTENT, and ADDITIVE: re-run it freely, and remove the layer
# with `--uninstall`. It changes nothing about how the agent itself behaves —
# only how the host keeps it alive. Default code paths are untouched.
#
# Usage:
#   bash scripts/vps-harden-longhorizon.sh                 # apply everything
#   bash scripts/vps-harden-longhorizon.sh --dry-run       # show, change nothing
#   bash scripts/vps-harden-longhorizon.sh --uninstall     # remove the layer
#   bash scripts/vps-harden-longhorizon.sh --no-watchdog --no-backup
#
# Options:
#   --dry-run            Print every action; write nothing.
#   --uninstall          Remove the hardening layer (keeps gateway.auto_start).
#   --no-autostart       Skip auto_start + linger.
#   --no-hardening       Skip the gateway restart-hardening drop-in.
#   --no-watchdog        Skip the watchdog timer.
#   --no-backup          Skip the daily backup timer.
#   --no-logrotate       Skip log rotation.
#   --backup-dir DIR     Where daily backups go (default: <hermes-home>/backups).
#   --backup-keep N      Delete backups older than N days (default: 14).
#   --service NAME       Gateway unit base name (default: hermes-gateway; use
#                        hermes-gateway-<profile> for a non-default profile).
# ============================================================================
set -eo pipefail

if [ -n "${PYTHONPATH:-}" ]; then unset PYTHONPATH; fi
if [ -n "${PYTHONHOME:-}" ]; then unset PYTHONHOME; fi

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; RED='\033[0;31m'
MAGENTA='\033[0;35m'; BOLD='\033[1m'; NC='\033[0m'
log_info()    { echo -e "${CYAN}→${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
log_error()   { echo -e "${RED}✗${NC} $1"; }
log_dry()     { echo -e "${MAGENTA}[dry-run]${NC} $1"; }

# ---- options --------------------------------------------------------------
DRY_RUN=false
UNINSTALL=false
DO_AUTOSTART=true
DO_HARDENING=true
DO_WATCHDOG=true
DO_BACKUP=true
DO_LOGROTATE=true
BACKUP_DIR=""
BACKUP_KEEP=14
SERVICE_BASE="hermes-gateway"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)       DRY_RUN=true; shift ;;
        --uninstall)     UNINSTALL=true; shift ;;
        --no-autostart)  DO_AUTOSTART=false; shift ;;
        --no-hardening)  DO_HARDENING=false; shift ;;
        --no-watchdog)   DO_WATCHDOG=false; shift ;;
        --no-backup)     DO_BACKUP=false; shift ;;
        --no-logrotate)  DO_LOGROTATE=false; shift ;;
        --backup-dir)    BACKUP_DIR="$2"; shift 2 ;;
        --backup-keep)   BACKUP_KEEP="$2"; shift 2 ;;
        --service)       SERVICE_BASE="$2"; shift 2 ;;
        -h|--help)       sed -n '2,55p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
[ -n "$BACKUP_DIR" ] || BACKUP_DIR="$HERMES_HOME/backups"
RUN_USER="$(id -un)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR/../deploy/longhorizon"

# `run` executes a command unless --dry-run, in which case it just prints it.
run() {
    if [ "$DRY_RUN" = true ]; then log_dry "$*"; return 0; fi
    "$@"
}
# `run_sh` is the same for a shell snippet (redirections, sudo tee, …).
run_sh() {
    if [ "$DRY_RUN" = true ]; then log_dry "$1"; return 0; fi
    bash -c "$1"
}

# ---- resolve the muse binary ----------------------------------------------
resolve_muse_cmd() {
    if command -v muse >/dev/null 2>&1; then command -v muse; return 0; fi
    if command -v hermes >/dev/null 2>&1; then command -v hermes; return 0; fi
    for c in "/usr/local/bin/muse" "$HOME/.local/bin/muse" \
             "$HERMES_HOME/hermes-agent/venv/bin/muse"; do
        [ -x "$c" ] && { echo "$c"; return 0; }
    done
    echo ""
}
MUSE_BIN="$(resolve_muse_cmd)"

# ---- detect the deployment topology ---------------------------------------
# DOCKER: a container named `hermes` is running (compose already handles
#         autostart/restart, so we only add backups + logrotate on the host).
# SYSTEM: the gateway unit lives in /etc/systemd/system.
# USER:   the gateway unit lives in ~/.config/systemd/user.
DEPLOY="none"
SYSTEMCTL=""        # the systemctl invocation for the chosen scope
UNIT_DIR=""         # where unit files for the chosen scope live
SUDO=""
[ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo"

detect_topology() {
    if command -v docker >/dev/null 2>&1 \
       && docker ps --filter "name=^/hermes$" --format '{{.Names}}' 2>/dev/null | grep -q '^hermes$'; then
        DEPLOY="docker"
        return
    fi
    if [ -f "/etc/systemd/system/${SERVICE_BASE}.service" ]; then
        DEPLOY="system"; SYSTEMCTL="$SUDO systemctl"; UNIT_DIR="/etc/systemd/system"
        return
    fi
    if [ -f "$HOME/.config/systemd/user/${SERVICE_BASE}.service" ]; then
        DEPLOY="user"; SYSTEMCTL="systemctl --user"; UNIT_DIR="$HOME/.config/systemd/user"
        return
    fi
    # Native install but the unit isn't there yet — establish it, then re-detect.
    if [ -n "$MUSE_BIN" ]; then
        log_info "No ${SERVICE_BASE}.service yet — establishing the gateway first…"
        run "$MUSE_BIN" gateway ensure || log_warn "gateway ensure did not complete cleanly"
        if [ -f "/etc/systemd/system/${SERVICE_BASE}.service" ]; then
            DEPLOY="system"; SYSTEMCTL="$SUDO systemctl"; UNIT_DIR="/etc/systemd/system"
        elif [ -f "$HOME/.config/systemd/user/${SERVICE_BASE}.service" ]; then
            DEPLOY="user"; SYSTEMCTL="systemctl --user"; UNIT_DIR="$HOME/.config/systemd/user"
        fi
    fi
}

# `User=` line belongs only in system-scope units; user units reject it.
user_line() {
    if [ "$DEPLOY" = "system" ]; then printf 'User=%s\n' "$RUN_USER"; else printf ''; fi
}

# Install a deploy/longhorizon template into the chosen scope's unit dir,
# substituting placeholders. Args: <template-filename> <dest-filename>
install_unit() {
    local tmpl="$TEMPLATE_DIR/$1" dest="$UNIT_DIR/$2"
    if [ ! -f "$tmpl" ]; then log_error "Missing template: $tmpl"; return 1; fi
    local rendered; rendered="$(sed \
        -e "s|__MUSE_BIN__|${MUSE_BIN}|g" \
        -e "s|__RUN_USER__|${RUN_USER}|g" \
        -e "s|__HERMES_HOME__|${HERMES_HOME}|g" \
        -e "s|__BACKUP_DIR__|${BACKUP_DIR}|g" \
        -e "s|__KEEP_DAYS__|${BACKUP_KEEP}|g" \
        -e "s|__USER_LINE__|$(user_line)|g" \
        "$tmpl")"
    if [ "$DRY_RUN" = true ]; then
        log_dry "write $dest:"; echo "$rendered" | sed 's/^/      /'
        return 0
    fi
    if [ "$DEPLOY" = "system" ]; then
        printf '%s\n' "$rendered" | $SUDO tee "$dest" >/dev/null
    else
        mkdir -p "$(dirname "$dest")"
        printf '%s\n' "$rendered" > "$dest"
    fi
    log_success "installed $dest"
}

# ===========================================================================
# Apply / uninstall steps
# ===========================================================================
apply_autostart() {
    [ "$DO_AUTOSTART" = true ] || { log_info "autostart: skipped"; return; }
    [ -n "$MUSE_BIN" ] || { log_warn "autostart: no muse binary found — skipped"; return; }
    log_info "Enabling gateway.auto_start + establishing the service…"
    run "$MUSE_BIN" config set gateway.auto_start true
    run "$MUSE_BIN" gateway ensure || log_warn "gateway ensure did not complete cleanly"
    if [ "$DEPLOY" = "user" ] && command -v loginctl >/dev/null 2>&1; then
        log_info "Enabling systemd linger so the user gateway survives reboots without login…"
        run $SUDO loginctl enable-linger "$RUN_USER"
    fi
}

apply_hardening() {
    [ "$DO_HARDENING" = true ] || { log_info "hardening: skipped"; return; }
    local dropin_dir="$UNIT_DIR/${SERVICE_BASE}.service.d"
    log_info "Installing restart-hardening drop-in for ${SERVICE_BASE}.service…"
    if [ "$DRY_RUN" = true ]; then
        log_dry "mkdir -p $dropin_dir && install gateway-hardening.conf -> 10-longhorizon.conf"
    elif [ "$DEPLOY" = "system" ]; then
        $SUDO mkdir -p "$dropin_dir"
        $SUDO cp "$TEMPLATE_DIR/gateway-hardening.conf" "$dropin_dir/10-longhorizon.conf"
        log_success "installed $dropin_dir/10-longhorizon.conf"
    else
        mkdir -p "$dropin_dir"
        cp "$TEMPLATE_DIR/gateway-hardening.conf" "$dropin_dir/10-longhorizon.conf"
        log_success "installed $dropin_dir/10-longhorizon.conf"
    fi
    run_sh "$SYSTEMCTL daemon-reload"
    run_sh "$SYSTEMCTL restart ${SERVICE_BASE}.service" || log_warn "could not restart ${SERVICE_BASE} (apply on next restart)"
}

apply_watchdog() {
    [ "$DO_WATCHDOG" = true ] || { log_info "watchdog: skipped"; return; }
    log_info "Installing the gateway watchdog timer (every 5 min)…"
    install_unit "muse-watchdog.service" "muse-watchdog.service"
    install_unit "muse-watchdog.timer"   "muse-watchdog.timer"
    run_sh "$SYSTEMCTL daemon-reload"
    run_sh "$SYSTEMCTL enable --now muse-watchdog.timer"
}

apply_backup() {
    [ "$DO_BACKUP" = true ] || { log_info "backup: skipped"; return; }
    [ -n "$MUSE_BIN" ] || { log_warn "backup: no muse binary found — skipped"; return; }
    log_info "Installing the daily backup timer (-> $BACKUP_DIR, keep ${BACKUP_KEEP}d)…"
    run mkdir -p "$BACKUP_DIR"
    install_unit "muse-backup.service" "muse-backup.service"
    install_unit "muse-backup.timer"   "muse-backup.timer"
    run_sh "$SYSTEMCTL daemon-reload"
    run_sh "$SYSTEMCTL enable --now muse-backup.timer"
}

apply_logrotate() {
    [ "$DO_LOGROTATE" = true ] || { log_info "logrotate: skipped"; return; }
    if ! command -v logrotate >/dev/null 2>&1; then
        log_warn "logrotate not installed (apt install logrotate) — skipping log rotation."
        return
    fi
    log_info "Installing logrotate config for $HERMES_HOME/logs…"
    local rendered; rendered="$(sed \
        -e "s|__HERMES_HOME__|${HERMES_HOME}|g" \
        -e "s|__RUN_USER__|${RUN_USER}|g" \
        "$TEMPLATE_DIR/muse-logrotate.conf")"
    if [ "$DRY_RUN" = true ]; then
        log_dry "write /etc/logrotate.d/muse-hermes:"; echo "$rendered" | sed 's/^/      /'
    else
        printf '%s\n' "$rendered" | $SUDO tee /etc/logrotate.d/muse-hermes >/dev/null
        log_success "installed /etc/logrotate.d/muse-hermes"
    fi
}

uninstall_all() {
    log_warn "Removing the long-horizon hardening layer (gateway.auto_start is left as-is)…"
    run_sh "$SYSTEMCTL disable --now muse-watchdog.timer 2>/dev/null || true"
    run_sh "$SYSTEMCTL disable --now muse-backup.timer 2>/dev/null || true"
    local files=(
        "$UNIT_DIR/muse-watchdog.service" "$UNIT_DIR/muse-watchdog.timer"
        "$UNIT_DIR/muse-backup.service"   "$UNIT_DIR/muse-backup.timer"
        "$UNIT_DIR/${SERVICE_BASE}.service.d/10-longhorizon.conf"
    )
    for f in "${files[@]}"; do
        if [ "$DEPLOY" = "system" ]; then run $SUDO rm -f "$f"; else run rm -f "$f"; fi
    done
    run $SUDO rm -f /etc/logrotate.d/muse-hermes
    run_sh "$SYSTEMCTL daemon-reload"
    log_success "Hardening layer removed. The gateway service itself is untouched."
}

# ===========================================================================
# Main
# ===========================================================================
echo ""
echo -e "${MAGENTA}${BOLD}┌─────────────────────────────────────────────────────────┐${NC}"
echo -e "${MAGENTA}${BOLD}│   ⚕ M.U.S.E. — long-horizon VPS hardening                │${NC}"
echo -e "${MAGENTA}${BOLD}└─────────────────────────────────────────────────────────┘${NC}"
echo ""
[ "$DRY_RUN" = true ] && log_warn "DRY RUN — no changes will be made."

detect_topology
log_info "Deployment:   ${BOLD}${DEPLOY}${NC}"
log_info "muse binary:  ${MUSE_BIN:-<not found>}"
log_info "Hermes home:  ${HERMES_HOME}"
log_info "Service:      ${SERVICE_BASE}.service"

if [ "$DEPLOY" = "docker" ]; then
    log_info "Docker deployment detected — compose already provides restart/autostart."
    log_info "Applying the host-level pieces that still help (backups + logrotate)."
    DO_AUTOSTART=false; DO_HARDENING=false; DO_WATCHDOG=false
    # Backups run on the host against the bind-mounted ~/.hermes; that needs a
    # muse binary on the host. If there isn't one, fall back to a zip of the dir.
    SYSTEMCTL="$SUDO systemctl"; UNIT_DIR="/etc/systemd/system"; DEPLOY="system"
fi

if [ "$DEPLOY" = "none" ]; then
    log_error "No M.U.S.E. deployment found (no docker container, no gateway service)."
    log_info "Deploy first:  bash scripts/quickstart.sh"
    exit 1
fi

if [ "$UNINSTALL" = true ]; then
    uninstall_all
    exit 0
fi

apply_autostart
apply_hardening
apply_watchdog
apply_backup
apply_logrotate

echo ""
log_success "Long-horizon hardening applied."
echo ""
log_info "Verify:"
log_info "  $SYSTEMCTL status ${SERVICE_BASE}.service"
log_info "  $SYSTEMCTL list-timers 'muse-*'"
log_info "  ${MUSE_BIN:-muse} gateway status   &&   ${MUSE_BIN:-muse} doctor"
log_info "Runbook: docs/deploy/long-horizon-vps-runbook.md"
[ "$DRY_RUN" = true ] && { echo ""; log_warn "This was a DRY RUN — re-run without --dry-run to apply."; }
