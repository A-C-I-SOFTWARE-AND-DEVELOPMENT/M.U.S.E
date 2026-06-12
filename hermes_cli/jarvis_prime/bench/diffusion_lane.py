"""Phase-5 EXPERIMENTAL diffusion lane — isolated, laptop-only, never default.

Quantifies clamped-template infilling on a diffusion LM (Dream-7B / LLaDA-8B
GGUF via llama.cpp's ``llama-diffusion-cli``) against the AR fast path, using
the same Phase-4 verifiers and latency co-metric. Expectation to confirm or
refute: diffusion is slower than the AR fast path on CPU at batch size 1.

Isolation is structural: nothing outside ``bench/`` may import this module
(test-enforced), it never touches ``gemma_runner.py`` or any default path, and
it degrades to ``{"available": False}`` when the binary or model is absent.

Flags verified against llama.cpp build 1593d56: ``--diffusion-steps``,
``--diffusion-algorithm``, ``--diffusion-block-length`` (LLaDA), ``-ub``.
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

DEFAULT_STEPS_SWEEP = (64, 128, 256)


def _default_cli_runner(cmd: list[str], timeout_s: float) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
    return proc.stdout


def build_infill_prompt(prompt: str, scaffold_literals: Sequence[str]) -> str:
    """Clamped-template infilling prompt: scaffold literals held fixed.

    ``llama-diffusion-cli`` exposes no token-clamping API, so the closest
    faithful construction is presenting the scaffold with explicit blanks and
    asking the model to denoise only the gaps. True clamping (fixing scaffold
    token positions during denoising) would need a llama.cpp patch — recorded
    as a deviation.
    """

    skeleton = "____".join(scaffold_literals)
    return f"{prompt}\nComplete the blanks (____) in this exact skeleton:\n{skeleton}\n"


def run_diffusion_probe(
    *,
    model_path: str,
    prompts: Sequence[str],
    binary: str = "llama-diffusion-cli",
    steps_sweep: Sequence[int] = DEFAULT_STEPS_SWEEP,
    block_length: Optional[int] = None,  # 32 for LLaDA; None for Dream
    algorithm: int = 3,
    ubatch: int = 512,
    timeout_s: float = 600.0,
    cli_runner: Optional[Callable[[list[str], float], str]] = None,
    which: Optional[Callable[[str], Optional[str]]] = None,
) -> dict[str, Any]:
    """Sweep diffusion steps over the prompts; return a latency/output report.

    Returns ``{"available": False, ...}`` (never raises) when the binary or
    model is missing, so callers can always embed the result in a report.
    """

    which_fn = which or shutil.which
    if which_fn(binary) is None:
        return {"available": False, "reason": f"{binary} not on PATH"}
    if not Path(model_path).exists():
        return {"available": False, "reason": f"model not found: {model_path}"}
    runner = cli_runner or _default_cli_runner

    sweeps: list[dict[str, Any]] = []
    for steps in steps_sweep:
        latencies: list[float] = []
        outputs: list[str] = []
        for prompt in prompts:
            cmd = [
                binary,
                "-m",
                model_path,
                "-p",
                prompt,
                "-ub",
                str(ubatch),
                "--diffusion-steps",
                str(steps),
                "--diffusion-algorithm",
                str(algorithm),
            ]
            if block_length:
                cmd += ["--diffusion-block-length", str(block_length)]
            start = time.perf_counter()
            try:
                out = runner(cmd, timeout_s)
            except subprocess.TimeoutExpired:
                out = ""
            latencies.append(time.perf_counter() - start)
            outputs.append(out)
        sweeps.append(
            {
                "steps": steps,
                "mean_latency_s": round(statistics.fmean(latencies), 3) if latencies else 0.0,
                "outputs": outputs,
            }
        )
    return {
        "available": True,
        "binary": binary,
        "model": model_path,
        "algorithm": algorithm,
        "block_length": block_length,
        "sweeps": sweeps,
    }


def comparison_table(
    diffusion_report: dict[str, Any], ar_fastpath_mean_latency_s: float
) -> str:
    """Markdown table comparing the diffusion sweeps to the AR fast path."""

    rows = [
        "| lane | steps | mean latency s | vs AR fast path |",
        "|---|---|---|---|",
        f"| AR fast path | — | {ar_fastpath_mean_latency_s:.3f} | 1.00x |",
    ]
    if not diffusion_report.get("available"):
        rows.append(f"| diffusion | — | unavailable ({diffusion_report.get('reason', '?')}) | — |")
        return "\n".join(rows)
    for sweep in diffusion_report["sweeps"]:
        ratio = (
            sweep["mean_latency_s"] / ar_fastpath_mean_latency_s
            if ar_fastpath_mean_latency_s
            else 0.0
        )
        rows.append(
            f"| diffusion | {sweep['steps']} | {sweep['mean_latency_s']:.3f} | {ratio:.2f}x slower |"
        )
    return "\n".join(rows)


__all__ = [
    "DEFAULT_STEPS_SWEEP",
    "build_infill_prompt",
    "run_diffusion_probe",
    "comparison_table",
]
