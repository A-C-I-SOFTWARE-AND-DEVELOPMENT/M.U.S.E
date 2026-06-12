#!/usr/bin/env bash
# ============================================================================
# hermes-termux-service.sh
# ----------------------------------------------------------------------------
# Phone-first service manager for the Hermes Agent runtime on Termux.
#
# Termux does not run systemd or launchd, so this script implements a
# minimal supervisor pattern using a PID file, a wake lock, and nohup.
# It is intentionally small and self-contained so it can be invoked from
# Termux:Boot at device startup (see docs/termux/hermes-termux-boot.md).
#
# Subcommands:
#   start     Start the local Hermes API (and the gateway if configured).
#   stop      Stop services started by this script.
#   restart   stop + start.
#   status    Show whether services are running, with PID + uptime.
#   logs      Tail the most recent service log (Ctrl-C to exit).
#   doctor    Delegate to hermes-termux-doctor.sh for environment checks.
#
# Environment:
#   HERMES_HOME              ~/.hermes by default
#   HERMES_REPO_DIR          Path to the hermes-agent checkout. Auto-detected
#                            from this script's parent or HERMES_HOME.
#   HERMES_TERMUX_API_CMD    Override the API start command (advanced).
#   HERMES_TERMUX_API_PORT   Port for the local API (default: 8765).
#   HERMES_TERMUX_GATEWAY    Set to "1" to also start the gateway.
#   HERMES_TERMUX_NO_WAKELOCK Set to "1" to skip termux-wake-lock acquisition.
#
# Safety:
#   * No secrets are read or printed.
#   * No destructive commands (no rm -rf, no pkg uninstall, no kill -9 of
#     unrelated PIDs). The script only signals processes whose PID it wrote.
# ============================================================================

set -u

# ── Locate the repo + this script ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_REPO_DIR="${HERMES_REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

# Termux runtime state directory.
STATE_DIR="$HERMES_HOME/termux"
LOG_DIR="$HERMES_HOME/logs"
mkdir -p "$STATE_DIR" "$LOG_DIR" 2>/dev/null || true

API_PID_FILE="$STATE_DIR/api.pid"
API_LOG_FILE="$LOG_DIR/termux-api.log"
GATEWAY_PID_FILE="$STATE_DIR/gateway.pid"
GATEWAY_LOG_FILE="$LOG_DIR/termux-gateway.log"
WAKELOCK_MARKER="$STATE_DIR/wake-lock.acquired"

API_PORT="${HERMES_TERMUX_API_PORT:-8765}"
RUN_GATEWAY="${HERMES_TERMUX_GATEWAY:-0}"

# ── Colors ─────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[0;33m'
    C_BLUE=$'\033[0;34m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_OFF=$'\033[0m'
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_BOLD=""; C_OFF=""
fi

log()  { printf '%s[hermes-termux]%s %s\n' "$C_BLUE" "$C_OFF" "$*"; }
ok()   { printf '%s[hermes-termux]%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '%s[hermes-termux]%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
err()  { printf '%s[hermes-termux]%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

is_termux() {
    [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux/files/usr"* ]]
}

# ── PID file helpers ───────────────────────────────────────────────────────
read_pid() {
    local f="$1"
    [ -f "$f" ] || return 1
    local pid
    pid=$(cat "$f" 2>/dev/null | tr -d '[:space:]')
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    echo "$pid"
}

# Returns 0 if PID is alive AND was started by this script (PID file matches).
pid_alive() {
    local f="$1"
    local pid
    pid=$(read_pid "$f") || return 1
    kill -0 "$pid" 2>/dev/null
}

uptime_for_pid() {
    local pid="$1"
    if have stat; then
        # On Termux/Linux, /proc/<pid> mtime reflects process start.
        local started_at now
        started_at=$(stat -c %Y "/proc/$pid" 2>/dev/null) || return 1
        now=$(date +%s)
        local secs=$((now - started_at))
        printf '%dh%02dm%02ds' $((secs/3600)) $(((secs%3600)/60)) $((secs%60))
    fi
}

# ── Wake lock ──────────────────────────────────────────────────────────────
acquire_wakelock() {
    [ "${HERMES_TERMUX_NO_WAKELOCK:-0}" = "1" ] && return 0
    if have termux-wake-lock; then
        if termux-wake-lock 2>/dev/null; then
            : > "$WAKELOCK_MARKER"
            log "wake lock acquired (CPU will stay awake)"
        else
            warn "termux-wake-lock failed — Android may suspend the service"
        fi
    else
        warn "termux-wake-lock not installed — service may pause on screen-off"
        warn "  install: pkg install termux-tools"
    fi
}

release_wakelock() {
    [ -f "$WAKELOCK_MARKER" ] || return 0
    if have termux-wake-unlock; then
        termux-wake-unlock 2>/dev/null || true
        log "wake lock released"
    fi
    rm -f "$WAKELOCK_MARKER" 2>/dev/null || true
}

# ── Start helpers ──────────────────────────────────────────────────────────
hermes_cmd() {
    # Prefer the hermes command on PATH; fall back to invoking the module
    # from the repo checkout so this script works in fresh installs where
    # the symlink has not yet been wired up.
    if have hermes; then
        echo "hermes"
    elif [ -f "$HERMES_REPO_DIR/cli.py" ]; then
        # Use the venv python if present, otherwise system python3.
        local py=""
        for c in \
            "$HERMES_REPO_DIR/venv/bin/python" \
            "$HERMES_REPO_DIR/.venv/bin/python" \
            "$HERMES_HOME/hermes-agent/venv/bin/python"; do
            if [ -x "$c" ]; then py="$c"; break; fi
        done
        [ -n "$py" ] || py="python3"
        echo "$py $HERMES_REPO_DIR/cli.py"
    else
        return 1
    fi
}

start_api() {
    if pid_alive "$API_PID_FILE"; then
        log "API already running (pid $(read_pid "$API_PID_FILE"))"
        return 0
    fi

    local cmd
    if [ -n "${HERMES_TERMUX_API_CMD:-}" ]; then
        cmd="$HERMES_TERMUX_API_CMD"
    else
        local base
        base=$(hermes_cmd) || { err "could not locate hermes command or cli.py"; return 1; }
        # `hermes serve` is the local-API entrypoint when the muse_cli
        # is installed. We pass it through `nohup` so it survives the
        # parent shell exiting.
        cmd="$base serve --port $API_PORT"
    fi

    log "starting API: $cmd"
    # shellcheck disable=SC2086
    nohup $cmd >> "$API_LOG_FILE" 2>&1 < /dev/null &
    local pid=$!
    echo "$pid" > "$API_PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        ok "API started (pid $pid, logs: $API_LOG_FILE)"
    else
        err "API failed to start — see $API_LOG_FILE"
        rm -f "$API_PID_FILE"
        return 1
    fi
}

start_gateway() {
    [ "$RUN_GATEWAY" = "1" ] || return 0
    if pid_alive "$GATEWAY_PID_FILE"; then
        log "gateway already running (pid $(read_pid "$GATEWAY_PID_FILE"))"
        return 0
    fi

    local base
    base=$(hermes_cmd) || { err "could not locate hermes command or cli.py"; return 1; }
    local cmd="$base gateway run"
    log "starting gateway: $cmd"
    # shellcheck disable=SC2086
    nohup $cmd >> "$GATEWAY_LOG_FILE" 2>&1 < /dev/null &
    local pid=$!
    echo "$pid" > "$GATEWAY_PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        ok "gateway started (pid $pid, logs: $GATEWAY_LOG_FILE)"
    else
        err "gateway failed to start — see $GATEWAY_LOG_FILE"
        rm -f "$GATEWAY_PID_FILE"
        return 1
    fi
}

# ── Stop helpers (graceful TERM, then INT — never -9) ──────────────────────
stop_one() {
    local label="$1" pidfile="$2"
    local pid
    if ! pid=$(read_pid "$pidfile"); then
        log "$label: no PID file ($pidfile)"
        return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        log "$label: PID $pid not alive — cleaning up stale PID file"
        rm -f "$pidfile"
        return 0
    fi
    log "$label: sending SIGTERM to pid $pid"
    kill -TERM "$pid" 2>/dev/null || true
    # Wait up to 10s for a graceful exit.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        warn "$label: pid $pid still alive after SIGTERM, sending SIGINT"
        kill -INT "$pid" 2>/dev/null || true
        sleep 2
    fi
    if kill -0 "$pid" 2>/dev/null; then
        warn "$label: pid $pid did not exit cleanly; leaving PID file in place"
        warn "  inspect the process with: ps -p $pid -o pid,etime,cmd"
        return 1
    fi
    rm -f "$pidfile"
    ok "$label stopped"
}

# ── Subcommands ────────────────────────────────────────────────────────────
cmd_start() {
    if ! is_termux; then
        warn "this script is designed for Termux; continuing anyway"
    fi
    acquire_wakelock
    start_api || return 1
    start_gateway || return 1
    log "to follow output: bash $0 logs"
}

cmd_stop() {
    local rc=0
    stop_one "gateway" "$GATEWAY_PID_FILE" || rc=1
    stop_one "API"     "$API_PID_FILE"     || rc=1
    release_wakelock
    return $rc
}

cmd_restart() {
    cmd_stop || true
    sleep 1
    cmd_start
}

cmd_status() {
    printf '%shermes-termux status%s\n' "$C_BOLD" "$C_OFF"
    printf '  state dir : %s\n' "$STATE_DIR"
    printf '  log dir   : %s\n' "$LOG_DIR"
    printf '  repo dir  : %s\n' "$HERMES_REPO_DIR"
    printf '  api port  : %s\n' "$API_PORT"
    printf '  gateway   : %s\n' "$([ "$RUN_GATEWAY" = "1" ] && echo enabled || echo disabled)"
    if [ -f "$WAKELOCK_MARKER" ]; then
        printf '  wake lock : %sheld%s\n' "$C_GREEN" "$C_OFF"
    else
        printf '  wake lock : %snot held%s\n' "$C_DIM" "$C_OFF"
    fi
    printf '\n'

    for entry in "API|$API_PID_FILE" "gateway|$GATEWAY_PID_FILE"; do
        local label="${entry%%|*}" pidfile="${entry##*|}" pid up
        if pid=$(read_pid "$pidfile") && kill -0 "$pid" 2>/dev/null; then
            up=$(uptime_for_pid "$pid" || echo "?")
            printf '  %s%s%s : running (pid %s, up %s)\n' "$C_GREEN" "$label" "$C_OFF" "$pid" "$up"
        else
            printf '  %s%s%s : stopped\n' "$C_DIM" "$label" "$C_OFF"
            [ -f "$pidfile" ] && printf '            (stale PID file: %s)\n' "$pidfile"
        fi
    done
}

cmd_logs() {
    local target="${1:-api}"
    local f
    case "$target" in
        api)     f="$API_LOG_FILE" ;;
        gateway) f="$GATEWAY_LOG_FILE" ;;
        *)       err "unknown log target: $target (try: api, gateway)"; return 2 ;;
    esac
    if [ ! -f "$f" ]; then
        warn "no log file yet at $f"
        return 1
    fi
    log "tailing $f (Ctrl-C to exit)"
    tail -n 100 -f "$f"
}

cmd_doctor() {
    local doc="$SCRIPT_DIR/hermes-termux-doctor.sh"
    if [ ! -x "$doc" ] && [ ! -f "$doc" ]; then
        err "doctor script not found at $doc"
        return 1
    fi
    bash "$doc" "$@"
}

usage() {
    cat <<'USAGE'
hermes-termux-service.sh — phone-first Hermes service manager

Usage:
  bash scripts/hermes-termux-service.sh <command>

Commands:
  start      Start the local API (and gateway if HERMES_TERMUX_GATEWAY=1).
  stop       Stop services started by this script.
  restart    stop + start.
  status     Show running state, PIDs, and uptime.
  logs [api|gateway]
             Tail the named log (default: api).
  doctor     Run hermes-termux-doctor.sh for environment checks.

Environment:
  HERMES_HOME              Base data dir (default: ~/.hermes)
  HERMES_REPO_DIR          Path to hermes-agent checkout (auto-detected)
  HERMES_TERMUX_API_PORT   Local API port (default: 8765)
  HERMES_TERMUX_GATEWAY    Set to 1 to also start the gateway
  HERMES_TERMUX_NO_WAKELOCK Set to 1 to skip wake lock acquisition
  HERMES_TERMUX_API_CMD    Override the API start command (advanced)

See docs/termux/ for phone-first runtime and Termux:Boot guidance.
USAGE
}

# ── Entry point ────────────────────────────────────────────────────────────
sub="${1:-}"
shift || true
case "$sub" in
    start)   cmd_start "$@" ;;
    stop)    cmd_stop "$@" ;;
    restart) cmd_restart "$@" ;;
    status)  cmd_status "$@" ;;
    logs)    cmd_logs "$@" ;;
    doctor)  cmd_doctor "$@" ;;
    ""|-h|--help|help) usage ;;
    *)
        err "unknown command: $sub"
        usage
        exit 2
        ;;
esac
