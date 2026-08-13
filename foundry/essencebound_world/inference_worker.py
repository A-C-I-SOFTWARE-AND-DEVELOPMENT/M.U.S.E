"""Isolated one-model Needle inference worker used by measured evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from needle import Needle, __version__ as needle_version
from needle import _lib as _needle_lib


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _load_agent(weights: Path, schemas: list[dict[str, Any]], system: str) -> Needle:
    """Load weights while retaining their backing bytes for the native engine lifetime."""
    blob = weights.read_bytes()
    if _needle_lib().needle_load(blob, len(blob)) != 0:
        raise RuntimeError(f"failed to load weights from {weights}")
    agent = Needle(tools=schemas, system=system)
    agent._weights_blob = blob  # The 2.0.0 engine retains this backing pointer.
    return agent


def run_worker(*, weights: Path, rows: Path, schemas: Path, output: Path) -> dict[str, Any]:
    eval_rows = _read_jsonl(rows)
    tool_schemas = json.loads(schemas.read_text(encoding="utf-8"))
    system = eval_rows[0].get("system", "") if eval_rows else ""
    agent = _load_agent(weights, tool_schemas, system)
    predictions = []
    errors = []
    started = time.monotonic()
    for index, row in enumerate(eval_rows, start=1):
        agent.reset()
        item_started = time.monotonic()
        try:
            # Gold targets top out at 102 tokens; 128 preserves headroom while
            # preventing malformed non-EOS generations from burning a full 256.
            response = agent.complete(row["query"], max_new_tokens=128)
            predictions.append(
                {
                    "id": row["id"],
                    "evaluation_pool": row["evaluation_pool"],
                    "query": row["query"],
                    "function_calls": response.get("function_calls") or [],
                    "confidence": response.get("confidence"),
                    "type": response.get("type"),
                    "text": response.get("text"),
                    "latency_s": round(time.monotonic() - item_started, 4),
                }
            )
        except Exception as exc:  # Persist every failed row; the caller fails closed.
            errors.append({"id": row.get("id"), "error": type(exc).__name__, "message": str(exc)})
            predictions.append(
                {
                    "id": row.get("id"),
                    "evaluation_pool": row.get("evaluation_pool"),
                    "query": row.get("query"),
                    "function_calls": [],
                    "error": type(exc).__name__,
                    "latency_s": round(time.monotonic() - item_started, 4),
                }
            )
        if index % 10 == 0 or index == len(eval_rows):
            print(json.dumps({"progress": index, "total": len(eval_rows), "errors": len(errors)}), flush=True)
    result = {
        "status": "COMPLETE" if not errors else "COMPLETE_WITH_ERRORS",
        "engine_version": needle_version,
        "weights": str(weights.resolve()),
        "weights_sha256": _sha256(weights),
        "rows": str(rows.resolve()),
        "n": len(eval_rows),
        "duration_s": round(time.monotonic() - started, 3),
        "errors": errors,
        "predictions": predictions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--schemas", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_worker(weights=args.weights, rows=args.rows, schemas=args.schemas, output=args.output)
    print(json.dumps({key: result[key] for key in ("status", "n", "duration_s", "weights_sha256")}), flush=True)
    return 0 if result["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
