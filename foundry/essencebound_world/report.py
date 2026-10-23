"""Measured final report and conditional Foundry registration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from foundry.registry import FoundryRegistry, SpecialistRecord

from .evaluation import DOMAIN_GATES
from .pipeline import refresh_manifest

SPECIALIST = "needle-eb-world-architect"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def registry_decision(
    *, gate: dict[str, Any], registry_path: Path, lineage: dict[str, Any]
) -> dict[str, Any]:
    """Register in the existing Foundry format only after every production gate passes."""
    if gate.get("all_pass") is not True:
        return {"status": "UNREGISTERED_GATE_FAILED", "content_id": None, "path": None}
    required = (
        "base_hash", "engine_hash", "tokenizer_hash", "schema_hash", "dataset_hash",
        "adapter_hash", "final_model_hash", "eval_report_hash", "training_config_hash",
    )
    missing = [field for field in required if not lineage.get(field)]
    if missing:
        return {
            "status": "NOT_REGISTERED_LINEAGE_INCOMPLETE",
            "content_id": None,
            "path": None,
            "missing": missing,
        }
    record = SpecialistRecord(
        specialist_id=SPECIALIST,
        niche_id="essencebound-world",
        specialist_version=str(lineage["specialist_version"]),
        status="CANDIDATE",
        base_revision="needle2-engine-2.0.0",
        base_hash=lineage["base_hash"],
        engine_hash=lineage["engine_hash"],
        tokenizer_hash=lineage["tokenizer_hash"],
        schema_hash=lineage["schema_hash"],
        dataset_hash=lineage["dataset_hash"],
        adapter_hash=lineage["adapter_hash"],
        final_model_hash=lineage["final_model_hash"],
        eval_report_hash=lineage["eval_report_hash"],
        training_config_hash=lineage["training_config_hash"],
        metrics=lineage.get("metrics", {}),
        thresholds=DOMAIN_GATES,
        provider_lineage=["Cactus-Compute/needle2", "MUSE Foundry"],
    )
    record.transition("ACTIVE", "all Essencebound production gates passed")
    content_id = FoundryRegistry(registry_path).register(record)
    return {"status": "REGISTERED_ACTIVE", "content_id": content_id, "path": str(registry_path)}


def diagnose_gate_failure(gate: dict[str, Any]) -> dict[str, Any]:
    """Turn measured gate misses into a bounded next-training diagnosis."""
    if gate.get("all_pass") is True:
        return {"status": "NO_FAILURE", "failed_metrics": [], "critical_failures": []}
    failed = []
    critical = []
    for pool, value in gate.get("pools", {}).items():
        stock = value.get("stock_metrics", {})
        tuned = value.get("tuned_metrics", {})
        for metric, result in value.get("gate", {}).items():
            if metric == "ALL_PASS" or result.get("passed") is not False:
                continue
            failed.append(
                {
                    "pool": pool,
                    "metric": metric,
                    "tuned_value": result.get("value"),
                    "gate": result.get("gate"),
                    "stock_value": stock.get(metric),
                }
            )
        for instance in tuned.get("critical_failures", []):
            critical.append({"pool": pool, **instance})
    return {
        "status": "STOPPED_AT_FAILED_GATE",
        "failed_metrics": failed,
        "critical_failures": critical,
        "next_action": (
            "Keep the ladder at the current rung. Add targeted, semantically distinct examples "
            "for the measured misses, retrain a new run at this rung, and repeat every gate."
        ),
    }


def _pool_result(gate: dict[str, Any], pool: str) -> dict[str, Any]:
    value = gate.get("pools", {}).get(pool)
    if not value:
        return {"status": "UNVERIFIED", "n": 0}
    tuned = value["tuned_metrics"]
    stock = value["stock_metrics"]
    return {
        "status": "PASSED" if value["gate"]["ALL_PASS"] else "FAILED",
        "n": value["n"],
        "tuned_exact_accuracy": tuned["exact_accuracy"],
        "stock_exact_accuracy": stock["exact_accuracy"],
        "tuned_verdict_accuracy": tuned["verdict_accuracy"],
        "tuned_category_accuracy": tuned["category_accuracy"],
        "critical_failure_count": tuned["critical_failure_count"],
    }


def _markdown(report: dict[str, Any]) -> str:
    fields = (
        "SPECIALIST", "DATASET RUNG", "TRAIN EXAMPLES", "VALIDATION EXAMPLES",
        "TEST EXAMPLES", "QA EXAMPLES", "CATEGORY COVERAGE", "DUPLICATE RATE",
        "TRAINING RESULT", "CORE EVAL RESULT", "QA RESULT", "HOLDOUT RESULT",
        "GATE STATUS", "MODEL ARTIFACT", "REGISTRY STATUS",
    )
    lines = ["# Essencebound World Architect Final Report", ""]
    for field in fields:
        value = report[field]
        rendered = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"- **{field}:** {rendered}")
    lines.append("")
    return "\n".join(lines)


def build_final_report(
    root: Path | str, *, rung: int | None = None, registry_path: Path | str | None = None
) -> dict[str, Any]:
    root = Path(root).resolve()
    gates_path = root / "reports" / "gate_results.json"
    gate_results = json.loads(gates_path.read_text(encoding="utf-8"))
    rung = rung or int(gate_results["highest_attempted_rung"])
    gate = gate_results.get("rungs", {}).get(str(rung), {})
    run_dir = Path(gate.get("run_dir", "")) if gate.get("run_dir") else None
    if run_dir is None or not run_dir.is_dir():
        candidates = sorted((root / f"rung_{rung:04d}" / "runs").glob("run_[0-9][0-9][0-9]"))
        if not candidates:
            raise FileNotFoundError(f"no run directory for rung {rung}")
        run_dir = candidates[-1]
    training_path = run_dir / "training_result.json"
    training = json.loads(training_path.read_text(encoding="utf-8"))
    stats = json.loads((root / "reports" / "dataset_stats.json").read_text(encoding="utf-8"))
    coverage = json.loads((root / "reports" / "coverage.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    covered = sum(1 for counts in coverage["categories"].values() if counts.get(str(rung), 0) > 0)
    total_categories = len(coverage["categories"])
    eval_path = run_dir / "evaluation" / "gate.json"
    config_path = run_dir / "training_config.json"
    model_path = run_dir / "model.cact"
    adapter_path = run_dir / "adapter.pkl"
    preflight = json.loads((root / "reports" / "training_preflight.json").read_text(encoding="utf-8"))
    artifacts = preflight["static"]["artifacts"]
    lineage = {
        "specialist_version": f"rung-{rung:04d}",
        "base_hash": _sha256(Path(artifacts["checkpoint"])),
        "engine_hash": _sha256(Path(artifacts["engine"])),
        "tokenizer_hash": _sha256(Path(artifacts["tokenizer"])),
        "schema_hash": _sha256(root / "source" / "tool_schemas.json"),
        "dataset_hash": manifest["dataset_hash"],
        "adapter_hash": _sha256(adapter_path),
        "final_model_hash": _sha256(model_path),
        "eval_report_hash": _sha256(eval_path),
        "training_config_hash": _sha256(config_path),
        "metrics": {name: value.get("tuned_metrics", {}) for name, value in gate.get("pools", {}).items()},
    }
    registry_path = Path(registry_path).resolve() if registry_path else root.parent / "foundry_registry.json"
    registry = registry_decision(gate=gate, registry_path=registry_path, lineage=lineage)
    diagnosis = diagnose_gate_failure(gate)
    report = {
        "SPECIALIST": SPECIALIST,
        "DATASET RUNG": rung,
        "TRAIN EXAMPLES": _line_count(root / f"rung_{rung:04d}" / "train.jsonl"),
        "VALIDATION EXAMPLES": _line_count(root / f"rung_{rung:04d}" / "validation.jsonl"),
        "TEST EXAMPLES": _line_count(root / f"rung_{rung:04d}" / "test.jsonl"),
        "QA EXAMPLES": _line_count(root / "qa" / f"qa_{rung:04d}.jsonl"),
        "CATEGORY COVERAGE": {"covered": covered, "total": total_categories},
        "DUPLICATE RATE": stats["duplicate_rate"],
        "TRAINING RESULT": {
            "status": training["status"],
            "first_loss": training.get("losses", {}).get("first"),
            "final_loss": training.get("losses", {}).get("last"),
            "finite": training.get("losses", {}).get("finite"),
        },
        "CORE EVAL RESULT": _pool_result(gate, "test"),
        "QA RESULT": _pool_result(gate, "qa"),
        "HOLDOUT RESULT": _pool_result(gate, "holdout"),
        "GATE STATUS": gate_results.get("status", gate.get("status", "UNVERIFIED")),
        "MODEL ARTIFACT": {
            "path": str(model_path),
            "sha256": lineage["final_model_hash"],
            "bytes": model_path.stat().st_size,
        },
        "REGISTRY STATUS": registry,
        "FAILURE DIAGNOSIS": diagnosis,
    }
    reports = root / "reports"
    (reports / "final_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (reports / "FINAL_REPORT.md").write_text(_markdown(report), encoding="utf-8", newline="\n")
    (run_dir / "evaluation" / "diagnosis.json").write_text(
        json.dumps(diagnosis, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    refresh_manifest(root)
    return report
