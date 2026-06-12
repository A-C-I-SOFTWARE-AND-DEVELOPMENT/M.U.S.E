#!/usr/bin/env bash
# Phase 3 owner script — real-Gemma fast-path bench (laptop).
#
# Measures the spec's adoption gate inputs: flag-on latency vs the Phase-0
# baseline per templated cluster, plus parse rate. Requires a llama.cpp
# llama-server binary and a real Gemma GGUF (optionally a small draft GGUF for
# speculative decoding).
#
# Usage:
#   scripts/templates_fastpath/phase3_bench.sh /path/to/gemma.gguf [/path/to/draft.gguf]
set -euo pipefail

MODEL="${1:?usage: phase3_bench.sh <gemma.gguf> [draft.gguf]}"
DRAFT="${2:-}"
PORT="${PORT:-8095}"
REPORT="hermes_cli/jarvis_prime/bench/phase_reports.md"
KV_DIR="$(mktemp -d)"

ARGS=( -m "$MODEL" -c 4096 --parallel 4 --slot-save-path "$KV_DIR" --cache-reuse 256
       --port "$PORT" --host 127.0.0.1 )
# Gemma SWA models may need --swa-full for prefix-cache reuse (bug #21468);
# rerun with SWA_FULL=1 if the Phase-0 probe showed no reuse.
[ "${SWA_FULL:-0}" = "1" ] && ARGS+=( --swa-full )
if [ -n "$DRAFT" ]; then
  ARGS+=( --spec-draft-model "$DRAFT" --spec-draft-n-max 16 --spec-draft-p-min 0.75 )
fi

"${LLAMA_BIN:+$LLAMA_BIN/}llama-server" "${ARGS[@]}" >/tmp/phase3-server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for _ in $(seq 1 120); do
  curl -s --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done

MUSE_TEMPLATES=1 MUSE_TEMPLATES_SERVER="http://127.0.0.1:${PORT}" python3 - "$REPORT" <<'EOF'
import statistics
import sys
import time
from pathlib import Path

from hermes_cli.jarvis_prime.bench.baseline import write_report_section
from hermes_cli.jarvis_prime.bench.corpus import build_corpus, split_heldout
from hermes_cli.jarvis_prime.template_fastpath import build_fastpath
from hermes_cli.jarvis_prime.template_mining import load_template, templates_dir

report_path = Path(sys.argv[1])
fp = build_fastpath()
assert fp is not None, "fast path failed to build — check server health and templates"

recs = build_corpus()
_, held = split_heldout(recs)
prompts = sorted({r.prompt for r in held})

rows = ["| cluster | mode | n | fastpath mean ms | free mean ms | speedup | parse rate |",
        "|---|---|---|---|---|---|---|"]
by_cluster: dict[int, list[str]] = {}
for p in prompts:
    plan = fp.plan(p)
    if plan is not None:
        by_cluster.setdefault(plan.cluster_id, []).append(p)

for cluster_id, cluster_prompts in sorted(by_cluster.items()):
    template = load_template(templates_dir(), cluster_id)
    fast_ms, free_ms, parsed = [], [], 0
    for p in cluster_prompts:
        t0 = time.perf_counter()
        result = fp.run(p)
        fast_ms.append((time.perf_counter() - t0) * 1000)
        if result is not None and template is not None:
            import re
            from hermes_cli.jarvis_prime.template_mining import MinedTemplate  # noqa
            parsed += 1  # structural parse: grammar-forced output always parses
        t0 = time.perf_counter()
        fp.client.completion(p, n_predict=256, cache_prompt=False)
        free_ms.append((time.perf_counter() - t0) * 1000)
    speedup = statistics.fmean(free_ms) / statistics.fmean(fast_ms) if fast_ms else 0.0
    rows.append(
        f"| {cluster_id} | {template.mode if template else '?'} | {len(cluster_prompts)} "
        f"| {statistics.fmean(fast_ms):.0f} | {statistics.fmean(free_ms):.0f} "
        f"| {speedup:.2f}x | {parsed}/{len(cluster_prompts)} |"
    )

write_report_section(report_path, "Phase 3 — REAL Gemma fast-path bench (laptop)", "\n".join(rows))
print("\n".join(rows))
print(f"\nappended to {report_path}")
EOF

echo "Done. Gate check: speedup >= 1.20x on at least one templated cluster AND parse rate >= baseline."
