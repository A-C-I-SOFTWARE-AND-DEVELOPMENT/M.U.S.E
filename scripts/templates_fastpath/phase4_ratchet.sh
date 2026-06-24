#!/usr/bin/env bash
# Phase 4 owner script — LIVE ratchet adoption run (laptop).
#
# Scores template-ON (challenger) vs template-OFF (champion) on the held-out
# suite through research_fabric's 8-condition ratchet. On PASS it freezes the
# challenger with this checkout's git sha as the rollback handle (SnapshotStore
# + GuardrailLedger). On FAIL it queues a structured improvement entry and
# stops. Thresholds are never modified.
#
# Prereqs: Ollama with a Gemma model installed (the champion), and a llama.cpp
# llama-server + real Gemma GGUF for the challenger's fast path.
#
# Usage:
#   scripts/templates_fastpath/phase4_ratchet.sh /path/to/gemma.gguf [draft.gguf]
set -euo pipefail

MODEL="${1:?usage: phase4_ratchet.sh <gemma.gguf> [draft.gguf]}"
DRAFT="${2:-}"
PORT="${PORT:-8096}"
KV_DIR="$(mktemp -d)"

ARGS=( -m "$MODEL" -c 4096 --parallel 4 --slot-save-path "$KV_DIR" --cache-reuse 256
       --port "$PORT" --host 127.0.0.1 )
[ "${SWA_FULL:-0}" = "1" ] && ARGS+=( --swa-full )
[ -n "$DRAFT" ] && ARGS+=( --spec-draft-model "$DRAFT" --spec-draft-n-max 16 --spec-draft-p-min 0.75 )

"${LLAMA_BIN:+$LLAMA_BIN/}llama-server" "${ARGS[@]}" >/tmp/phase4-server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do
  curl -s --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done

HERMES_JARVIS_GEMMA_AUTO_RUNNER=1 \
MUSE_TEMPLATES_SERVER="http://127.0.0.1:${PORT}" \
python3 -m hermes_cli.jarvis_prime.bench.ratchet_run \
  --rollback-handle "$(git rev-parse HEAD)"

echo ""
echo "If PASSED+frozen: the promotion is recorded in SnapshotStore + GuardrailLedger;"
echo "the MUSE_TEMPLATES=1 default-flip proposal in bench/phase_reports.md now awaits"
echo "the owner's exact 'Yes, with authorization.'"
echo "If FAILED: see \$HERMES_HOME/flywheel/improvement_queue.jsonl — do not lower bars."
