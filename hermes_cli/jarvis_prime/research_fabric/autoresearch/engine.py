"""The governed autoresearch experiment driver — program.md's loop + MUSE rules.

Implements the vendored ``program.md`` loop verbatim (edit train.py → commit →
``uv run train.py > run.log`` → parse ``val_bpb`` → keep if lower else
``git reset``) inside a **disposable workspace** seeded from the vendored
payload under ``$HERMES_HOME/autoresearch/workspaces/<tag>/`` — the MUSE repo
and the byte-identical vendor files are never touched.

On top of the upstream loop it adds the four things autoresearch deliberately
omits and MUSE mandates:

- **cost ceiling** — ``max_experiments`` / ``max_wall_clock_seconds`` /
  ``max_cost_usd`` (first hit stops the run; supersedes program.md's
  NEVER STOP);
- **watchdog** — program.md's 10-minute hang kill, as a real subprocess
  timeout with process-group termination (``status="killed"``);
- **feasibility gate** — a run whose ``peak_vram_mb`` exceeds the VRAM budget
  is ``infeasible``: reset like a discard, never champion;
- **provenance** — every experiment is recorded to the flywheel
  (``"autoresearch.experiment"``; crash/killed/infeasible record
  ``outcome="failure"`` which auto-queues an improvement). ``results.tsv``
  is kept as the upstream-format local mirror only, never the ledger.

All process/git/edit interactions are injectable so the loop is fully testable
without a GPU, network, or git binary.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol, Sequence

from .platform import DeviceProfile, honest_mfu

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
TSV_HEADER = "commit\tval_bpb\tmemory_gb\tstatus\tdescription"
_SUMMARY_KEYS = (
    "val_bpb",
    "training_seconds",
    "total_seconds",
    "peak_vram_mb",
    "mfu_percent",
    "total_tokens_M",
    "num_steps",
    "num_params_M",
    "depth",
)


class CompletedLike(Protocol):
    returncode: int
    stdout: str
    stderr: str


# (argv, cwd=..., timeout=..., env=...) -> CompletedLike; raises
# subprocess.TimeoutExpired when the watchdog fires.
SubprocessRunner = Callable[..., CompletedLike]
# (git_args, cwd) -> CompletedLike
GitRunner = Callable[[Sequence[str], str], CompletedLike]


@dataclass(frozen=True)
class ExperimentEdit:
    """One idea: a description plus the full new train.py content."""

    description: str
    train_py: Optional[str]  # None for the baseline run (no edit)


@dataclass(frozen=True)
class EditContext:
    workspace: str
    history: tuple["ExperimentResult", ...]
    best_bpb: Optional[float]
    config: "ExperimentConfig"


# Returns the next experiment to try, or None when out of ideas.
EditProvider = Callable[[EditContext], Optional[ExperimentEdit]]


@dataclass(frozen=True)
class ExperimentConfig:
    tag: str
    objective: str = "minimize val_bpb"
    workspace_dir: str = ""  # default $HERMES_HOME/autoresearch/workspaces/<tag>
    branch: str = ""  # default autoresearch/<tag>
    device: str = "cuda:0"  # "modal:<gpu>" for serverless lanes
    # --- cost ceiling (ALL enforced; first hit stops; supersedes NEVER STOP) ---
    max_experiments: int = 12
    max_wall_clock_seconds: float = 4 * 3600.0
    max_cost_usd: float = 0.0  # 0.0 => local/free lane
    cost_per_hour_usd: float = 0.0
    # --- feasibility ---
    vram_budget_mb: float = 0.0  # 0.0 => platform.default_vram_budget_mb(detect())
    # --- watchdog (program.md's 10-minute kill) ---
    watchdog_seconds: float = 600.0
    baseline_bpb: Optional[float] = None  # None => experiment 0 establishes it
    uv_argv: tuple[str, ...] = ("uv", "run", "train.py")

    def resolved_branch(self) -> str:
        return self.branch or f"autoresearch/{self.tag}"

    def resolved_workspace(self) -> str:
        if self.workspace_dir:
            return self.workspace_dir
        base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
        return str(Path(base) / "autoresearch" / "workspaces" / self.tag)


@dataclass(frozen=True)
class ExperimentResult:
    index: int
    commit: str  # short-7 sha inside the workspace repo
    description: str
    val_bpb: Optional[float]  # None => crash/killed
    peak_vram_mb: Optional[float]
    mfu_percent_raw: Optional[float]
    mfu_percent_honest: Optional[float]
    training_seconds: Optional[float]
    total_seconds: Optional[float]
    total_tokens_m: Optional[float]
    num_steps: Optional[int]
    num_params_m: Optional[float]
    depth: Optional[int]
    status: str  # "keep" | "discard" | "crash" | "killed" | "infeasible"
    reason: str = ""
    log_tail: str = ""
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AutoresearchRun:
    config: ExperimentConfig
    results: tuple[ExperimentResult, ...]
    baseline: Optional[ExperimentResult]
    champion: Optional[ExperimentResult]  # lowest feasible val_bpb that improved
    best_infeasible: Optional[ExperimentResult]  # won bpb but blew a constraint
    stopped_reason: str
    workspace_path: str
    results_tsv_path: str
    total_cost_usd: float
    started_at: float
    finished_at: float


def bpb_gate_score(val_bpb: float) -> float:
    """Monotone-DECREASING map of bpb into (0, 1].

    ``benchmark_gate.evaluate_improvement`` is higher-is-better and
    ``WorkerScore.value`` is range-validated to [0, 1], so literal negation of
    a lower-is-better bpb is contract-illegal. Applied identically to baseline
    and candidate this transform is ordering-equivalent to negation; raw bpb
    values are preserved in rationale/evidence for honesty.
    """

    return 1.0 / (1.0 + max(0.0, val_bpb))


def gate_margin_for_bpb_delta(baseline_bpb: float, min_bpb_delta: float) -> float:
    """Convert a required bpb improvement into the gate's score-margin space."""

    if min_bpb_delta <= 0.0:
        return 0.0
    return bpb_gate_score(baseline_bpb - min_bpb_delta) - bpb_gate_score(baseline_bpb)


def parse_summary(log_text: str) -> Optional[dict[str, float]]:
    """Parse train.py's final summary block; None == crash (empty-grep rule)."""

    values: dict[str, float] = {}
    for line in log_text.splitlines():
        for key in _SUMMARY_KEYS:
            prefix = f"{key}:"
            if line.startswith(prefix):
                raw = line[len(prefix) :].strip()
                try:
                    values[key] = float(raw)
                except ValueError:
                    # Ignore malformed numeric values; parser is best-effort and
                    # only requires a valid final val_bpb to consider the run parsed.
                    continue
    if "val_bpb" not in values:
        return None
    return values


def _default_subprocess_runner(
    argv: Sequence[str],
    *,
    cwd: str,
    timeout: float,
    env: Optional[dict[str, str]] = None,
) -> CompletedLike:
    """Run with a process group so the watchdog kills uv's grandchildren too."""

    with subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    ) as proc:
        try:
            stdout, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):  # POSIX: kill the whole process group
                    os.killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))  # windows-footgun: ok
                else:
                    proc.kill()
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait()
            raise
    return subprocess.CompletedProcess(list(argv), proc.returncode, stdout or "", "")


def _default_git_runner(args: Sequence[str], cwd: str) -> CompletedLike:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def _record_experiment(config: ExperimentConfig, result: ExperimentResult) -> None:
    """Flywheel is the durable ledger; soft-fail by flywheel's own contract."""

    from hermes_cli.jarvis_prime import flywheel

    failed = result.status in ("crash", "killed", "infeasible")
    flywheel.record(
        "autoresearch.experiment",
        {
            "summary": f"[{config.tag}#{result.index}] {result.description}",
            "tag": config.tag,
            "index": result.index,
            "commit": result.commit,
            "val_bpb": result.val_bpb,
            "peak_vram_mb": result.peak_vram_mb,
            "status": result.status,
            "reason": result.reason,
            "branch": config.resolved_branch(),
            "device": config.device,
            "cost_usd": round(result.cost_usd, 4),
        },
        outcome="failure" if failed else "success",
        lesson=(result.log_tail.splitlines()[-1][:200] if failed and result.log_tail else None),
    )


def _append_tsv(tsv_path: Path, result: ExperimentResult) -> None:
    val = f"{result.val_bpb:.6f}" if result.val_bpb is not None else "0.000000"
    mem = (
        f"{result.peak_vram_mb / 1024:.1f}" if result.peak_vram_mb is not None else "0.0"
    )
    # Upstream statuses are keep|discard|crash; killed/infeasible map to the
    # mirror's nearest upstream notion, with the real status in description.
    status = {"killed": "crash", "infeasible": "discard"}.get(result.status, result.status)
    description = result.description.replace("\t", " ").replace("\n", " ")
    if result.status in ("killed", "infeasible"):
        description = f"[{result.status}] {description}"
    with tsv_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{result.commit}\t{val}\t{mem}\t{status}\t{description}\n")


def seed_workspace(
    config: ExperimentConfig,
    *,
    git_runner: Optional[GitRunner] = None,
    vendor_dir: Optional[Path] = None,
) -> str:
    """Copy the vendored payload into a fresh workspace repo on the run branch.

    The workspace gets its own ``git init`` + initial commit; ``results.tsv``
    is written AFTER the commit and never added (untracked mirror, per
    program.md step 7).
    """

    git = git_runner or _default_git_runner
    source = vendor_dir or VENDOR_DIR
    workspace = Path(config.resolved_workspace())
    workspace.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, workspace / item.name)
    git(["init", "--quiet"], str(workspace))
    git(["add", "-A"], str(workspace))
    git(
        ["-c", "user.email=muse@local", "-c", "user.name=MUSE autoresearch",
         "commit", "--quiet", "-m", "autoresearch: seed from MUSE vendor payload"],
        str(workspace),
    )
    git(["checkout", "--quiet", "-b", config.resolved_branch()], str(workspace))
    (workspace / "results.tsv").write_text(TSV_HEADER + "\n", encoding="utf-8")
    return str(workspace)


def _short_commit(git: GitRunner, workspace: str) -> str:
    res = git(["rev-parse", "--short=7", "HEAD"], workspace)
    return (res.stdout or "").strip() or "unknown"


def run_single_experiment(
    config: ExperimentConfig,
    workspace: str,
    index: int,
    edit: ExperimentEdit,
    *,
    best_bpb: Optional[float],
    subprocess_runner: Optional[SubprocessRunner] = None,
    git_runner: Optional[GitRunner] = None,
    profile: Optional[DeviceProfile] = None,
    clock: Callable[[], float] = time.monotonic,
) -> ExperimentResult:
    """One program.md iteration: commit → run (watchdogged) → parse → keep/reset."""

    runner = subprocess_runner or _default_subprocess_runner
    git = git_runner or _default_git_runner
    ws = Path(workspace)

    edited = edit.train_py is not None
    if edited:
        (ws / "train.py").write_text(edit.train_py, encoding="utf-8")
        git(["add", "train.py"], workspace)
        git(
            ["-c", "user.email=muse@local", "-c", "user.name=MUSE autoresearch",
             "commit", "--quiet", "-m", edit.description],
            workspace,
        )
    commit = _short_commit(git, workspace)

    started = clock()
    log_text = ""
    killed = False
    try:
        completed = runner(
            list(config.uv_argv),
            cwd=workspace,
            timeout=config.watchdog_seconds,
            env=None,
        )
        log_text = (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        killed = True
        captured = exc.stdout or b""
        log_text = captured.decode("utf-8", "replace") if isinstance(captured, bytes) else str(captured)
    elapsed = clock() - started
    (ws / "run.log").write_text(log_text, encoding="utf-8")
    cost = (elapsed / 3600.0) * config.cost_per_hour_usd

    summary = None if killed else parse_summary(log_text)
    tail = "\n".join(log_text.splitlines()[-50:])

    def _make(status: str, reason: str = "") -> ExperimentResult:
        mfu_raw = summary.get("mfu_percent") if summary else None
        return ExperimentResult(
            index=index,
            commit=commit,
            description=edit.description,
            val_bpb=summary.get("val_bpb") if summary else None,
            peak_vram_mb=summary.get("peak_vram_mb") if summary else None,
            mfu_percent_raw=mfu_raw,
            mfu_percent_honest=(
                honest_mfu(mfu_raw, profile) if mfu_raw is not None else None
            ),
            training_seconds=summary.get("training_seconds") if summary else None,
            total_seconds=summary.get("total_seconds") if summary else None,
            total_tokens_m=summary.get("total_tokens_M") if summary else None,
            num_steps=int(summary["num_steps"]) if summary and "num_steps" in summary else None,
            num_params_m=summary.get("num_params_M") if summary else None,
            depth=int(summary["depth"]) if summary and "depth" in summary else None,
            status=status,
            reason=reason,
            log_tail=tail if status in ("crash", "killed") else "",
            cost_usd=cost,
        )

    if killed:
        result = _make("killed", f"watchdog: exceeded {config.watchdog_seconds:.0f}s")
    elif summary is None:
        result = _make("crash", "no val_bpb in run.log (empty-grep rule)")
    elif (
        config.vram_budget_mb > 0
        and summary.get("peak_vram_mb") is not None
        and summary["peak_vram_mb"] > config.vram_budget_mb
    ):
        result = _make(
            "infeasible",
            f"peak VRAM {summary['peak_vram_mb']:.1f}MB > budget "
            f"{config.vram_budget_mb:.1f}MB",
        )
    elif best_bpb is None or summary["val_bpb"] < best_bpb:
        result = _make("keep")
    else:
        result = _make(
            "discard",
            f"val_bpb {summary['val_bpb']:.6f} >= best {best_bpb:.6f}",
        )

    # program.md steps 8/9: advance the branch on keep; reset otherwise.
    # The baseline (no edit) is never reset — there is nothing to undo.
    if edited and result.status != "keep":
        git(["reset", "--quiet", "--hard", "HEAD~1"], workspace)

    _append_tsv(ws / "results.tsv", result)
    _record_experiment(config, result)
    return result


def run_experiment_loop(
    config: ExperimentConfig,
    *,
    propose_edit: EditProvider,
    subprocess_runner: Optional[SubprocessRunner] = None,
    git_runner: Optional[GitRunner] = None,
    profile: Optional[DeviceProfile] = None,
    clock: Callable[[], float] = time.monotonic,
) -> AutoresearchRun:
    """The bounded loop: baseline, then ideas until a ceiling stops it."""

    started = clock()
    workspace = seed_workspace(config, git_runner=git_runner)
    tsv_path = str(Path(workspace) / "results.tsv")

    results: list[ExperimentResult] = []
    baseline: Optional[ExperimentResult] = None
    champion: Optional[ExperimentResult] = None
    best_infeasible: Optional[ExperimentResult] = None
    best_bpb = config.baseline_bpb
    total_cost = 0.0
    stopped_reason: str
    index = 0

    def _ceiling_hit() -> Optional[str]:
        if index >= config.max_experiments:
            return "max_experiments"
        if clock() - started >= config.max_wall_clock_seconds:
            return "wall_clock"
        if 0.0 < config.max_cost_usd <= total_cost:
            return "cost_ceiling"
        return None

    while True:
        hit = _ceiling_hit()
        if hit is not None:
            stopped_reason = hit
            break

        is_unedited_baseline = index == 0 and config.baseline_bpb is None
        if is_unedited_baseline:
            edit = ExperimentEdit(description="baseline (unedited train.py)", train_py=None)
        else:
            proposed = propose_edit(
                EditContext(
                    workspace=workspace,
                    history=tuple(results),
                    best_bpb=best_bpb,
                    config=config,
                )
            )
            if proposed is None:
                stopped_reason = "edit_provider_exhausted"
                break
            edit = proposed

        result = run_single_experiment(
            config,
            workspace,
            index,
            edit,
            best_bpb=best_bpb,
            subprocess_runner=subprocess_runner,
            git_runner=git_runner,
            profile=profile,
            clock=clock,
        )
        results.append(result)
        total_cost += result.cost_usd

        if is_unedited_baseline:
            baseline = result
        if result.status == "keep" and result.val_bpb is not None:
            best_bpb = result.val_bpb
            # The unedited baseline is the bar, not a challenger.
            if not is_unedited_baseline:
                champion = result
        if result.status == "infeasible" and result.val_bpb is not None:
            if best_infeasible is None or result.val_bpb < (
                best_infeasible.val_bpb or float("inf")
            ):
                best_infeasible = result
        index += 1

    return AutoresearchRun(
        config=config,
        results=tuple(results),
        baseline=baseline,
        champion=champion,
        best_infeasible=best_infeasible,
        stopped_reason=stopped_reason,
        workspace_path=workspace,
        results_tsv_path=tsv_path,
        total_cost_usd=round(total_cost, 6),
        started_at=started,
        finished_at=clock(),
    )


def summarize_idea_classes(results: Sequence[ExperimentResult]) -> str:
    """One-paragraph 'what worked' digest for Memory-Tree consolidation."""

    kept = [r.description for r in results if r.status == "keep"]
    discarded = [r.description for r in results if r.status == "discard"]
    failed = [
        f"{r.description} ({r.status})"
        for r in results
        if r.status in ("crash", "killed", "infeasible")
    ]

    def _fmt(items: Sequence[str]) -> str:
        return "; ".join(items) if items else "none"

    return (
        f"kept: {_fmt(kept)}. discarded: {_fmt(discarded)}. failed: {_fmt(failed)}."
    )


__all__ = [
    "VENDOR_DIR",
    "TSV_HEADER",
    "ExperimentEdit",
    "EditContext",
    "EditProvider",
    "ExperimentConfig",
    "ExperimentResult",
    "AutoresearchRun",
    "bpb_gate_score",
    "gate_margin_for_bpb_delta",
    "parse_summary",
    "seed_workspace",
    "run_single_experiment",
    "run_experiment_loop",
    "summarize_idea_classes",
]
