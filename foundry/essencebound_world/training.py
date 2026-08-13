"""Verified WSL2/JAX training and export runner for Essencebound rungs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

WSL_DISTRO = "Ubuntu"
WSL_NEEDLE = "/root/needle_gpu_probe/.venv/bin/needle"
WSL_PYTHON = "/root/needle_gpu_probe/.venv/bin/python"
BASE_CHECKPOINT_HASH = "4b0a972d163ffc7678fb3c36bace508114872e9d2ce9e10f225825752d3795bc"
TOKENIZER_HASH = "0871b8e3df78e0dd7ccc236e187fc055f75cd57ebe3bec76ca8103030b8fe659"

_LOSS_RE = re.compile(
    r"\bloss\s+(nan|[-+]?inf|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def to_wsl_path(path: Path | str) -> str:
    """Convert an absolute Windows path into the standard WSL `/mnt/<drive>` path."""
    value = str(Path(path).resolve())
    drive, tail = os.path.splitdrive(value)
    if not drive:
        raise ValueError(f"WSL conversion requires an absolute drive path: {value}")
    normalized_tail = tail.lstrip("\\/").replace("\\", "/")
    return f"/mnt/{drive[0].casefold()}/{normalized_tail}"


def build_train_command(
    *,
    root: Path,
    repo_root: Path,
    rung: int,
    run_dir: Path,
    epochs: int,
    batch_size: int,
    lr: float,
    lora_rank: int,
) -> list[str]:
    train_file = root / f"rung_{rung:04d}" / "train.jsonl"
    checkpoint = repo_root / "third_party" / "needle" / "checkpoints" / "needle2.pkl"
    return [
        "wsl.exe", "-d", WSL_DISTRO, "--", WSL_NEEDLE, "finetune",
        to_wsl_path(train_file),
        "--epochs", str(epochs),
        "--batch-size", str(batch_size),
        "--lr", f"{lr:g}",
        "--lora-rank", str(lora_rank),
        "--max-len", "2048",
        "--checkpoint", to_wsl_path(checkpoint),
        "--checkpoint-dir", to_wsl_path(run_dir / "checkpoints"),
        "--out", to_wsl_path(run_dir / "adapter.pkl"),
    ]


def build_export_command(*, repo_root: Path, run_dir: Path) -> list[str]:
    checkpoint = repo_root / "third_party" / "needle" / "checkpoints" / "needle2.pkl"
    return [
        "wsl.exe", "-d", WSL_DISTRO, "--", WSL_NEEDLE, "build",
        to_wsl_path(checkpoint),
        "--lora", to_wsl_path(run_dir / "adapter.pkl"),
        "--out", to_wsl_path(run_dir / "model.cact"),
        "--bits", "2",
    ]


def parse_training_losses(log_text: str) -> dict[str, Any]:
    values = []
    for match in _LOSS_RE.finditer(log_text):
        token = match.group(1).casefold()
        values.append(float(token))
    finite = bool(values) and all(math.isfinite(value) for value in values)
    return {
        "values": values,
        "finite": finite,
        "first": values[0] if values else None,
        "last": values[-1] if values else None,
    }


def static_preflight(root: Path | str, repo_root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    repo_root = Path(repo_root).resolve()
    checkpoint = repo_root / "third_party" / "needle" / "checkpoints" / "needle2.pkl"
    tokenizer = repo_root / "third_party" / "needle" / "needle" / "model" / "tokenizer.model"
    finetune = repo_root / "third_party" / "needle" / "needle" / "model" / "finetune.py"
    stock_model = repo_root / "third_party" / "needle" / "foundry_test" / "needle2_plain_reexport.cact"
    engine = Path.home() / ".cache" / "cactus-needle" / "2.0.0" / "libneedle.dll"
    checks = {
        "dataset_validation": (
            root / "reports" / "dataset_validation.json"
        ).is_file(),
        "checkpoint": checkpoint.is_file(),
        "checkpoint_hash": checkpoint.is_file() and _sha256(checkpoint) == BASE_CHECKPOINT_HASH,
        "tokenizer": tokenizer.is_file(),
        "tokenizer_hash": tokenizer.is_file() and _sha256(tokenizer) == TOKENIZER_HASH,
        "f32_lora_patch": finetune.is_file() and "MUSE-FOUNDRY FIX" in finetune.read_text(encoding="utf-8"),
        "stock_engine_model": stock_model.is_file(),
        "engine_2_0_0": engine.is_file(),
        "disk_free_5gb": shutil.disk_usage(root).free >= 5 * 1024**3,
    }
    if checks["dataset_validation"]:
        persisted = json.loads(
            (root / "reports" / "dataset_validation.json").read_text(encoding="utf-8")
        )
        checks["dataset_validation"] = persisted.get("passed") is True
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "artifacts": {
            "checkpoint": str(checkpoint),
            "tokenizer": str(tokenizer),
            "stock_model": str(stock_model),
            "engine": str(engine),
        },
    }


def has_cuda_device(devices: list[str]) -> bool:
    return any("cuda" in device.casefold() for device in devices)


def probe_wsl_gpu(timeout_s: int = 180) -> dict[str, Any]:
    command = [
        "wsl.exe", "-d", WSL_DISTRO, "--", WSL_PYTHON, "-c",
        "import json,jax; print(json.dumps({'jax':jax.__version__,'devices':[str(x) for x in jax.devices()]}))",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "passed": False,
            "command": command,
            "duration_s": round(time.monotonic() - started, 3),
            "error": "timeout",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    output = completed.stdout.strip().splitlines()
    payload = {}
    if output:
        try:
            payload = json.loads(output[-1])
        except json.JSONDecodeError:
            payload = {}
    devices = payload.get("devices", [])
    return {
        "passed": completed.returncode == 0 and has_cuda_device(devices),
        "command": command,
        "duration_s": round(time.monotonic() - started, 3),
        "exit_code": completed.returncode,
        "jax": payload.get("jax"),
        "devices": devices,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def training_preflight(root: Path | str, repo_root: Path | str) -> dict[str, Any]:
    static = static_preflight(root, repo_root)
    gpu = probe_wsl_gpu() if static["passed"] else {"passed": False, "skipped": True}
    report = {"passed": static["passed"] and gpu["passed"], "static": static, "wsl_gpu": gpu}
    _write_json(Path(root).resolve() / "reports" / "training_preflight.json", report)
    return report


def _run_logged(command: list[str], log_path: Path) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    chunks: list[str] = []
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
            chunks.append(line)
        exit_code = process.wait()
    return {
        "command": command,
        "exit_code": exit_code,
        "duration_s": round(time.monotonic() - started, 3),
        "log": str(log_path),
        "text": "".join(chunks),
    }


def next_run_dir(root: Path | str, rung: int) -> Path:
    base = Path(root).resolve() / f"rung_{rung:04d}" / "runs"
    base.mkdir(parents=True, exist_ok=True)
    existing = [int(path.name.split("_")[-1]) for path in base.glob("run_[0-9][0-9][0-9]")]
    return base / f"run_{(max(existing, default=0) + 1):03d}"


def run_training(
    *,
    root: Path | str,
    repo_root: Path | str,
    rung: int,
    epochs: int = 1,
    batch_size: int = 8,
    lr: float = 1e-4,
    lora_rank: int = 16,
) -> dict[str, Any]:
    root = Path(root).resolve()
    repo_root = Path(repo_root).resolve()
    run_dir = next_run_dir(root, rung)
    run_dir.mkdir(parents=True)
    config = {
        "rung": rung,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "lora_rank": lora_rank,
        "max_len": 2048,
        "quantization_bits": 2,
    }
    _write_json(run_dir / "training_config.json", config)
    train_command = build_train_command(
        root=root,
        repo_root=repo_root,
        rung=rung,
        run_dir=run_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        lora_rank=lora_rank,
    )
    training = _run_logged(train_command, run_dir / "training.log")
    losses = parse_training_losses(training.pop("text"))
    adapter = run_dir / "adapter.pkl"
    result: dict[str, Any] = {
        "status": "FAILED",
        "run_dir": str(run_dir),
        "config": config,
        "training": training,
        "losses": losses,
    }
    if training["exit_code"] != 0 or not losses["finite"] or not adapter.is_file():
        result["reason"] = "training_process_or_loss_failed"
        _write_json(run_dir / "training_result.json", result)
        return result

    export_command = build_export_command(repo_root=repo_root, run_dir=run_dir)
    export = _run_logged(export_command, run_dir / "export.log")
    export.pop("text")
    model = run_dir / "model.cact"
    result["export"] = export
    if export["exit_code"] != 0 or not model.is_file():
        result["reason"] = "export_failed"
        _write_json(run_dir / "training_result.json", result)
        return result

    result.update(
        {
            "status": "TRAINED_UNEVALUATED",
            "adapter": {"path": str(adapter), "sha256": _sha256(adapter), "bytes": adapter.stat().st_size},
            "model": {"path": str(model), "sha256": _sha256(model), "bytes": model.stat().st_size},
        }
    )
    _write_json(run_dir / "training_result.json", result)
    return result
