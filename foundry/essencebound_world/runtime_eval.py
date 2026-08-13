"""Measured stock-versus-tuned evaluation and fail-closed rung promotion gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .evaluation import domain_gate, evaluate_domain
from .pipeline import refresh_manifest

PRODUCTION_POOLS = ("test", "qa", "holdout")
DEFAULT_WORKERS = 24


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_prediction_cache(
    *, evaluation_dir: Path, current_rows: Path, weights: Path, label: str
) -> dict[str, Any] | None:
    """Return complete predictions only when rows and model bytes are identical."""
    cached_rows = evaluation_dir / "evaluation_rows.jsonl"
    cached_predictions = evaluation_dir / f"{label}_predictions.json"
    if not cached_rows.is_file() or not cached_predictions.is_file() or not weights.is_file():
        return None
    if cached_rows.read_bytes() != current_rows.read_bytes():
        return None
    payload = json.loads(cached_predictions.read_text(encoding="utf-8"))
    predictions = payload.get("predictions", [])
    if (
        payload.get("status") != "COMPLETE"
        or payload.get("errors")
        or payload.get("weights_sha256") != _sha256(weights)
        or payload.get("n") != len(predictions)
        or payload.get("n") != len(_read_jsonl(current_rows))
    ):
        return None
    return payload


def find_verified_prediction_cache(
    *, runs_root: Path, current_run: Path, current_rows: Path, weights: Path, label: str
) -> tuple[dict[str, Any], Path] | None:
    """Find the newest prior run with byte-identical rows and model weights."""
    current_run = current_run.resolve()
    for candidate in sorted(runs_root.glob("run_[0-9][0-9][0-9]"), reverse=True):
        if candidate.resolve() == current_run:
            continue
        evaluation_dir = candidate / "evaluation"
        payload = load_verified_prediction_cache(
            evaluation_dir=evaluation_dir,
            current_rows=current_rows,
            weights=weights,
            label=label,
        )
        if payload is not None:
            return payload, evaluation_dir
    return None


def build_eval_command(
    *, repo_root: Path, weights: Path, rows: Path, schemas: Path, output: Path
) -> list[str]:
    """Build a worker command containing exactly one model path."""
    return [
        str(Path(sys.executable)),
        "-m",
        "foundry.essencebound_world.inference_worker",
        "--weights", str(weights),
        "--rows", str(rows),
        "--schemas", str(schemas),
        "--output", str(output),
    ]


def shard_rows(rows: list[dict[str, Any]], workers: int) -> list[list[dict[str, Any]]]:
    """Split rows into stable, balanced, contiguous worker shards."""
    if workers < 1:
        raise ValueError("workers must be positive")
    count = min(workers, max(1, len(rows)))
    quotient, remainder = divmod(len(rows), count)
    shards = []
    offset = 0
    for index in range(count):
        size = quotient + int(index < remainder)
        shards.append(rows[offset : offset + size])
        offset += size
    return shards


def _run_worker(command: list[str], log_path: Path, timeout_s: int = 1800) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            exit_code = process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = -1
            log.write("evaluation worker timed out\n")
    return {
        "command": command,
        "exit_code": exit_code,
        "duration_s": round(time.monotonic() - started, 3),
        "log": str(log_path),
    }


def _evaluate_model_sharded(
    *,
    label: str,
    weights: Path,
    bundle: list[dict[str, Any]],
    evaluation_dir: Path,
    schemas: Path,
    repo_root: Path,
    workers: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    jobs = []
    for index, shard in enumerate(shard_rows(bundle, workers), start=1):
        rows_path = evaluation_dir / "shards" / f"rows_{index:02d}.jsonl"
        output_path = evaluation_dir / "shards" / f"{label}_{index:02d}.json"
        _write_jsonl(rows_path, shard)
        command = build_eval_command(
            repo_root=repo_root,
            weights=weights,
            rows=rows_path,
            schemas=schemas,
            output=output_path,
        )
        jobs.append((index, command, output_path, evaluation_dir / "shards" / f"{label}_{index:02d}.log"))

    reports: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {
            index: pool.submit(_run_worker, command, log_path)
            for index, command, _output_path, log_path in jobs
        }
        for index, _command, output_path, _log_path in jobs:
            report = futures[index].result()
            reports[str(index)] = report
            if report["exit_code"] != 0 or not output_path.is_file():
                return {"status": "FAILED", "shards": reports}, None

    predictions = []
    errors = []
    duration_s = 0.0
    weight_hash = None
    for index, _command, output_path, _log_path in jobs:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        predictions.extend(payload.get("predictions", []))
        errors.extend(payload.get("errors", []))
        duration_s = max(duration_s, float(payload.get("duration_s", 0.0)))
        weight_hash = weight_hash or payload.get("weights_sha256")
    merged = {
        "status": "COMPLETE" if not errors and len(predictions) == len(bundle) else "COMPLETE_WITH_ERRORS",
        "engine_version": "2.0.0",
        "weights": str(weights.resolve()),
        "weights_sha256": weight_hash,
        "n": len(predictions),
        "duration_s": round(duration_s, 3),
        "worker_count": len(jobs),
        "errors": errors,
        "predictions": predictions,
    }
    _write_json(evaluation_dir / f"{label}_predictions.json", merged)
    return {"status": merged["status"], "shards": reports, "worker_count": len(jobs)}, merged


def summarize_rung_evaluation(pools: dict[str, dict[str, list[dict]]]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for name, values in pools.items():
        stock_metrics = evaluate_domain(values["golds"], values["stock"])
        tuned_metrics = evaluate_domain(values["golds"], values["tuned"])
        reports[name] = {
            "n": len(values["golds"]),
            "stock_metrics": stock_metrics,
            "tuned_metrics": tuned_metrics,
            "gate": domain_gate(tuned_metrics, baseline=stock_metrics),
        }
    missing = [name for name in PRODUCTION_POOLS if name not in reports]
    all_pass = not missing and all(reports[name]["gate"]["ALL_PASS"] for name in PRODUCTION_POOLS)
    return {
        "all_pass": all_pass,
        "status": "PASSED" if all_pass else "FAILED",
        "production_pools": list(PRODUCTION_POOLS),
        "missing_production_pools": missing,
        "pools": reports,
    }


def record_training_evaluation(run_dir: Path | str, result: dict[str, Any]) -> dict[str, Any]:
    """Attach the measured terminal evaluation state to the training result."""
    run_dir = Path(run_dir).resolve()
    path = run_dir / "training_result.json"
    training = json.loads(path.read_text(encoding="utf-8"))
    if result.get("status") == "UNVERIFIED":
        status = "EVALUATION_UNVERIFIED"
    else:
        status = "EVALUATED_GATE_PASSED" if result.get("all_pass") else "EVALUATED_GATE_FAILED"
    training["status"] = status
    training["evaluation"] = {
        "status": result.get("status"),
        "all_pass": result.get("all_pass") is True,
        "gate": str(run_dir / "evaluation" / "gate.json"),
    }
    _write_json(path, training)
    return training


def _latest_run(root: Path, rung: int) -> Path:
    runs = sorted((root / f"rung_{rung:04d}" / "runs").glob("run_[0-9][0-9][0-9]"))
    valid = [path for path in runs if (path / "model.cact").is_file()]
    if not valid:
        raise FileNotFoundError(f"no trained model found for rung {rung}")
    return valid[-1]


def evaluate_rung(
    *, root: Path | str, repo_root: Path | str, rung: int,
    run_dir: Path | str | None = None, workers: int = DEFAULT_WORKERS,
) -> dict[str, Any]:
    root = Path(root).resolve()
    repo_root = Path(repo_root).resolve()
    run_dir = Path(run_dir).resolve() if run_dir else _latest_run(root, rung)
    evaluation_dir = run_dir / "evaluation"
    sources = {
        "validation": root / f"rung_{rung:04d}" / "validation.jsonl",
        "test": root / f"rung_{rung:04d}" / "test.jsonl",
        "qa": root / "qa" / f"qa_{rung:04d}.jsonl",
        "holdout": root / "holdout" / "needle_eb_world_holdout.jsonl",
    }
    golds: dict[str, list[dict[str, Any]]] = {}
    bundle: list[dict[str, Any]] = []
    for pool, source in sources.items():
        golds[pool] = _read_jsonl(source)
        for row in golds[pool]:
            bundle.append({**row, "evaluation_pool": pool})
    bundle_path = evaluation_dir / "evaluation_rows.jsonl"
    _write_jsonl(bundle_path, bundle)

    models = {
        "stock": repo_root / "third_party" / "needle" / "foundry_test" / "needle2_plain_reexport.cact",
        "tuned": run_dir / "model.cact",
    }
    worker_reports = {}
    outputs = {}
    schemas = root / "source" / "tool_schemas.json"
    for label, weights in models.items():
        cached = None
        if label == "stock":
            cached = find_verified_prediction_cache(
                runs_root=run_dir.parent,
                current_run=run_dir,
                current_rows=bundle_path,
                weights=weights,
                label=label,
            )
        if cached is not None:
            output, source = cached
            output = {
                **output,
                "cache_provenance": {
                    "status": "REUSED_VERIFIED_CACHE",
                    "source": str(source.resolve()),
                    "rows_sha256": _sha256(bundle_path),
                },
            }
            _write_json(evaluation_dir / f"{label}_predictions.json", output)
            worker_reports[label] = {
                "status": "REUSED_VERIFIED_CACHE",
                "source": str(source.resolve()),
                "worker_count": 0,
            }
            outputs[label] = output
            continue
        worker_reports[label], output = _evaluate_model_sharded(
            label=label,
            weights=weights,
            bundle=bundle,
            evaluation_dir=evaluation_dir,
            schemas=schemas,
            repo_root=repo_root,
            workers=workers,
        )
        if output is None:
            result = {
                "rung": rung,
                "run_dir": str(run_dir),
                "status": "UNVERIFIED",
                "all_pass": False,
                "reason": f"{label}_worker_failed",
                "workers": worker_reports,
            }
            _write_json(evaluation_dir / "gate.json", result)
            record_training_evaluation(run_dir, result)
            _persist_gate_result(root, rung, result)
            return result
        outputs[label] = output
        if outputs[label].get("errors") or outputs[label].get("n") != len(bundle):
            result = {
                "rung": rung,
                "run_dir": str(run_dir),
                "status": "UNVERIFIED",
                "all_pass": False,
                "reason": f"{label}_worker_incomplete",
                "workers": worker_reports,
            }
            _write_json(evaluation_dir / "gate.json", result)
            record_training_evaluation(run_dir, result)
            _persist_gate_result(root, rung, result)
            return result

    grouped: dict[str, dict[str, list[dict]]] = {}
    for pool in sources:
        grouped[pool] = {
            "golds": golds[pool],
            "stock": [item for item in outputs["stock"]["predictions"] if item["evaluation_pool"] == pool],
            "tuned": [item for item in outputs["tuned"]["predictions"] if item["evaluation_pool"] == pool],
        }
    summary = summarize_rung_evaluation(grouped)
    summary.update(
        {
            "rung": rung,
            "run_dir": str(run_dir),
            "workers": worker_reports,
            "model_artifact": outputs["tuned"]["weights"],
            "model_sha256": outputs["tuned"]["weights_sha256"],
            "stock_artifact": outputs["stock"]["weights"],
            "stock_sha256": outputs["stock"]["weights_sha256"],
        }
    )
    _write_json(evaluation_dir / "metrics.json", summary["pools"])
    _write_json(evaluation_dir / "gate.json", summary)
    record_training_evaluation(run_dir, summary)
    _persist_gate_result(root, rung, summary)
    return summary


def _persist_gate_result(root: Path, rung: int, result: dict[str, Any]) -> None:
    path = root / "reports" / "gate_results.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"rungs": {}}
    current.setdefault("rungs", {})[str(rung)] = result
    current["highest_attempted_rung"] = rung
    current["winning_rung"] = rung if result.get("all_pass") else None
    current["status"] = "PASSED" if result.get("all_pass") else "STOPPED_GATE_FAILED"
    _write_json(path, current)
    refresh_manifest(root)
