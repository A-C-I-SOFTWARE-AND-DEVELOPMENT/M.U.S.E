"""Dataset engine — provenance, validation, dedupe, partitioning (§16–19).

Every example carries provenance; every row is schema-validated before it can
enter a training set; paraphrase-sibling leakage across train/eval is blocked
by clustering on normalized output structure.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

REQUIRED_KEYS = ("query", "answers")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class Provenance:
    example_id: str
    specialist_id: str
    schema_version: str
    prompt_hash: str
    teacher_provider: str
    teacher_model: str
    generation_timestamp: float = field(default_factory=time.time)
    validation_version: str = "1"
    semantic_category: str = "positive"
    negative_class: str = ""
    dedupe_cluster: str = ""
    review_state: str = "auto"


def normalize_query(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def dedupe_key(example: dict) -> str:
    answers = example.get("answers", [])
    return _hash(normalize_query(example.get("query", ""))
                 + "|" + json.dumps(answers, sort_keys=True))


def output_cluster(example: dict) -> str:
    """Paraphrase-sibling cluster: same tool calls, ignoring query wording."""
    answers = example.get("answers", [])
    return _hash(json.dumps(answers, sort_keys=True))


def validate_row(example: dict, tool_names: set[str]) -> list[str]:
    """Schema-level validation. Returns a list of violations (empty = valid)."""
    errs = []
    if "query" not in example or not isinstance(example["query"], str):
        errs.append("missing_query")
    answers = example.get("answers")
    if not isinstance(answers, list):
        errs.append("answers_not_list")
        return errs
    for a in answers:
        if not isinstance(a, dict) or "name" not in a:
            errs.append("answer_missing_name")
            continue
        if a["name"] not in tool_names:
            errs.append(f"unknown_tool:{a['name']}")
        if not isinstance(a.get("arguments", {}), dict):
            errs.append(f"arguments_not_object:{a['name']}")
    return errs


def build_dataset(
    rows: Iterable[dict],
    *,
    specialist_id: str,
    schema_version: str,
    tool_names: set[str],
    teacher_provider: str,
    teacher_model: str,
    eval_fraction: float = 0.1,
) -> dict[str, Any]:
    """Validate, dedupe, cluster, and partition rows. Returns the dataset
    manifest; raises nothing — invalid rows are quarantined with reasons."""
    valid, quarantined = [], []
    seen_keys: dict[str, int] = {}
    for i, row in enumerate(rows):
        errs = validate_row(row, tool_names)
        if errs:
            quarantined.append({"row": i, "errors": errs, "query": str(row.get("query"))[:80]})
            continue
        key = dedupe_key(row)
        if key in seen_keys:
            quarantined.append({"row": i, "errors": ["exact_duplicate"], "of": seen_keys[key]})
            continue
        seen_keys[key] = i
        cluster = output_cluster(row)
        row["_provenance"] = asdict(Provenance(
            example_id=_hash(f"{specialist_id}:{i}:{key}")[:16],
            specialist_id=specialist_id,
            schema_version=schema_version,
            prompt_hash=_hash(normalize_query(row["query"])),
            teacher_provider=teacher_provider,
            teacher_model=teacher_model,
            semantic_category=row.get("semantic_category", "positive" if row.get("answers") else "negative"),
            negative_class=row.get("negative_class", ""),
            dedupe_cluster=cluster,
        ))
        valid.append(row)

    # Cluster-safe partition: all siblings of one output-cluster stay together.
    clusters: dict[str, list[int]] = {}
    for i, row in enumerate(valid):
        clusters.setdefault(row["_provenance"]["dedupe_cluster"], []).append(i)

    cluster_list = sorted(clusters.values(), key=lambda c: (len(c), c[0]))
    n_eval = max(1, round(len(valid) * eval_fraction))
    eval_idx: set[int] = set()
    for c in reversed(cluster_list):  # largest clusters first for coverage
        if len(eval_idx) >= n_eval:
            break
        eval_idx.update(c)

    train = [r for i, r in enumerate(valid) if i not in eval_idx]
    eval_ = [r for i, r in enumerate(valid) if i in eval_idx]
    manifest = {
        "specialist_id": specialist_id,
        "schema_version": schema_version,
        "created_at": time.time(),
        "counts": {
            "input_rows": len(list(rows)) if not isinstance(rows, list) else len(rows),
            "valid": len(valid),
            "quarantined": len(quarantined),
            "train": len(train),
            "eval": len(eval_),
        },
        "dataset_hash": _hash(json.dumps([dedupe_key(r) for r in valid])),
        "quarantine": quarantined,
    }
    return {"manifest": manifest, "train": train, "eval": eval_}


def write_jsonl(rows: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h
