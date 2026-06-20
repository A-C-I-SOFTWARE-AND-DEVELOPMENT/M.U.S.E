#!/usr/bin/env python3
"""Generate the bundled demo snapshot for the statically-hosted Observatory.

The Neural Observatory web viewer (``gateway/cockpit/static/observatory.*``) is
a pure client-side SPA that normally fetches ``/v1/observatory/*`` from a live
gateway. To host it 24/7 as a static GitHub Pages site (no backend), the viewer
has an opt-in "demo" mode that reads a *bundled, clearly-labeled* snapshot
instead. This script produces that snapshot.

Honesty: the cluster *structure* is authentic — real M.U.S.E. area labels,
positioned with the SAME ``gateway.cockpit.observatory_layout_engine`` the live
page uses — but the telemetry numbers are illustrative and FROZEN. The page
shows a prominent "DEMO - static snapshot, not live" badge. Nothing here is
presented as live measurement.

Run:  python3 scripts/build_observatory_demo.py
Out:  gateway/cockpit/static/observatory-demo.json
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from gateway.cockpit import observatory_layout_engine as ole

GRAPH_VERSION = "g-demo-20260620"
OUT = pathlib.Path("gateway/cockpit/static/observatory-demo.json")

# (label, members, type_mix, heat)  - real M.U.S.E. areas; heat None = below the
# n>=5 confidence gate (renders cool-gray, never a guessed glow).
AREAS: list[tuple[str, int, dict[str, float], float | None]] = [
    ("gateway/cockpit", 412, {"code": 0.82, "docs": 0.18}, 0.61),
    ("hermes_cli/jarvis_prime", 524, {"code": 0.88, "docs": 0.12}, 0.74),
    ("hermes_cli/jarvis_prime/graphrag", 263, {"code": 0.9, "docs": 0.1}, 0.43),
    ("axiom/core", 188, {"code": 0.93, "docs": 0.07}, 0.55),
    ("axiom/orchestrator", 156, {"code": 0.91, "docs": 0.09}, None),
    ("plugins/memory", 142, {"code": 0.86, "docs": 0.14}, 0.29),
    ("plugins/github_assistant", 98, {"code": 0.84, "docs": 0.16}, None),
    ("plugins/model_providers", 167, {"code": 0.89, "docs": 0.11}, 0.34),
    ("second_brain", 211, {"code": 0.7, "docs": 0.3}, 0.22),
    ("apps/android", 305, {"code": 0.95, "docs": 0.05}, 0.48),
    ("apps/synapse-ue", 134, {"code": 0.97, "docs": 0.03}, None),
    ("docs/synapse", 86, {"docs": 1.0}, None),
    ("docs/orchestration", 73, {"docs": 1.0}, 0.18),
    ("skills/aos-enterprise-council", 261, {"docs": 0.88, "code": 0.12}, 0.39),
    ("run_agent.py core", 240, {"code": 1.0}, 0.66),
    ("model_tools", 132, {"code": 1.0}, 0.41),
    ("gateway/messaging", 178, {"code": 0.92, "docs": 0.08}, 0.27),
    ("tui_gateway", 64, {"code": 0.96, "docs": 0.04}, None),
    ("providers", 91, {"code": 0.94, "docs": 0.06}, 0.2),
    ("cron", 47, {"code": 0.9, "docs": 0.1}, None),
    ("orchestration/ledger", 119, {"code": 0.85, "docs": 0.15}, 0.52),
    ("memory tree", 95, {"docs": 0.6, "code": 0.4}, 0.31),
]

# (src-label, dst-label, weight) - plausible dependency / provenance edges.
LINKS: list[tuple[str, str, float]] = [
    ("gateway/cockpit", "hermes_cli/jarvis_prime", 9.0),
    ("hermes_cli/jarvis_prime", "hermes_cli/jarvis_prime/graphrag", 7.0),
    ("hermes_cli/jarvis_prime", "axiom/core", 6.0),
    ("axiom/core", "axiom/orchestrator", 8.0),
    ("axiom/orchestrator", "orchestration/ledger", 5.0),
    ("hermes_cli/jarvis_prime", "plugins/memory", 4.0),
    ("plugins/memory", "memory tree", 6.0),
    ("hermes_cli/jarvis_prime", "plugins/model_providers", 5.0),
    ("plugins/model_providers", "providers", 4.0),
    ("gateway/cockpit", "gateway/messaging", 5.0),
    ("run_agent.py core", "model_tools", 7.0),
    ("run_agent.py core", "hermes_cli/jarvis_prime", 6.0),
    ("apps/android", "gateway/cockpit", 4.0),
    ("apps/synapse-ue", "gateway/cockpit", 3.0),
    ("docs/synapse", "apps/synapse-ue", 3.0),
    ("skills/aos-enterprise-council", "hermes_cli/jarvis_prime", 4.0),
    ("second_brain", "hermes_cli/jarvis_prime/graphrag", 5.0),
    ("docs/orchestration", "axiom/orchestrator", 3.0),
    ("gateway/cockpit", "tui_gateway", 3.0),
    ("hermes_cli/jarvis_prime", "cron", 2.0),
    ("graphrag", "second_brain", 2.0),
    ("orchestration/ledger", "gateway/cockpit", 4.0),
]


def cid(label: str) -> str:
    return "c-" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]


def build_snapshot() -> dict:
    clusters = [{"id": cid(lbl), "members": m} for (lbl, m, _, _) in AREAS]
    by_label = {lbl: cid(lbl) for (lbl, _, _, _) in AREAS}
    edges = [
        {"a": by_label[a], "b": by_label[b], "weight": w}
        for (a, b, w) in LINKS
        if a in by_label and b in by_label
    ]
    pos = ole.super_layout(clusters, edges, ole.seed_from(GRAPH_VERSION))

    cluster_out = []
    for lbl, members, mix, heat in AREAS:
        i = cid(lbl)
        p = pos.get(i)
        cluster_out.append(
            {
                "id": i,
                "label": lbl,
                "type_mix": mix,
                "members": members,
                "pos": list(p) if p else None,
                "radius": ole.cluster_radius(members),
                "heat": heat,
            }
        )

    edge_out = []
    for k, (a, b, w) in enumerate(LINKS):
        if a in by_label and b in by_label:
            edge_out.append(
                {
                    "a": by_label[a],
                    "b": by_label[b],
                    "weight": w,
                    "heat": round(0.2 + (k % 5) * 0.12, 2) if k % 3 == 0 else None,
                }
            )

    metrics = build_metrics()
    return {
        "v": 1,
        "generated_at": "2026-06-20T18:00:00Z",
        "graph": {
            "graph_version": GRAPH_VERSION,
            "node_count": sum(m for (_, m, _, _) in AREAS),
            "edge_count": len(edge_out) * 37,
            "clusters": cluster_out,
            "cluster_edges": edge_out,
            "clusters_total": len(cluster_out),
            "clusters_truncated": False,
            "layout_status": "computed",
            "layout_algo": ole.layout_algo(),
        },
        "stations": {
            "nodes": ["job", "navigator", "worker", "gate", "ledger"],
            "active_jobs": [
                {
                    "job_id": "jb-7f3a2e",
                    "task_class": "code",
                    "stage": "worker",
                    "stage_entered_at": "2026-06-20T17:59:51Z",
                    "queue_pos": None,
                },
                {
                    "job_id": "jb-91c4d0",
                    "task_class": "docs",
                    "stage": "gate",
                    "stage_entered_at": "2026-06-20T17:59:58Z",
                    "queue_pos": None,
                },
                {
                    "job_id": "jb-2b8e15",
                    "task_class": "research",
                    "stage": "navigator",
                    "stage_entered_at": "2026-06-20T18:00:00Z",
                    "queue_pos": 1,
                },
            ],
            "queue_depth": 1,
        },
        "ladder": {
            "tiers": [
                {
                    "tier": "local",
                    "model": "qwen2.5-coder-7b",
                    "share_1h": 0.58,
                    "n": 742,
                    "p50_latency_ms": 410,
                    "p95_latency_ms": 980,
                },
                {
                    "tier": "hosted",
                    "model": "claude-sonnet-4-6",
                    "share_1h": 0.31,
                    "n": 396,
                    "p50_latency_ms": 1180,
                    "p95_latency_ms": 3200,
                },
                {
                    "tier": "paired",
                    "model": "gpt-4o",
                    "share_1h": 0.11,
                    "n": 141,
                    "p50_latency_ms": 1520,
                    "p95_latency_ms": 4100,
                },
            ]
        },
        "metrics_rollup": metrics,
    }


def build_metrics() -> dict:
    return {
        "v": 1,
        "window": "1h",
        "from": "2026-06-20T17:00:00Z",
        "to": "2026-06-20T18:00:00Z",
        "stages": [
            {"stage": "perceive", "task_class": None, "count": 1279, "p50_ms": 12, "p95_ms": 48, "queue_wait_p95_ms": 5, "retries": 0},
            {"stage": "classify", "task_class": None, "count": 1279, "p50_ms": 34, "p95_ms": 120, "queue_wait_p95_ms": 8, "retries": 2},
            {"stage": "decide", "task_class": None, "count": 1188, "p50_ms": 410, "p95_ms": 1900, "queue_wait_p95_ms": 30, "retries": 11},
            {"stage": "gate", "task_class": None, "count": 1188, "p50_ms": 58, "p95_ms": 240, "queue_wait_p95_ms": 12, "retries": 4},
            {"stage": "delegate", "task_class": None, "count": 1042, "p50_ms": 880, "p95_ms": 3400, "queue_wait_p95_ms": 140, "retries": 9},
            {"stage": "speak", "task_class": None, "count": 1042, "p50_ms": 220, "p95_ms": 900, "queue_wait_p95_ms": 7, "retries": 1},
        ],
        "gates": [
            {"gate": "planning", "task_class": None, "passes": 1150, "fails": 38, "overrides": 0, "fail_rate": 0.032},
            {"gate": "build", "task_class": None, "passes": 1102, "fails": 86, "overrides": 0, "fail_rate": 0.072},
            {"gate": "review", "task_class": None, "passes": 1064, "fails": 124, "overrides": 3, "fail_rate": 0.104},
            {"gate": "test", "task_class": None, "passes": 998, "fails": 190, "overrides": 0, "fail_rate": 0.16},
            {"gate": "security", "task_class": None, "passes": 1181, "fails": 7, "overrides": 0, "fail_rate": 0.006},
            {"gate": "release", "task_class": None, "passes": 1042, "fails": 0, "overrides": 0, "fail_rate": 0.0},
            {"gate": "owner", "task_class": None, "passes": 64, "fails": 0, "overrides": 0, "fail_rate": 0.0},
            {"gate": "rollback", "task_class": None, "passes": 1042, "fails": 0, "overrides": 0, "fail_rate": 0.0},
        ],
        "models": [
            {"tier": "local", "model": "qwen2.5-coder-7b", "calls": 742, "p95_latency_ms": 980, "tokens_in": 1284000, "tokens_out": 318000, "est_cost_usd": 0.0},
            {"tier": "hosted", "model": "claude-sonnet-4-6", "calls": 396, "p95_latency_ms": 3200, "tokens_in": 902000, "tokens_out": 241000, "est_cost_usd": 4.81},
            {"tier": "paired", "model": "gpt-4o", "calls": 141, "p95_latency_ms": 4100, "tokens_in": 388000, "tokens_out": 96000, "est_cost_usd": 2.34},
        ],
        "cost_per_task_class": [
            {"task_class": "code", "usd": 4.12, "n": 612},
            {"task_class": "research", "usd": 2.05, "n": 188},
            {"task_class": "docs", "usd": 0.98, "n": 242},
        ],
        "heat": [
            {"key": "stage:delegate:code", "score": 0.81, "n": 612, "evidence_ref": "/v1/cockpit/ledger?stage=delegate&class=code"},
            {"key": "gate:test:code", "score": 0.64, "n": 190, "evidence_ref": "/v1/cockpit/ledger?gate=test&class=code"},
            {"key": "stage:decide:research", "score": 0.47, "n": 188, "evidence_ref": "/v1/cockpit/ledger?stage=decide&class=research"},
            {"key": "gate:review:docs", "score": None, "n": 3, "evidence_ref": "/v1/cockpit/ledger?gate=review&class=docs"},
        ],
        "heat_weights": {"latency": 0.3, "queue": 0.2, "fail": 0.25, "retry": 0.15, "cost": 0.1},
        "min_n": 5,
        "collector": {"events_in_window": 8421, "events_recorded": 8421, "io_errors": 0},
    }


def build_layouts() -> dict:
    """Member expansions (local space) for a couple of clusters."""
    layouts: dict[str, dict] = {}
    samples = [
        ("hermes_cli/jarvis_prime", ["run_agent", "system_contract", "router", "memory_tree", "graph_query", "modes", "constitution", "self_audit", "learning", "persona", "gates", "speak"]),
        ("axiom/core", ["verifier", "ledger", "canonical", "registry", "contracts", "effects", "merkle", "attestation"]),
    ]
    for label, names in samples:
        i = cid(label)
        nodes = [{"id": f"{i}-n{k}", "degree": max(1, 12 - k)} for k in range(len(names))]
        edges = [{"a": nodes[0]["id"], "b": nodes[k]["id"], "weight": 1.0} for k in range(1, len(names))]
        pos = ole.member_layout(nodes, edges, (0.0, 0.0, 0.0), ole.cluster_radius(len(names) * 12), ole.seed_from(GRAPH_VERSION, i))
        layouts[i] = {
            "v": 1,
            "cluster": i,
            "graph_version": GRAPH_VERSION,
            "layout_status": "computed",
            "layout_algo": ole.member_layout_algo(),
            "truncated": False,
            "nodes": [
                {
                    "id": nodes[k]["id"],
                    "type": "function" if k % 2 == 0 else "class",
                    "label": names[k],
                    "pos": list(pos.get(nodes[k]["id"], (0.0, 0.0, 0.0))),
                    "degree": nodes[k]["degree"],
                    "heat": round(0.15 + (k % 4) * 0.18, 2) if k % 2 == 0 else None,
                    "source_ref": f"{label}/{names[k]}.py",
                }
                for k in range(len(names))
            ],
            "edges": [{"a": e["a"], "b": e["b"], "weight": e["weight"]} for e in edges],
        }
    return layouts


def build_recommendations() -> dict:
    return {
        "v": 1,
        "generated_at": "2026-06-20T18:00:00Z",
        "cards": [
            {
                "id": "rec-route-local-code",
                "title": "Route short code edits to the local tier",
                "state": "validated",
                "delta": "-18% median latency",
                "validation": {
                    "method": "replay",
                    "n_baseline": 240,
                    "n_candidate": 240,
                    "median_delta_pct": -18.4,
                    "ci95": [-23.1, -12.9],
                    "metric": "latency_ms",
                },
                "evidence_refs": ["/v1/cockpit/ledger?stage=delegate&class=code"],
                "created_at": "2026-06-20T17:42:00Z",
            },
            {
                "id": "rec-test-gate-retries",
                "title": "Pre-warm the test gate for the code class",
                "state": "collecting",
                "delta": None,
                "validation": {
                    "method": "shadow",
                    "n_baseline": 31,
                    "n_candidate": 0,
                    "median_delta_pct": None,
                    "ci95": None,
                    "metric": "retries",
                },
                "evidence_refs": [],
                "created_at": "2026-06-20T17:55:00Z",
            },
        ],
    }


def main() -> int:
    payload = {
        "_demo": True,
        "_note": "Static, illustrative snapshot for the always-on hosted viewer. "
        "Structure is authentic (real M.U.S.E. areas, real layout engine); "
        "telemetry numbers are frozen samples, NOT live measurement.",
        "generated_by": "scripts/build_observatory_demo.py",
        "snapshot": build_snapshot(),
        "recommendations": build_recommendations(),
        "layouts": build_layouts(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    snap = payload["snapshot"]
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  clusters={len(snap['graph']['clusters'])} edges={len(snap['graph']['cluster_edges'])} "
          f"layouts={len(payload['layouts'])} cards={len(payload['recommendations']['cards'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
