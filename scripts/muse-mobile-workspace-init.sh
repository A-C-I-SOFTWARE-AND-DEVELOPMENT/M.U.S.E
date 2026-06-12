#!/usr/bin/env bash
# ============================================================================
# hermes-mobile-workspace-init.sh
# ----------------------------------------------------------------------------
# Workspace bootstrap helper for ACI Hermes on phone / Termux setups.
#
# What this script does:
#   * Captures the current working directory as the "Hermes workspace".
#   * Confirms the workspace is a git checkout.
#   * Prints the active branch, remote URL, and short HEAD.
#   * Probes for the optional CLIs that share this workspace:
#       hermes        — the Python CLI in this repo
#       codex         — OpenAI Codex CLI
#       claude        — Anthropic Claude Code CLI
#       adb           — Android Debug Bridge (for the apps/android module)
#       termux-info   — Termux runtime
#   * Reports whether the repo's apps/android module is present.
#
# What this script DOES NOT do:
#   * It never reads, prints, or stores any API key, OAuth token, or
#     gateway bearer.
#   * It never runs `codex auth`, `claude auth`, `hermes setup`, or any
#     other command that mutates configuration. Authentication for each
#     CLI must be performed by following that CLI's own documented flow.
#   * It never modifies files in the workspace.
#
# Usage:
#   bash scripts/muse-mobile-workspace-init.sh
#   bash scripts/muse-mobile-workspace-init.sh --quiet   # only failures
#   bash scripts/muse-mobile-workspace-init.sh --json    # machine-readable
#
# Exit codes:
#   0   workspace is usable (CLIs may be missing — those are warnings only)
#   1   not a git workspace, or a structural problem with the repo
#   2   bad usage / unknown flag
# ============================================================================

set -u

QUIET=false
JSON=false
for arg in "$@"; do
    case "$arg" in
        --quiet|-q) QUIET=true ;;
        --json) JSON=true ;;
        -h|--help)
            sed -n '2,32p' "$0"
            exit 0
            ;;
        *)
            echo "unknown flag: $arg" >&2
            exit 2
            ;;
    esac
done

# ── Colors (disabled if not a TTY or in JSON mode) ─────────────────────────
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

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
INFO_COUNT=0

RESULTS_FILE="$(mktemp -t hermes-workspace-init.XXXXXX 2>/dev/null || mktemp)"
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
    printf '\n%s== %s ==%s\n' "$C_BOLD" "$1" "$C_OFF"
}

# ── 1. Workspace location ─────────────────────────────────────────────────
WORKSPACE_DIR="$(pwd)"
_section "Workspace"
_print info "workspace_dir" "$WORKSPACE_DIR"

# ── 2. Git workspace check ────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
    _print fail "git not on PATH" "install git before running this script"
    GIT_OK=false
elif ! git -C "$WORKSPACE_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    _print fail "not a git workspace" "cd into an ACI Hermes checkout first"
    GIT_OK=false
else
    GIT_OK=true
    BRANCH="$(git -C "$WORKSPACE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    SHORT_SHA="$(git -C "$WORKSPACE_DIR" rev-parse --short HEAD 2>/dev/null || echo '?')"
    REMOTE_URL="$(git -C "$WORKSPACE_DIR" config --get remote.origin.url 2>/dev/null || echo '(no origin remote)')"
    _print pass "git workspace detected"
    _print info "branch" "$BRANCH"
    _print info "HEAD" "$SHORT_SHA"
    _print info "origin" "$REMOTE_URL"
fi

# ── 3. Repo structural sanity ─────────────────────────────────────────────
_section "Repo structure"
if [ -f "$WORKSPACE_DIR/pyproject.toml" ]; then
    _print pass "pyproject.toml present"
else
    _print warn "pyproject.toml missing" "are you in the wrong directory?"
fi

if [ -f "$WORKSPACE_DIR/run_agent.py" ] && [ -f "$WORKSPACE_DIR/cli.py" ]; then
    _print pass "Python CLI entry points present" "run_agent.py + cli.py"
else
    _print warn "Python CLI entry points missing" "expected run_agent.py and cli.py"
fi

if [ -d "$WORKSPACE_DIR/apps/android" ] && [ -f "$WORKSPACE_DIR/apps/android/settings.gradle.kts" ]; then
    _print pass "apps/android module present" "Kotlin/Compose companion app"
else
    _print info "apps/android module not present" "Python/CLI-only checkout"
fi

if [ -d "$WORKSPACE_DIR/skills" ]; then
    _print pass "skills/ directory present"
else
    _print warn "skills/ directory missing"
fi

# ── 4. Optional CLIs that share this workspace ────────────────────────────
_section "Tooling"

_probe_cli() {
    local name="$1" purpose="$2"
    if command -v "$name" >/dev/null 2>&1; then
        local where
        where="$(command -v "$name")"
        _print pass "$name found" "$where"
    else
        _print warn "$name not on PATH" "$purpose"
    fi
}

_probe_cli hermes      "Hermes Python CLI (install with: uv pip install -e \".[dev]\")"
_probe_cli codex       "OpenAI Codex CLI (follow Codex's install + auth docs separately)"
_probe_cli claude      "Anthropic Claude Code CLI (follow Anthropic's install + auth docs separately)"
_probe_cli adb         "Android Debug Bridge (needed only when working with apps/android)"
_probe_cli termux-info "Termux runtime probe (only present inside Termux)"

# ── 5. Termux awareness ───────────────────────────────────────────────────
if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux/files" ]; then
    _section "Termux runtime"
    _print pass "Termux environment detected"
    if [ -n "${TERMUX_VERSION:-}" ]; then
        _print info "TERMUX_VERSION" "$TERMUX_VERSION"
    fi
    if [ -d "$HOME/storage" ]; then
        _print pass "shared storage linked" "$HOME/storage"
    else
        _print warn "shared storage not linked" "run termux-setup-storage when ready"
    fi
fi

# ── 6. Honest reminders about auth ────────────────────────────────────────
_section "Authentication reminders"
_print info "Provider API keys" "live in ~/.hermes/.env — never commit them"
_print info "Codex login"        "use Codex CLI's own login flow; this script will not run it"
_print info "Claude Code login"  "use Claude CLI's own login flow; this script will not run it"
_print info "ChatGPT / Claude.ai subscriptions" "do NOT grant API access — separate billing"
_print info "Same-workspace rule" "launch hermes, codex, and claude from this directory: $WORKSPACE_DIR"

# ── 7. Summary ────────────────────────────────────────────────────────────
if [ "$JSON" = true ]; then
    # Emit JSON without depending on jq.
    printf '{\n'
    printf '  "workspace": "%s",\n' "$WORKSPACE_DIR"
    printf '  "summary": {"pass": %d, "warn": %d, "fail": %d, "info": %d},\n' \
        "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" "$INFO_COUNT"
    printf '  "results": [\n'
    first=true
    while IFS=$'\t' read -r status label detail; do
        if [ "$first" = true ]; then first=false; else printf ',\n'; fi
        esc_label=${label//\"/\\\"}
        esc_detail=${detail//\"/\\\"}
        printf '    {"status": "%s", "label": "%s", "detail": "%s"}' \
            "$status" "$esc_label" "$esc_detail"
    done < "$RESULTS_FILE"
    printf '\n  ]\n}\n'
else
    printf '\n%sSummary:%s pass=%d warn=%d fail=%d info=%d\n' \
        "$C_BOLD" "$C_OFF" "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT" "$INFO_COUNT"
    if [ "$FAIL_COUNT" -gt 0 ]; then
        printf '%sWorkspace is NOT ready.%s See FAIL lines above.\n' "$C_RED" "$C_OFF"
    else
        printf '%sWorkspace looks usable.%s Warnings (if any) are optional CLIs.\n' \
            "$C_GREEN" "$C_OFF"
    fi
fi

[ "$GIT_OK" = false ] && exit 1
[ "$FAIL_COUNT" -gt 0 ] && exit 1
exit 0
