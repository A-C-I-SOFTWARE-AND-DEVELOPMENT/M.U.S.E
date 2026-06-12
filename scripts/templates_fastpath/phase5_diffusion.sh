#!/usr/bin/env bash
# Phase 5 owner script — EXPERIMENTAL diffusion lane (laptop ONLY).
#
# Never touches gemma_runner defaults. Requires a Dream-7B or LLaDA-8B GGUF
# (owner-acquired; HF was network-blocked in the build container) and a
# llama.cpp build with the llama-diffusion-cli target.
#
# Usage:
#   scripts/templates_fastpath/phase5_diffusion.sh /path/to/dream7b.gguf          # Dream
#   BLOCK_LENGTH=32 scripts/templates_fastpath/phase5_diffusion.sh llada-8b.gguf  # LLaDA
set -euo pipefail

MODEL="${1:?usage: phase5_diffusion.sh <diffusion-model.gguf>}"
BLOCK_LENGTH="${BLOCK_LENGTH:-0}"
REPORT="hermes_cli/jarvis_prime/bench/phase_reports.md"

python3 - "$MODEL" "$BLOCK_LENGTH" "$REPORT" <<'EOF'
import sys
from pathlib import Path

from hermes_cli.jarvis_prime.bench.baseline import write_report_section
from hermes_cli.jarvis_prime.bench.corpus import build_corpus, split_heldout
from hermes_cli.jarvis_prime.bench.diffusion_lane import comparison_table, run_diffusion_probe

model, block_length, report_path = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
_, held = split_heldout(build_corpus())
prompts = sorted({r.prompt for r in held})[:4]

probe = run_diffusion_probe(
    model_path=model,
    prompts=prompts,
    block_length=block_length or None,
)
# AR fast-path reference latency: paste the measured Phase-3 number, or rerun
# phase3_bench.sh first. 0 disables the ratio column.
ar_latency_s = float(__import__("os").environ.get("AR_FASTPATH_LATENCY_S", "0") or 0)
table = comparison_table(probe, ar_latency_s)
write_report_section(
    report_path,
    "Phase 5 — EXPERIMENTAL diffusion lane (laptop, not gated, not adopted)",
    table,
)
print(table)
EOF
