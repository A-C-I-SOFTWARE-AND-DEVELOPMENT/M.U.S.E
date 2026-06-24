#!/usr/bin/env bash
# Phase 6 owner script — Termux/aarch64 port of the template fast path.
#
# Run ON THE PHONE inside Termux, from the repo root. Targets a 1-3B Gemma
# GGUF (+ optional 270M draft). Verifies, in order: GBNF grammar sampling,
# prompt-cache reuse, then speculative decoding ONLY if the measured memory
# budget allows both models + KV. If RAM-bound, speculative decoding is
# dropped FIRST; grammar + prompt-cache stay.
#
# Usage:
#   scripts/templates_fastpath/phase6_termux.sh /path/gemma-2b-q4.gguf [draft-270m.gguf]
set -euo pipefail

MODEL="${1:?usage: phase6_termux.sh <gemma-1-3b.gguf> [draft-270m.gguf]}"
DRAFT="${2:-}"
REPORT="hermes_cli/jarvis_prime/bench/phase_reports.md"

echo "== Phase 6: Termux preflight =="
# 1. Toolchain + build llama.cpp natively if no binary yet.
if ! command -v llama-server >/dev/null 2>&1 && [ -z "${LLAMA_BIN:-}" ]; then
  echo "building llama.cpp (one-time)…"
  pkg install -y cmake clang git python >/dev/null
  git clone --depth 1 https://github.com/ggml-org/llama.cpp /tmp/llamacpp
  cmake -B /tmp/llamacpp/build -S /tmp/llamacpp -DLLAMA_CURL=OFF -DGGML_NATIVE=ON \
        -DCMAKE_BUILD_TYPE=Release
  cmake --build /tmp/llamacpp/build --target llama-server llama-bench -j"$(nproc)"
  export LLAMA_BIN=/tmp/llamacpp/build/bin
fi
BENCH="${LLAMA_BIN:+$LLAMA_BIN/}llama-bench"

# 2. Python deps (numpy via the Termux constraints file; NO torch/MiniLM on
#    device — the hashed embedding backend is the designed-in answer).
python3 -c "import numpy" 2>/dev/null || \
  python3 -m pip install numpy -c constraints-termux.txt

# 3. Measured memory budget table (target + draft + KV per slot <= device).
DEVICE_MB=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
MODEL_MB=$(( $(stat -c %s "$MODEL") / 1048576 ))
DRAFT_MB=0; [ -n "$DRAFT" ] && DRAFT_MB=$(( $(stat -c %s "$DRAFT") / 1048576 ))
SLOTS=2
KV_MB=$(( 64 * SLOTS ))   # c=2048 estimate; refine from llama-server logs
NEED_MB=$(( MODEL_MB + DRAFT_MB + KV_MB + 256 ))  # +256MB runtime overhead
{
  echo ""
  echo "## Phase 6 — Termux device run ($(date -u +%Y-%m-%dT%H:%M:%SZ), $(uname -m))"
  echo ""
  echo "| component | MB |"
  echo "|---|---|"
  echo "| device MemAvailable | ${DEVICE_MB} |"
  echo "| target model | ${MODEL_MB} |"
  echo "| draft model | ${DRAFT_MB} |"
  echo "| KV (${SLOTS} slots, est.) | ${KV_MB} |"
  echo "| total needed | ${NEED_MB} |"
} | tee -a "$REPORT"

USE_DRAFT=""
if [ -n "$DRAFT" ] && [ "$NEED_MB" -lt "$DEVICE_MB" ]; then
  USE_DRAFT="$DRAFT"
  echo "speculative decoding: ENABLED (fits budget)" | tee -a "$REPORT"
else
  echo "speculative decoding: DROPPED (RAM-bound rule — grammar + prompt-cache kept)" \
    | tee -a "$REPORT"
fi

# 4. Device baseline, then the same fast-path bench as the laptop (it starts
#    and owns its llama-server; gate: >=20% latency win + parse rate >= base).
"$BENCH" -m "$MODEL" -p 256 -n 64 -t "$(nproc)" | tee -a "$REPORT"
export MUSE_TEMPLATES_DIR="${MUSE_TEMPLATES_DIR:-$PWD/hermes_cli/jarvis_prime/templates}"
PORT="${PORT:-8097}" bash scripts/templates_fastpath/phase3_bench.sh "$MODEL" ${USE_DRAFT:+"$USE_DRAFT"}

echo "Done — device numbers appended to $REPORT. Rollback: MUSE_TEMPLATES=0 on device."
