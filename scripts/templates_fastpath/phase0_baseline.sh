#!/usr/bin/env bash
# Phase 0 owner script — real-Gemma baseline numbers (laptop).
#
# Produces the MEASURED rows that are DEFERRED in
# hermes_cli/jarvis_prime/bench/phase_reports.md: llama-bench tok/s per Gemma
# GGUF, the prompt-cache probe on the real model (Gemma SWA bug #21468 check),
# and Ollama-runner latency over the fixture prompts.
#
# Usage:
#   scripts/templates_fastpath/phase0_baseline.sh /path/to/gemma.gguf [more.gguf ...]
# Requires: a llama.cpp checkout built with llama-bench + llama-server on PATH
# (or set LLAMA_BIN=/path/to/llama.cpp/build/bin), and optionally a local
# Ollama install with a gemma model for the runner-latency section.
set -euo pipefail

LLAMA_BIN="${LLAMA_BIN:-}"
THREADS="${THREADS:-$(nproc --all 2>/dev/null || sysctl -n hw.physicalcpu 2>/dev/null || echo 4)}"
REPORT="hermes_cli/jarvis_prime/bench/phase_reports.md"
bench() { "${LLAMA_BIN:+$LLAMA_BIN/}llama-bench" "$@"; }
server() { "${LLAMA_BIN:+$LLAMA_BIN/}llama-server" "$@"; }

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <gemma.gguf> [more.gguf ...]" >&2
  exit 2
fi

echo "## Phase 0 — REAL Gemma baseline ($(date -u +%Y-%m-%dT%H:%M:%SZ), $(uname -ms), ${THREADS} threads)" | tee -a "$REPORT"
echo "" | tee -a "$REPORT"

echo "### llama-bench (pp512 / tg128)" | tee -a "$REPORT"
for MODEL in "$@"; do
  echo "" | tee -a "$REPORT"
  echo "Model: \`$MODEL\`" | tee -a "$REPORT"
  echo '```' >> "$REPORT"
  bench -m "$MODEL" -p 512 -n 128 -t "$THREADS" | tee -a "$REPORT"
  echo '```' >> "$REPORT"
done

echo "" | tee -a "$REPORT"
echo "### Prompt-cache probe (Gemma SWA bug #21468 check)" | tee -a "$REPORT"
MODEL="$1"
KV_DIR="$(mktemp -d)"
PORT=8093
# First without --swa-full; rerun with it if reuse fails (cache_n stays 0).
for SWA_FLAG in "" "--swa-full"; do
  server -m "$MODEL" -c 4096 -np 2 --slot-save-path "$KV_DIR" --cache-reuse 256 \
    --port "$PORT" --host 127.0.0.1 ${SWA_FLAG} >/dev/null 2>&1 &
  SRV=$!
  for _ in $(seq 1 60); do
    curl -s --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
    sleep 1
  done
  PREFIX="$(python3 -c "print('You are muse a careful assistant. ' * 30)")"
  probe() {
    curl -s "http://127.0.0.1:${PORT}/completion" -d "{\"prompt\": \"${PREFIX} $1\", \
\"n_predict\": 8, \"id_slot\": 0, \"cache_prompt\": true, \"temperature\": 0}" \
      | python3 -c "import json,sys; d=json.load(sys.stdin); t=d.get('timings',{}); \
print(f\"prompt_n={t.get('prompt_n')} tokens_cached={d.get('tokens_cached')} prompt_ms={t.get('prompt_ms')}\")"
  }
  R1="$(probe 'Task A')"; R2="$(probe 'Task B')"
  kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true
  echo "- swa_flag='${SWA_FLAG:-none}': req1 ${R1} | req2 ${R2}" | tee -a "$REPORT"
  # Reuse works when req2 prompt_n is small (only the divergent suffix).
  if echo "$R2" | grep -qE "prompt_n=[0-9]{1,2} "; then
    echo "  cache reuse OK${SWA_FLAG:+ (with ${SWA_FLAG})}" | tee -a "$REPORT"
    break
  fi
done

echo "" | tee -a "$REPORT"
echo "### Ollama Gemma runner latency (fixture prompts)" | tee -a "$REPORT"
if command -v ollama >/dev/null 2>&1; then
  HERMES_JARVIS_GEMMA_AUTO_RUNNER=1 python3 - <<'EOF' | tee -a "$REPORT"
from hermes_cli.jarvis_prime.bench.baseline import measure_runner
from hermes_cli.jarvis_prime.bench.corpus import build_corpus
from hermes_cli.jarvis_prime.gemma_runner import build_gemma_runner

runner = build_gemma_runner()
if runner is None:
    print("no Gemma model installed in Ollama — section skipped")
else:
    prompts = sorted({r.prompt for r in build_corpus(max_per_domain=2)})[:6]
    report = measure_runner(runner, prompts, label="ollama-gemma baseline")
    print("| runner | prompts | mean | p95 |")
    print("|---|---|---|---|")
    print(report.to_markdown_row())
EOF
else
  echo "ollama not installed — section skipped" | tee -a "$REPORT"
fi

echo ""
echo "Phase 0 real-baseline sections appended to $REPORT"
