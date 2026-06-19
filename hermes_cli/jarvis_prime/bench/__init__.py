"""Bench harness for the cluster-based token template fast path.

Phase-gated benchmarking, corpus building, and ratchet adoption tooling for the
``muse_TEMPLATES`` fast path (see ``bench/phase_reports.md`` for measured
results and deviations). Everything here is offline and deterministic; real
model latency/quality numbers are produced by the owner scripts under
``scripts/templates_fastpath/``.
"""
