#!/bin/sh
# setup-local-gemma-8gb.sh — configure local Gemma 4 routing for an ~8 GB box.
#
# Applies the job-weight routing policy this repo ships (see
# docs/ai-intelligence/gemma4-integration.md):
#
#   Fast daily (chat/voice/summarize/memory)  -> gemma4-e2b
#   Coding / planning / deeper reasoning       -> gemma4-e4b *if it loads cleanly*
#                                                 (auto-falls back to e2b on OOM)
#   Large autonomous research                  -> cloud / server (never local)
#   26B / 31B                                  -> never an auto local default
#
# It pulls the two small variants, writes the free-first/local-only routing
# policy, and runs the E4B smoke check that arms the load-gate. The policy +
# gate then route everything automatically — no owner pins are set, so the
# "only if it loads cleanly" fallback stays in force. Idempotent and safe to
# re-run. Nothing here spends money or touches a remote.
#
# Usage:
#   scripts/setup-local-gemma-8gb.sh            # pull + bootstrap + smoke + verify
#   PYTHON=python3.11 scripts/setup-local-gemma-8gb.sh
set -eu

PYTHON="${PYTHON:-python3}"
JP="$PYTHON -m muse_cli.jarvis_prime"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33m!! %s\033[0m\n' "$*" >&2; }

# --- 1. runtime guard ------------------------------------------------------
say "1/5  Checking the local runtime (Ollama)"
if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama is not installed. Install it first: https://ollama.com"
    warn "Then re-run this script."
    exit 1
fi
ollama --version || true

# --- 2. pull the small variants (with a tag-existence guard) ---------------
# 'gemma4:*' tags may not be published on the public Ollama registry yet; if a
# tag is missing we fall back to the gemma3n variants that exist today rather
# than blindly pulling a 404.
pull_variant() {  # $1 = preferred tag, $2 = fallback tag
    pref="$1"; fb="$2"
    if ollama show "$pref" >/dev/null 2>&1; then
        say "Pulling $pref"; ollama pull "$pref"
    elif ollama pull "$pref" >/dev/null 2>&1; then
        say "Pulled $pref"
    else
        warn "$pref is not available on this Ollama registry."
        warn "Falling back to $fb (exists today). Update the catalog tag when gemma4 ships."
        ollama pull "$fb"
    fi
}
say "2/5  Pulling small Gemma variants (E2B fast, E4B reasoning/coding)"
pull_variant "gemma4:e2b" "gemma3n:e2b"
pull_variant "gemma4:e4b" "gemma3n:e4b"
# NB: 26B / 31B are intentionally NOT pulled — they don't fit an 8 GB box.

# --- 3. write the free-first / local-only routing policy -------------------
# No --force: this writes model_policy.json only; the manual pulls above are
# the (tag-guarded) download step. The 8 GB hardware fit excludes 26B/31B.
say "3/5  Writing the free-first, local-only routing policy"
$JP bootstrap --free-first --jarvis --local-only

# --- 4. arm the load-gate via the E4B smoke check --------------------------
# Records whether E4B loads cleanly. If it OOMs, the router automatically routes
# the coding/reasoning lanes to E2B instead — no manual pin needed.
say "4/5  Smoke-testing E4B (arms the 'loads cleanly' gate)"
$JP gemma smoke --variant gemma4-e4b || \
    warn "E4B did not load cleanly — coding/reasoning lanes will use E2B (by design)."

# --- 5. show the resulting routes ------------------------------------------
say "5/5  Resulting Gemma status + per-lane routes"
$JP gemma status || true
for lane in mobile_chat voice_reply summarization memory_curator \
            coding_plan coding_build coding_review test_debug \
            research citation_verification; do
    $JP route --task "$lane" 2>/dev/null | sed -n '1,3p' || true
done

cat <<'NOTE'

Done. The policy + load-gate now route by job weight automatically.

Optional, owner-gated pins (only if you want a lane FIXED regardless of the
load-gate — note this bypasses the "loads cleanly" fallback):

  python -m muse_cli.jarvis_prime -c ignored 2>/dev/null  # (pins via Python:)
  python - <<'PY'
  from muse_cli.jarvis_prime import task_router as tr
  tr.set_task_override("mobile_chat", "ollama-local/gemma4-e2b")
  # clear with: tr.set_task_override("mobile_chat", None)
  PY

Re-run `python -m muse_cli.jarvis_prime gemma smoke --variant gemma4-e4b`
any time you change hardware to refresh the load-gate.
NOTE
