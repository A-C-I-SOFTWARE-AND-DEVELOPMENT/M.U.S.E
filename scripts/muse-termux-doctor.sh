#!/usr/bin/env bash
# ============================================================================
# hermes-termux-doctor.sh
# ----------------------------------------------------------------------------
# Phone-first Termux diagnostic for the Hermes Agent runtime.
#
# Reports on:
#   * Termux detection (TERMUX_VERSION, PREFIX, termux-info)
#   * Package availability (pkg, git, python, node, etc.)
#   * Storage permission (~/storage symlink from termux-setup-storage)
#   * Wake lock support (termux-wake-lock / termux-api)
#   * Tooling: git, gh, python, node, codex, claude, aider, goose
#   * Hermes install state (HERMES_HOME, venv, hermes command)
#
# This script is strictly read-only — it never installs packages, modifies
# settings, or touches anything destructive. Output is suitable for sharing
# (no secrets are printed).
#
# Usage:
#   bash scripts/muse-termux-doctor.sh
#   bash scripts/muse-termux-doctor.sh --quiet     # only failures
#   bash scripts/muse-termux-doctor.sh --json      # machine-readable
# ============================================================================

set -u

QUIET=false
JSON=false
for arg in "$@"; do
    case "$arg" in
        --quiet|-q) QUIET=true ;;
        --json) JSON=true ;;
        -h|--help)
            sed -n '2,22p' "$0"
            exit 0
            ;;
        *)
            echo "unknown flag: $arg" >&2
            exit 2
            ;;
    esac
done

# ── Colors (disabled if not a TTY) ─────────────────────────────────────────
if [ -t 1 ] && [ "$JSON" = false ]; then
    C_RED=$'\033[0;31m'
    C_GREEN=$'\033[0;32m'
    C_YELLOW=$'\033[0;33m'
    C_BLUE=$'\033[0;34m'
    C_DIM=$'\033[2m'
    C_BOLD=$'\033[1m'
    C_OFF=$'\033[0m'
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_BOLD=""; C_OFF=""
fi

# Result counters
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
INFO_COUNT=0

# JSON results buffer (lines of: status<TAB>label<TAB>detail)
RESULTS_FILE="$(mktemp -t hermes-termux-doctor.XXXXXX 2>/dev/null || mktemp)"
trap 'rm -f "$RESULTS_FILE"' EXIT

_record() {
    local status="$1" label="$2" detail="${3:-}"
    printf '%s\t%s\t%s\n' "$status" "$label" "$detail" >> "$RESULTS_FILE"
}

_print() {
    local status="$1" label="$2" detail="${3:-}"
    case "$status" in
        pass) PASS_COUNT=$((PASS_COUNT + 1)) ;;
        warn) WARN_COUNT=$((WARN_COUNT + 1)) ;;
        fail) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
        info) INFO_COUNT=$((INFO_COUNT + 1)) ;;
    esac
    _record "$status" "$label" "$detail"

    [ "$JSON" = true ] && return 0
    if [ "$QUIET" = true ] && [ "$status" != "fail" ] && [ "$status" != "warn" ]; then
        return 0
    fi

    local glyph color
    case "$status" in
        pass) glyph="OK  "; color="$C_GREEN" ;;
        warn) glyph="WARN"; color="$C_YELLOW" ;;
        fail) glyph="FAIL"; color="$C_RED" ;;
        info) glyph="INFO"; color="$C_BLUE" ;;
        *)    glyph="    "; color="" ;;
    esac
    if [ -n "$detail" ]; then
        printf '%s[%s]%s %s %s(%s)%s\n' "$color" "$glyph" "$C_OFF" "$label" "$C_DIM" "$detail" "$C_OFF"
    else
        printf '%s[%s]%s %s\n' "$color" "$glyph" "$C_OFF" "$label"
    fi
}

_section() {
    [ "$JSON" = true ] && return 0
    [ "$QUIET" = true ] && return 0
    printf '\n%s── %s ──%s\n' "$C_BOLD" "$1" "$C_OFF"
}

# ── Detection helpers ──────────────────────────────────────────────────────

is_termux() {
    [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux/files/usr"* ]]
}

have() {
    command -v "$1" >/dev/null 2>&1
}

# Try to obtain a version string without leaking env contents.
tool_version() {
    local tool="$1"
    if ! have "$tool"; then
        echo ""
        return 1
    fi
    local out=""
    out=$("$tool" --version 2>&1 | head -n 1) || out=""
    if [ -z "$out" ]; then
        out=$("$tool" -v 2>&1 | head -n 1) || out=""
    fi
    # Strip anything that looks like a path under /data/data/com.termux to
    # avoid printing the device-specific install location in shared output.
    out=${out//\/data\/data\/com.termux\/files\/usr/<PREFIX>}
    out=${out//$HOME/<HOME>}
    echo "$out"
}

# ── Header ─────────────────────────────────────────────────────────────────
_section "Hermes Termux Doctor"

# ── 1. Termux detection ────────────────────────────────────────────────────
_section "Termux detection"

if is_termux; then
    _print pass "Running inside Termux" "TERMUX_VERSION=${TERMUX_VERSION:-unknown}"
else
    _print fail "Not running inside Termux" "TERMUX_VERSION unset and PREFIX does not look Termux-like"
    _print info "This script is designed for Termux on Android" \
        "see docs/termux/muse-phone-first-runtime.md"
fi

if [ -n "${PREFIX:-}" ]; then
    _print pass "PREFIX environment variable set" "$PREFIX"
else
    _print warn "PREFIX is unset" "expected on Termux"
fi

if have termux-info; then
    # Pull only architecture, Android version, device model lines — keep
    # the rest off-screen to avoid leaking anything identifying.
    info_arch=$(termux-info 2>/dev/null | awk -F': ' '/^CPU architecture/{print $2; exit}')
    info_android=$(termux-info 2>/dev/null | awk -F': ' '/^Android version/{print $2; exit}')
    _print pass "termux-info available" "${info_arch:-?} on Android ${info_android:-?}"
else
    _print warn "termux-info not found" "pkg install termux-tools"
fi

# ── 2. Package manager + storage ───────────────────────────────────────────
_section "Package manager + storage"

if have pkg; then
    _print pass "pkg is available"
else
    _print fail "pkg (Termux package manager) not found" "is this really Termux?"
fi

if have apt; then
    _print pass "apt is available (used by pkg under the hood)"
else
    _print info "apt not directly on PATH" "pkg wraps it"
fi

if [ -L "$HOME/storage" ] || [ -d "$HOME/storage" ]; then
    _print pass "Shared storage linked at ~/storage" "termux-setup-storage previously run"
else
    _print warn "~/storage symlink not present" \
        "run: termux-setup-storage (grants Android storage permission)"
fi

# Detect Termux:API availability (separate add-on app).
if have termux-battery-status; then
    bs_pct=$(termux-battery-status 2>/dev/null | awk -F'[,:]' '/"percentage"/{gsub(/[ "]/,"",$2); print $2; exit}')
    if [ -n "$bs_pct" ]; then
        _print pass "Termux:API installed (battery readable)" "battery ${bs_pct}%"
    else
        _print warn "Termux:API helper present but unresponsive" \
            "is the Termux:API Android app installed and granted permissions?"
    fi
else
    _print warn "Termux:API helpers not found" \
        "install Termux:API app + pkg install termux-api (optional but recommended)"
fi

# ── 3. Wake lock support ───────────────────────────────────────────────────
_section "Wake lock"

if have termux-wake-lock && have termux-wake-unlock; then
    _print pass "termux-wake-lock / termux-wake-unlock available"
    _print info "Wake lock keeps the CPU awake while the gateway runs in the background" \
        "see docs/termux/muse-android-permissions.md"
else
    _print warn "termux-wake-lock helpers missing" \
        "pkg install termux-tools (usually preinstalled)"
fi

# ── 4. Required tooling ────────────────────────────────────────────────────
_section "Core tooling"

for t in git python python3 pip node; do
    if have "$t"; then
        v=$(tool_version "$t")
        _print pass "$t available" "${v:-installed}"
    else
        case "$t" in
            python)
                # python3 is fine if present
                if have python3; then continue; fi
                _print fail "$t missing" "pkg install python"
                ;;
            python3)
                if have python; then continue; fi
                _print fail "$t missing" "pkg install python"
                ;;
            git)  _print fail "$t missing" "pkg install git" ;;
            pip)  _print warn "$t missing" "python -m ensurepip --upgrade" ;;
            node) _print warn "$t missing" "pkg install nodejs (optional; needed for browser tools)" ;;
        esac
    fi
done

# ── 5. Optional CLI agents ─────────────────────────────────────────────────
_section "Optional CLI agents"

for t in gh codex claude aider goose; do
    if have "$t"; then
        v=$(tool_version "$t")
        _print pass "$t available" "${v:-installed}"
    else
        _print info "$t not installed" "optional integration"
    fi
done

# ── 6. Hermes install state ────────────────────────────────────────────────
_section "Hermes install state"

HERMES_HOME_VAL="${HERMES_HOME:-$HOME/.hermes}"
if [ -d "$HERMES_HOME_VAL" ]; then
    _print pass "HERMES_HOME exists" "$HERMES_HOME_VAL"
else
    _print warn "HERMES_HOME directory missing" "$HERMES_HOME_VAL (will be created on first run)"
fi

if [ -d "$HERMES_HOME_VAL/hermes-agent/.git" ]; then
    _print pass "hermes-agent checkout present" "$HERMES_HOME_VAL/hermes-agent"
else
    _print info "No hermes-agent checkout under HERMES_HOME" \
        "expected if you cloned elsewhere; see scripts/install.sh"
fi

# Venv check — try common locations without picking a side.
VENV_FOUND=""
for c in \
    "$HERMES_HOME_VAL/hermes-agent/venv" \
    "$HERMES_HOME_VAL/hermes-agent/.venv" \
    "$(pwd)/venv" \
    "$(pwd)/.venv"; do
    if [ -f "$c/bin/activate" ]; then
        VENV_FOUND="$c"
        break
    fi
done
if [ -n "$VENV_FOUND" ]; then
    _print pass "Python venv detected" "$VENV_FOUND"
else
    _print warn "No Python venv detected" "run scripts/install.sh to create one"
fi

if have hermes; then
    _print pass "hermes command on PATH" "$(command -v hermes)"
else
    _print warn "hermes command not on PATH" \
        "add \$PREFIX/bin or your venv bin dir to PATH"
fi

# ── 7. Network + DNS sanity (no external calls) ────────────────────────────
_section "Network sanity (local only)"

if [ -r /etc/resolv.conf ] || [ -r "${PREFIX:-/}/etc/resolv.conf" ]; then
    _print pass "resolv.conf readable"
else
    _print info "resolv.conf not readable" "Termux often uses getaddrinfo via Android — usually fine"
fi

# ── Summary ────────────────────────────────────────────────────────────────
if [ "$JSON" = true ]; then
    # Emit compact JSON (no jq dependency).
    printf '{"results":['
    first=true
    while IFS=$'\t' read -r status label detail; do
        [ -z "$status" ] && continue
        $first || printf ','
        first=false
        # Escape minimally — replace " and \ in label/detail.
        esc_label=${label//\\/\\\\}; esc_label=${esc_label//\"/\\\"}
        esc_detail=${detail//\\/\\\\}; esc_detail=${esc_detail//\"/\\\"}
        printf '{"status":"%s","label":"%s","detail":"%s"}' \
            "$status" "$esc_label" "$esc_detail"
    done < "$RESULTS_FILE"
    printf '],"summary":{"pass":%d,"warn":%d,"fail":%d,"info":%d}}\n' \
        "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" "$INFO_COUNT"
else
    _section "Summary"
    printf '%sPass:%s %d   %sWarn:%s %d   %sFail:%s %d   %sInfo:%s %d\n' \
        "$C_GREEN" "$C_OFF" "$PASS_COUNT" \
        "$C_YELLOW" "$C_OFF" "$WARN_COUNT" \
        "$C_RED" "$C_OFF" "$FAIL_COUNT" \
        "$C_BLUE" "$C_OFF" "$INFO_COUNT"
fi

# Exit non-zero only on hard failures so this can gate CI / startup hooks.
if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
