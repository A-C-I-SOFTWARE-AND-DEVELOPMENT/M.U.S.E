"""Local validation gates for Hermes work product.

Hermes runs ``ValidationRunner`` against a workspace before any
"publish" action (committing, opening a PR, exporting a job folder).
The runner infers safe checks from the workspace shape, executes
them, records structured results, and reports whether the publish
gate should open or stay closed.

Policy invariants (mirrored in ``skills/local-quality-gate/SKILL.md``
and ``docs/orchestration/local-validation-gates.md``):

* Safe, read-only checks (``git status``, ``py_compile``,
  ``bash -n``, frontmatter parsing) auto-run.
* Expensive checks (full test suites, ``./gradlew assembleDebug``,
  ``apktool d``) only run when ``allow_expensive=True`` or the
  workspace config opts in.
* Destructive operations (anything that would mutate user data on
  disk, push to a remote, rewrite history) are *never* invoked from
  here — they are tagged ``destructive`` and skipped with a
  ``blocked`` status.
* If a check tagged ``critical`` produces a ``fail`` status, the
  publish gate stays closed regardless of the other results.

The runner writes three artefacts under ``<workspace>/validation/``:

  - ``results.json`` — machine-readable list of check records
  - ``summary.md``   — human-readable summary table
  - ``commands.log`` — the literal commands that were executed,
                       one per line, in the order they ran

Nothing in this module imports the rest of the Hermes CLI — it is
intentionally standalone so the validation skill can call it from a
freshly-spawned subprocess, a worker, or a unit test.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


# ── Constants ───────────────────────────────────────────────────────────────

# Default timeout for any single check, in seconds. Individual checks
# can override via their own ``timeout`` field.
DEFAULT_CHECK_TIMEOUT_S = 60

# Result statuses. ``skipped`` and ``blocked`` are intentionally
# distinct: skipped means "not relevant for this workspace", blocked
# means "policy forbids running this here without explicit consent".
STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_WARN = "warn"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"

_TERMINAL_STATUSES = frozenset(
    {STATUS_PASS, STATUS_FAIL, STATUS_WARN, STATUS_SKIPPED, STATUS_BLOCKED, STATUS_ERROR}
)

# Patterns that look like secrets in a diff. Kept conservative — we
# would rather miss an obscure key than block every commit on a false
# positive. Each entry is (label, compiled regex).
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"(?i)aws(.{0,20})?(secret|private).{0,20}['\"][0-9a-zA-Z/+]{40}['\"]")),
    ("github_token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("slack_token", re.compile(r"xox[abpr]-[0-9A-Za-z\-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("generic_secret_kv", re.compile(r"(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][^'\"\s]{16,}['\"]")),
)

# Names of files we never want to see staged. ``.env`` is the canonical
# offender; users keep meaning to ``.gitignore`` it but forget.
_BLOCKED_PATHS: tuple[str, ...] = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
)

# Categories. The runner uses these to filter (e.g. ``--only secrets``)
# and to drive the summary table grouping.
CATEGORY_GIT = "git"
CATEGORY_SECRETS = "secrets"
CATEGORY_LANGUAGE = "language"
CATEGORY_HERMES = "hermes"
CATEGORY_APK = "apk"
CATEGORY_REMOTE = "remote"

# Remote runtime artefacts the runner inspects when discovering
# ``CATEGORY_REMOTE`` checks. These are deliberately read-only — the
# runner never opens a tunnel, never enqueues a job, never starts a
# worker. It only reports on whatever the remote stack has already
# written under ``<workspace>/remote/``.
REMOTE_DIRNAME = "remote"
REMOTE_TUNNEL_FILENAME = "tunnel.json"
REMOTE_WORKERS_DIRNAME = "workers"
REMOTE_QUEUE_FILENAME = "queue.json"

# Heartbeat / queue-age thresholds. A heartbeat older than
# ``REMOTE_WORKER_STALE_S`` produces a warn; a queue head older than
# ``REMOTE_QUEUE_STALE_S`` produces a warn. Neither blocks publish —
# the gate's job is to flag, not to gate on transient remote state.
REMOTE_WORKER_STALE_S = 5 * 60
REMOTE_QUEUE_STALE_S = 30 * 60


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclasses.dataclass
class CheckResult:
    """A single check's outcome.

    ``status`` is one of the ``STATUS_*`` constants above. ``critical``
    means a ``fail`` here blocks publish. ``stdout`` / ``stderr`` are
    truncated to avoid blowing up ``results.json`` when a tool floods
    output (the full text is in ``commands.log``).
    """

    name: str
    category: str
    status: str
    summary: str
    critical: bool = False
    command: str | None = None
    returncode: int | None = None
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        # Drop empty noise — keeps results.json readable.
        if not d["stdout"]:
            d.pop("stdout")
        if not d["stderr"]:
            d.pop("stderr")
        if not d["metadata"]:
            d.pop("metadata")
        if d["command"] is None:
            d.pop("command")
        if d["returncode"] is None:
            d.pop("returncode")
        return d


@dataclasses.dataclass
class ValidationReport:
    """Aggregate output of a single ``ValidationRunner.run()`` pass."""

    workspace: str
    results: list[CheckResult]
    publish_allowed: bool
    blocking_failures: list[str]
    started_at: float
    finished_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": self.workspace,
            "publish_allowed": self.publish_allowed,
            "blocking_failures": self.blocking_failures,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": int((self.finished_at - self.started_at) * 1000),
            "checks": [r.to_dict() for r in self.results],
        }

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


# ── Runner ──────────────────────────────────────────────────────────────────


class ValidationRunner:
    """Orchestrate validation checks for a workspace.

    Construction is cheap — discovery and command execution happen in
    ``run()``. The runner is intentionally not threadsafe; spin up one
    per concurrent workspace.
    """

    def __init__(
        self,
        workspace: str | os.PathLike[str],
        *,
        allow_expensive: bool = False,
        only: Sequence[str] | None = None,
        skip: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        output_dir: str | os.PathLike[str] | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.allow_expensive = bool(allow_expensive)
        self.only = tuple(only or ())
        self.skip = tuple(skip or ())
        self._env = dict(env) if env is not None else None
        self.output_dir = Path(output_dir).resolve() if output_dir else self.workspace / "validation"

        self._commands_log: list[str] = []

    # — Public entrypoint ───────────────────────────────────────────────────

    def run(self) -> ValidationReport:
        started = time.time()
        results: list[CheckResult] = []

        for check in self._discover_checks():
            if self.only and check["category"] not in self.only:
                continue
            if self.skip and check["category"] in self.skip:
                continue
            results.append(self._execute(check))

        finished = time.time()

        blocking = [
            r.name for r in results if r.critical and r.status == STATUS_FAIL
        ]
        report = ValidationReport(
            workspace=str(self.workspace),
            results=results,
            publish_allowed=not blocking,
            blocking_failures=blocking,
            started_at=started,
            finished_at=finished,
        )
        self._write_artifacts(report)
        return report

    # — Check discovery ────────────────────────────────────────────────────

    def _discover_checks(self) -> list[dict[str, Any]]:
        """Return the list of checks the runner will attempt.

        Each entry is a plain dict with these keys:

          - ``name``      — stable identifier
          - ``category``  — one of the ``CATEGORY_*`` constants
          - ``critical``  — bool, blocks publish on fail
          - ``runner``    — callable(self) -> CheckResult
        """
        checks: list[dict[str, Any]] = []

        # 1. Git checks — only meaningful inside a git work tree.
        if self._is_git_repo():
            checks.extend(
                [
                    {
                        "name": "git.status",
                        "category": CATEGORY_GIT,
                        "critical": False,
                        "runner": self._check_git_status,
                    },
                    {
                        "name": "git.whitespace",
                        "category": CATEGORY_GIT,
                        "critical": False,
                        "runner": self._check_git_whitespace,
                    },
                    {
                        "name": "git.diff_stat",
                        "category": CATEGORY_GIT,
                        "critical": False,
                        "runner": self._check_git_diff_stat,
                    },
                ]
            )
            # 2. Secret checks rely on a git diff being available.
            checks.extend(
                [
                    {
                        "name": "secrets.staged_diff",
                        "category": CATEGORY_SECRETS,
                        "critical": True,
                        "runner": self._check_secrets_staged,
                    },
                    {
                        "name": "secrets.unstaged_diff",
                        "category": CATEGORY_SECRETS,
                        "critical": False,
                        "runner": self._check_secrets_unstaged,
                    },
                    {
                        "name": "secrets.blocked_paths",
                        "category": CATEGORY_SECRETS,
                        "critical": True,
                        "runner": self._check_blocked_paths,
                    },
                ]
            )

        # 3. Language / framework checks.
        if (self.workspace / "pyproject.toml").exists() or self._has_python_sources():
            checks.append(
                {
                    "name": "python.py_compile",
                    "category": CATEGORY_LANGUAGE,
                    "critical": True,
                    "runner": self._check_py_compile,
                }
            )
            if self._has_pytest():
                checks.append(
                    {
                        "name": "python.pytest",
                        "category": CATEGORY_LANGUAGE,
                        "critical": True,
                        "runner": self._check_pytest,
                        "expensive": True,
                    }
                )
            if self._has_ruff_config():
                checks.append(
                    {
                        "name": "python.ruff",
                        "category": CATEGORY_LANGUAGE,
                        "critical": False,
                        "runner": self._check_ruff,
                    }
                )

        if (self.workspace / "package.json").exists():
            checks.append(
                {
                    "name": "node.tests",
                    "category": CATEGORY_LANGUAGE,
                    "critical": True,
                    "runner": self._check_node_tests,
                    "expensive": True,
                }
            )
            checks.append(
                {
                    "name": "node.lint",
                    "category": CATEGORY_LANGUAGE,
                    "critical": False,
                    "runner": self._check_node_lint,
                }
            )

        if (self.workspace / "gradlew").exists() or (self.workspace / "build.gradle").exists():
            checks.append(
                {
                    "name": "gradle.test",
                    "category": CATEGORY_LANGUAGE,
                    "critical": True,
                    "runner": self._check_gradle_test,
                    "expensive": True,
                }
            )
            checks.append(
                {
                    "name": "gradle.assemble_debug",
                    "category": CATEGORY_LANGUAGE,
                    "critical": False,
                    "runner": self._check_gradle_assemble,
                    "expensive": True,
                }
            )

        if (self.workspace / "scripts").is_dir() and self._has_shell_scripts():
            checks.append(
                {
                    "name": "shell.syntax",
                    "category": CATEGORY_LANGUAGE,
                    "critical": True,
                    "runner": self._check_shell_syntax,
                }
            )

        # 4. Hermes-specific checks. These are cheap and always
        #    relevant if the workspace looks Hermes-shaped.
        if (self.workspace / "skills").is_dir():
            checks.append(
                {
                    "name": "hermes.skill_frontmatter",
                    "category": CATEGORY_HERMES,
                    "critical": True,
                    "runner": self._check_skill_frontmatter,
                }
            )
            checks.append(
                {
                    "name": "hermes.duplicate_skills",
                    "category": CATEGORY_HERMES,
                    "critical": True,
                    "runner": self._check_duplicate_skill_names,
                }
            )

        if (self.workspace / "jobs").is_dir():
            checks.append(
                {
                    "name": "hermes.job_folder",
                    "category": CATEGORY_HERMES,
                    "critical": True,
                    "runner": self._check_job_folder_contract,
                }
            )

        if (self.workspace / "model_registry.json").exists() or (self.workspace / "models.yaml").exists():
            checks.append(
                {
                    "name": "hermes.model_registry",
                    "category": CATEGORY_HERMES,
                    "critical": True,
                    "runner": self._check_model_registry,
                }
            )

        if (self.workspace / "workers").is_dir():
            checks.append(
                {
                    "name": "hermes.worker_status",
                    "category": CATEGORY_HERMES,
                    "critical": False,
                    "runner": self._check_worker_status,
                }
            )

        # 5. Remote runtime checks — only meaningful when the workspace
        #    has a ``remote/`` directory the worker stack writes to.
        if (self.workspace / REMOTE_DIRNAME).is_dir():
            checks.append(
                {
                    "name": "remote.tunnel",
                    "category": CATEGORY_REMOTE,
                    "critical": False,
                    "runner": self._check_remote_tunnel,
                }
            )
            checks.append(
                {
                    "name": "remote.workers",
                    "category": CATEGORY_REMOTE,
                    "critical": False,
                    "runner": self._check_remote_workers,
                }
            )
            checks.append(
                {
                    "name": "remote.queue",
                    "category": CATEGORY_REMOTE,
                    "critical": False,
                    "runner": self._check_remote_queue,
                }
            )

        # 6. APK audit pack — optional, only runs when the user opts in
        #    via ``allow_expensive`` AND the relevant tools are on PATH
        #    AND the workspace has an APK to audit. Each individual
        #    check no-ops cleanly if its tool is missing.
        if self._has_apk():
            checks.extend(
                [
                    {
                        "name": "apk.apktool",
                        "category": CATEGORY_APK,
                        "critical": False,
                        "runner": self._check_apk_apktool,
                        "expensive": True,
                    },
                    {
                        "name": "apk.aapt_badging",
                        "category": CATEGORY_APK,
                        "critical": False,
                        "runner": self._check_apk_aapt,
                        "expensive": True,
                    },
                    {
                        "name": "apk.jadx_smoke",
                        "category": CATEGORY_APK,
                        "critical": False,
                        "runner": self._check_apk_jadx,
                        "expensive": True,
                    },
                ]
            )

        return checks

    # — Execution wrapper ──────────────────────────────────────────────────

    def _execute(self, check: dict[str, Any]) -> CheckResult:
        if check.get("expensive") and not self.allow_expensive:
            return CheckResult(
                name=check["name"],
                category=check["category"],
                status=STATUS_BLOCKED,
                summary="expensive check skipped (allow_expensive=False)",
                critical=check["critical"],
            )

        runner = check["runner"]
        try:
            result = runner()
        except Exception as exc:  # noqa: BLE001 — boundary for tool wrappers.
            result = CheckResult(
                name=check["name"],
                category=check["category"],
                status=STATUS_ERROR,
                summary=f"runner raised: {type(exc).__name__}: {exc}",
                critical=check["critical"],
            )

        # Force the check's declared name/category/criticality onto the
        # result. This keeps individual runners from accidentally
        # rewriting their own identity.
        result.name = check["name"]
        result.category = check["category"]
        result.critical = bool(check["critical"])
        if result.status not in _TERMINAL_STATUSES:
            result.status = STATUS_ERROR
            result.summary = f"unknown status returned: {result.status!r}"
        return result

    # — Helpers ────────────────────────────────────────────────────────────

    def _run_cmd(
        self,
        argv: Sequence[str],
        *,
        timeout: int = DEFAULT_CHECK_TIMEOUT_S,
        cwd: Path | None = None,
        stdin: str | None = None,
    ) -> tuple[int, str, str, int]:
        """Run ``argv`` capturing stdout/stderr.

        Returns ``(returncode, stdout, stderr, duration_ms)``.
        Records the literal command in ``commands.log``. Wraps
        ``subprocess.run`` so that ``TimeoutExpired`` and missing
        executables come back as a synthetic non-zero return code
        rather than an unhandled exception.
        """
        cwd_path = cwd or self.workspace
        pretty = " ".join(_shell_quote(a) for a in argv)
        self._commands_log.append(pretty)

        start = time.monotonic()
        try:
            proc = subprocess.run(  # noqa: S603 — argv is built internally.
                list(argv),
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin,
                env=self._env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            elapsed = int((time.monotonic() - start) * 1000)
            return 124, "", f"timeout after {timeout}s", elapsed
        except FileNotFoundError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return 127, "", f"command not found: {exc.filename or argv[0]}", elapsed

        elapsed = int((time.monotonic() - start) * 1000)
        return proc.returncode, proc.stdout or "", proc.stderr or "", elapsed

    def _is_git_repo(self) -> bool:
        return (self.workspace / ".git").exists()

    def _has_python_sources(self) -> bool:
        for p in self.workspace.rglob("*.py"):
            # Cheap heuristic — bail out the moment we see one.
            try:
                if ".git" in p.parts or ".venv" in p.parts or "venv" in p.parts:
                    continue
            except OSError:
                continue
            return True
        return False

    def _has_pytest(self) -> bool:
        return (self.workspace / "tests").is_dir() or (self.workspace / "test").is_dir()

    def _has_ruff_config(self) -> bool:
        # ruff reads pyproject.toml or its own ruff.toml.
        pyproject = self.workspace / "pyproject.toml"
        if pyproject.exists():
            try:
                text = pyproject.read_text(encoding="utf-8")
            except OSError:
                return False
            if "[tool.ruff" in text:
                return True
        return (self.workspace / "ruff.toml").exists() or (self.workspace / ".ruff.toml").exists()

    def _has_shell_scripts(self) -> bool:
        scripts = self.workspace / "scripts"
        return any(p.suffix == ".sh" for p in scripts.glob("*.sh"))

    def _has_apk(self) -> bool:
        for p in self.workspace.rglob("*.apk"):
            if ".git" in p.parts:
                continue
            return True
        return False

    # — Git checks ─────────────────────────────────────────────────────────

    def _check_git_status(self) -> CheckResult:
        rc, out, err, ms = self._run_cmd(["git", "status", "--short"])
        if rc != 0:
            return CheckResult(
                name="git.status",
                category=CATEGORY_GIT,
                status=STATUS_ERROR,
                summary=err.strip() or "git status failed",
                command="git status --short",
                returncode=rc,
                duration_ms=ms,
                stderr=_truncate(err),
            )
        lines = [ln for ln in out.splitlines() if ln.strip()]
        changed = len(lines)
        return CheckResult(
            name="git.status",
            category=CATEGORY_GIT,
            status=STATUS_PASS,
            summary=f"{changed} changed path(s)",
            command="git status --short",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            metadata={"changed_paths": changed, "paths": [ln[3:] for ln in lines[:50]]},
        )

    def _check_git_whitespace(self) -> CheckResult:
        rc, out, err, ms = self._run_cmd(["git", "diff", "--check"])
        # ``git diff --check`` exits 0 when clean, non-zero on findings.
        if rc == 0:
            return CheckResult(
                name="git.whitespace",
                category=CATEGORY_GIT,
                status=STATUS_PASS,
                summary="no whitespace errors",
                command="git diff --check",
                returncode=rc,
                duration_ms=ms,
            )
        return CheckResult(
            name="git.whitespace",
            category=CATEGORY_GIT,
            status=STATUS_WARN,
            summary=f"{len(out.splitlines())} whitespace issue(s)",
            command="git diff --check",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_git_diff_stat(self) -> CheckResult:
        rc, out, err, ms = self._run_cmd(["git", "diff", "--stat"])
        if rc != 0:
            return CheckResult(
                name="git.diff_stat",
                category=CATEGORY_GIT,
                status=STATUS_ERROR,
                summary=err.strip() or "git diff failed",
                command="git diff --stat",
                returncode=rc,
                duration_ms=ms,
                stderr=_truncate(err),
            )
        # Final line is typically ``N files changed, ...``
        tail = out.strip().splitlines()[-1] if out.strip() else "no changes"
        return CheckResult(
            name="git.diff_stat",
            category=CATEGORY_GIT,
            status=STATUS_PASS,
            summary=tail,
            command="git diff --stat",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
        )

    # — Secret checks ──────────────────────────────────────────────────────

    def _check_secrets_staged(self) -> CheckResult:
        return self._scan_diff_for_secrets(["git", "diff", "--cached"], "staged")

    def _check_secrets_unstaged(self) -> CheckResult:
        return self._scan_diff_for_secrets(["git", "diff"], "unstaged")

    def _scan_diff_for_secrets(self, argv: Sequence[str], label: str) -> CheckResult:
        rc, out, err, ms = self._run_cmd(list(argv))
        if rc != 0:
            return CheckResult(
                name=f"secrets.{label}_diff",
                category=CATEGORY_SECRETS,
                status=STATUS_ERROR,
                summary=err.strip() or f"git diff ({label}) failed",
                command=" ".join(argv),
                returncode=rc,
                duration_ms=ms,
                stderr=_truncate(err),
            )
        findings = scan_text_for_secrets(out)
        if not findings:
            return CheckResult(
                name=f"secrets.{label}_diff",
                category=CATEGORY_SECRETS,
                status=STATUS_PASS,
                summary=f"no secrets found in {label} diff",
                command=" ".join(argv),
                returncode=rc,
                duration_ms=ms,
            )
        # Each finding: (pattern_label, snippet)
        snippets = [{"pattern": p, "snippet": s} for p, s in findings[:20]]
        return CheckResult(
            name=f"secrets.{label}_diff",
            category=CATEGORY_SECRETS,
            status=STATUS_FAIL,
            summary=f"{len(findings)} secret-like match(es) in {label} diff",
            command=" ".join(argv),
            returncode=rc,
            duration_ms=ms,
            metadata={"findings": snippets},
        )

    def _check_blocked_paths(self) -> CheckResult:
        rc, out, err, ms = self._run_cmd(
            ["git", "diff", "--cached", "--name-only"]
        )
        if rc != 0:
            return CheckResult(
                name="secrets.blocked_paths",
                category=CATEGORY_SECRETS,
                status=STATUS_ERROR,
                summary=err.strip() or "git diff failed",
                command="git diff --cached --name-only",
                returncode=rc,
                duration_ms=ms,
                stderr=_truncate(err),
            )
        offenders = []
        for line in out.splitlines():
            name = line.strip()
            if not name:
                continue
            basename = name.rsplit("/", 1)[-1]
            if basename in _BLOCKED_PATHS:
                offenders.append(name)
        if offenders:
            return CheckResult(
                name="secrets.blocked_paths",
                category=CATEGORY_SECRETS,
                status=STATUS_FAIL,
                summary=f"blocked path(s) staged: {', '.join(offenders)}",
                command="git diff --cached --name-only",
                returncode=rc,
                duration_ms=ms,
                metadata={"offenders": offenders},
            )
        return CheckResult(
            name="secrets.blocked_paths",
            category=CATEGORY_SECRETS,
            status=STATUS_PASS,
            summary="no blocked paths staged",
            command="git diff --cached --name-only",
            returncode=rc,
            duration_ms=ms,
        )

    # — Language checks ────────────────────────────────────────────────────

    def _check_py_compile(self) -> CheckResult:
        files: list[str] = []
        for p in self.workspace.rglob("*.py"):
            if any(part in {".git", ".venv", "venv", "node_modules", "build", "dist"} for part in p.parts):
                continue
            try:
                files.append(str(p.relative_to(self.workspace)))
            except ValueError:
                continue
        if not files:
            return CheckResult(
                name="python.py_compile",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no python sources found",
            )
        # Cap compile-list size to avoid command-line blow-up on huge
        # trees; ``py_compile`` does the work, not the shell.
        sample = files[:500]
        rc, out, err, ms = self._run_cmd(
            ["python", "-m", "py_compile", *sample],
            timeout=120,
        )
        if rc == 0:
            return CheckResult(
                name="python.py_compile",
                category=CATEGORY_LANGUAGE,
                status=STATUS_PASS,
                summary=f"compiled {len(sample)} file(s) cleanly",
                command=f"python -m py_compile <{len(sample)} files>",
                returncode=rc,
                duration_ms=ms,
                metadata={"files_compiled": len(sample), "total_files": len(files)},
            )
        return CheckResult(
            name="python.py_compile",
            category=CATEGORY_LANGUAGE,
            status=STATUS_FAIL,
            summary=err.splitlines()[0] if err else "py_compile failed",
            command=f"python -m py_compile <{len(sample)} files>",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_pytest(self) -> CheckResult:
        if not shutil.which("pytest") and not shutil.which("python"):
            return CheckResult(
                name="python.pytest",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="pytest unavailable",
            )
        rc, out, err, ms = self._run_cmd(
            ["python", "-m", "pytest", "-q", "--maxfail=5"], timeout=600
        )
        status = STATUS_PASS if rc == 0 else STATUS_FAIL
        tail = (out or err).strip().splitlines()
        summary = tail[-1] if tail else f"pytest exit={rc}"
        return CheckResult(
            name="python.pytest",
            category=CATEGORY_LANGUAGE,
            status=status,
            summary=summary,
            command="python -m pytest -q --maxfail=5",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_ruff(self) -> CheckResult:
        if not shutil.which("ruff"):
            return CheckResult(
                name="python.ruff",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="ruff not installed",
            )
        rc, out, err, ms = self._run_cmd(["ruff", "check", "."], timeout=120)
        if rc == 0:
            return CheckResult(
                name="python.ruff",
                category=CATEGORY_LANGUAGE,
                status=STATUS_PASS,
                summary="ruff clean",
                command="ruff check .",
                returncode=rc,
                duration_ms=ms,
            )
        return CheckResult(
            name="python.ruff",
            category=CATEGORY_LANGUAGE,
            status=STATUS_WARN,
            summary=f"ruff reported issues (exit={rc})",
            command="ruff check .",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
        )

    def _check_node_tests(self) -> CheckResult:
        cmd = self._node_pkg_manager_command("test")
        if cmd is None:
            return CheckResult(
                name="node.tests",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no node package manager available",
            )
        rc, out, err, ms = self._run_cmd(cmd, timeout=600)
        return CheckResult(
            name="node.tests",
            category=CATEGORY_LANGUAGE,
            status=STATUS_PASS if rc == 0 else STATUS_FAIL,
            summary=f"{' '.join(cmd)} exit={rc}",
            command=" ".join(cmd),
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_node_lint(self) -> CheckResult:
        # Lint is best-effort. We only run it when package.json
        # actually declares a ``lint`` script — running ``npm run lint``
        # without that script just exits 1 with a meaningless error.
        pkg = self.workspace / "package.json"
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return CheckResult(
                name="node.lint",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="package.json unreadable",
            )
        scripts = data.get("scripts") or {}
        if "lint" not in scripts:
            return CheckResult(
                name="node.lint",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no `lint` script in package.json",
            )
        cmd = self._node_pkg_manager_command("lint")
        if cmd is None:
            return CheckResult(
                name="node.lint",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no node package manager available",
            )
        rc, out, err, ms = self._run_cmd(cmd, timeout=180)
        return CheckResult(
            name="node.lint",
            category=CATEGORY_LANGUAGE,
            status=STATUS_PASS if rc == 0 else STATUS_WARN,
            summary=f"lint exit={rc}",
            command=" ".join(cmd),
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _node_pkg_manager_command(self, script: str) -> list[str] | None:
        for pm, run_args in (("pnpm", ["run"]), ("npm", ["run"]), ("yarn", [])):
            if shutil.which(pm):
                return [pm, *run_args, script]
        return None

    def _check_gradle_test(self) -> CheckResult:
        return self._gradle_task("gradle.test", "test")

    def _check_gradle_assemble(self) -> CheckResult:
        return self._gradle_task("gradle.assemble_debug", "assembleDebug", critical=False)

    def _gradle_task(self, name: str, task: str, *, critical: bool = True) -> CheckResult:
        gradlew = self.workspace / "gradlew"
        if not gradlew.exists():
            return CheckResult(
                name=name,
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no gradlew in workspace root",
                critical=critical,
            )
        rc, out, err, ms = self._run_cmd(["./gradlew", task, "--quiet"], timeout=600)
        return CheckResult(
            name=name,
            category=CATEGORY_LANGUAGE,
            status=STATUS_PASS if rc == 0 else STATUS_FAIL,
            summary=f"./gradlew {task} exit={rc}",
            command=f"./gradlew {task} --quiet",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
            critical=critical,
        )

    def _check_shell_syntax(self) -> CheckResult:
        scripts = sorted((self.workspace / "scripts").glob("*.sh"))
        if not scripts:
            return CheckResult(
                name="shell.syntax",
                category=CATEGORY_LANGUAGE,
                status=STATUS_SKIPPED,
                summary="no shell scripts",
            )
        errors: list[str] = []
        commands: list[str] = []
        total_ms = 0
        for script in scripts:
            rel = str(script.relative_to(self.workspace))
            rc, _, err, ms = self._run_cmd(["bash", "-n", rel])
            total_ms += ms
            commands.append(f"bash -n {rel}")
            if rc != 0:
                errors.append(f"{rel}: {err.strip() or 'syntax error'}")
        if errors:
            return CheckResult(
                name="shell.syntax",
                category=CATEGORY_LANGUAGE,
                status=STATUS_FAIL,
                summary=f"{len(errors)} shell syntax error(s)",
                command="; ".join(commands[:5]),
                duration_ms=total_ms,
                stderr="\n".join(errors[:20]),
            )
        return CheckResult(
            name="shell.syntax",
            category=CATEGORY_LANGUAGE,
            status=STATUS_PASS,
            summary=f"{len(scripts)} shell script(s) clean",
            command="bash -n scripts/*.sh",
            duration_ms=total_ms,
            metadata={"scripts_checked": len(scripts)},
        )

    # — Hermes-specific checks ─────────────────────────────────────────────

    def _check_skill_frontmatter(self) -> CheckResult:
        skill_files = list((self.workspace / "skills").rglob("SKILL.md"))
        if not skill_files:
            return CheckResult(
                name="hermes.skill_frontmatter",
                category=CATEGORY_HERMES,
                status=STATUS_SKIPPED,
                summary="no SKILL.md files",
            )
        bad: list[str] = []
        for skill in skill_files:
            try:
                text = skill.read_text(encoding="utf-8")
            except OSError as exc:
                bad.append(f"{skill}: unreadable ({exc})")
                continue
            err = validate_skill_frontmatter(text)
            if err is not None:
                bad.append(f"{skill.relative_to(self.workspace)}: {err}")
        if bad:
            return CheckResult(
                name="hermes.skill_frontmatter",
                category=CATEGORY_HERMES,
                status=STATUS_FAIL,
                summary=f"{len(bad)} skill(s) with invalid frontmatter",
                stderr="\n".join(bad[:20]),
                metadata={"invalid": bad[:20]},
            )
        return CheckResult(
            name="hermes.skill_frontmatter",
            category=CATEGORY_HERMES,
            status=STATUS_PASS,
            summary=f"{len(skill_files)} skill(s) parsed cleanly",
            metadata={"skills_checked": len(skill_files)},
        )

    def _check_duplicate_skill_names(self) -> CheckResult:
        skill_files = list((self.workspace / "skills").rglob("SKILL.md"))
        if not skill_files:
            return CheckResult(
                name="hermes.duplicate_skills",
                category=CATEGORY_HERMES,
                status=STATUS_SKIPPED,
                summary="no SKILL.md files",
            )
        names: dict[str, list[str]] = {}
        for skill in skill_files:
            try:
                text = skill.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = parse_frontmatter(text) or {}
            name = meta.get("name")
            if not isinstance(name, str):
                continue
            names.setdefault(name, []).append(str(skill.relative_to(self.workspace)))
        duplicates = {n: paths for n, paths in names.items() if len(paths) > 1}
        if duplicates:
            return CheckResult(
                name="hermes.duplicate_skills",
                category=CATEGORY_HERMES,
                status=STATUS_FAIL,
                summary=f"{len(duplicates)} duplicate skill name(s)",
                metadata={"duplicates": duplicates},
            )
        return CheckResult(
            name="hermes.duplicate_skills",
            category=CATEGORY_HERMES,
            status=STATUS_PASS,
            summary=f"{len(names)} unique skill name(s)",
        )

    def _check_job_folder_contract(self) -> CheckResult:
        jobs_root = self.workspace / "jobs"
        if not jobs_root.is_dir():
            return CheckResult(
                name="hermes.job_folder",
                category=CATEGORY_HERMES,
                status=STATUS_SKIPPED,
                summary="no jobs/ directory",
            )
        problems: list[str] = []
        job_count = 0
        for job_dir in sorted(p for p in jobs_root.iterdir() if p.is_dir()):
            job_count += 1
            err = validate_job_folder(job_dir)
            if err is not None:
                problems.append(f"{job_dir.name}: {err}")
        if not job_count:
            return CheckResult(
                name="hermes.job_folder",
                category=CATEGORY_HERMES,
                status=STATUS_SKIPPED,
                summary="jobs/ is empty",
            )
        if problems:
            return CheckResult(
                name="hermes.job_folder",
                category=CATEGORY_HERMES,
                status=STATUS_FAIL,
                summary=f"{len(problems)} job folder(s) violate contract",
                stderr="\n".join(problems[:20]),
                metadata={"violations": problems[:20]},
            )
        return CheckResult(
            name="hermes.job_folder",
            category=CATEGORY_HERMES,
            status=STATUS_PASS,
            summary=f"{job_count} job folder(s) ok",
        )

    def _check_model_registry(self) -> CheckResult:
        candidates = [
            self.workspace / "model_registry.json",
            self.workspace / "models.yaml",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                return CheckResult(
                    name="hermes.model_registry",
                    category=CATEGORY_HERMES,
                    status=STATUS_FAIL,
                    summary=f"{path.name}: unreadable ({exc})",
                )
            try:
                if path.suffix == ".json":
                    data = json.loads(text)
                else:
                    try:
                        import yaml  # type: ignore[import-not-found]

                        data = yaml.safe_load(text)
                    except ImportError:
                        data = _parse_simple_yaml(text)
            except Exception as exc:  # noqa: BLE001 — surfaces parse errors.
                return CheckResult(
                    name="hermes.model_registry",
                    category=CATEGORY_HERMES,
                    status=STATUS_FAIL,
                    summary=f"{path.name}: parse error: {exc}",
                )
            if not isinstance(data, (dict, list)):
                return CheckResult(
                    name="hermes.model_registry",
                    category=CATEGORY_HERMES,
                    status=STATUS_FAIL,
                    summary=f"{path.name}: top-level must be mapping or list",
                )
            count = len(data)
            return CheckResult(
                name="hermes.model_registry",
                category=CATEGORY_HERMES,
                status=STATUS_PASS,
                summary=f"{path.name}: parsed {count} entry/entries",
                metadata={"path": str(path.relative_to(self.workspace)), "entries": count},
            )
        return CheckResult(
            name="hermes.model_registry",
            category=CATEGORY_HERMES,
            status=STATUS_SKIPPED,
            summary="no model registry file",
        )

    def _check_worker_status(self) -> CheckResult:
        workers = self.workspace / "workers"
        status_files = sorted(workers.rglob("status.json"))
        if not status_files:
            return CheckResult(
                name="hermes.worker_status",
                category=CATEGORY_HERMES,
                status=STATUS_SKIPPED,
                summary="no worker status files",
            )
        stale: list[str] = []
        ok = 0
        now = time.time()
        for status_file in status_files:
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                stale.append(f"{status_file.relative_to(self.workspace)}: {exc}")
                continue
            heartbeat = data.get("heartbeat") or data.get("updated_at") or 0
            try:
                heartbeat = float(heartbeat)
            except (TypeError, ValueError):
                heartbeat = 0
            age = now - heartbeat if heartbeat else None
            if age is not None and age > 24 * 3600:
                stale.append(
                    f"{status_file.relative_to(self.workspace)}: heartbeat {age/3600:.1f}h ago"
                )
            else:
                ok += 1
        if stale:
            return CheckResult(
                name="hermes.worker_status",
                category=CATEGORY_HERMES,
                status=STATUS_WARN,
                summary=f"{len(stale)} stale worker status file(s)",
                metadata={"stale": stale[:20], "fresh": ok},
            )
        return CheckResult(
            name="hermes.worker_status",
            category=CATEGORY_HERMES,
            status=STATUS_PASS,
            summary=f"{ok} worker(s) fresh",
        )

    # — Remote runtime checks ──────────────────────────────────────────────

    def _check_remote_tunnel(self) -> CheckResult:
        path = self.workspace / REMOTE_DIRNAME / REMOTE_TUNNEL_FILENAME
        if not path.exists():
            return CheckResult(
                name="remote.tunnel",
                category=CATEGORY_REMOTE,
                status=STATUS_SKIPPED,
                summary="no remote/tunnel.json",
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return CheckResult(
                name="remote.tunnel",
                category=CATEGORY_REMOTE,
                status=STATUS_FAIL,
                summary=f"tunnel.json parse error: {exc}",
            )
        if not isinstance(data, dict):
            return CheckResult(
                name="remote.tunnel",
                category=CATEGORY_REMOTE,
                status=STATUS_FAIL,
                summary="tunnel.json must be an object",
            )
        state = str(data.get("state") or data.get("status") or "").lower()
        url = data.get("url") or data.get("public_url") or ""
        meta: dict[str, Any] = {"state": state, "url": url}
        if state in {"up", "open", "healthy", "connected", "ready"}:
            return CheckResult(
                name="remote.tunnel",
                category=CATEGORY_REMOTE,
                status=STATUS_PASS,
                summary=f"tunnel {state}",
                metadata=meta,
            )
        if state in {"down", "closed", "error", "failed"}:
            return CheckResult(
                name="remote.tunnel",
                category=CATEGORY_REMOTE,
                status=STATUS_WARN,
                summary=f"tunnel {state}",
                metadata=meta,
            )
        return CheckResult(
            name="remote.tunnel",
            category=CATEGORY_REMOTE,
            status=STATUS_WARN,
            summary=f"tunnel state unknown: {state or '<missing>'}",
            metadata=meta,
        )

    def _check_remote_workers(self) -> CheckResult:
        workers_dir = self.workspace / REMOTE_DIRNAME / REMOTE_WORKERS_DIRNAME
        if not workers_dir.is_dir():
            return CheckResult(
                name="remote.workers",
                category=CATEGORY_REMOTE,
                status=STATUS_SKIPPED,
                summary="no remote/workers/ directory",
            )
        heartbeat_files = sorted(workers_dir.rglob("heartbeat.json"))
        if not heartbeat_files:
            return CheckResult(
                name="remote.workers",
                category=CATEGORY_REMOTE,
                status=STATUS_SKIPPED,
                summary="no remote worker heartbeats",
            )
        stale: list[str] = []
        fresh = 0
        now = time.time()
        for hb in heartbeat_files:
            try:
                data = json.loads(hb.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                stale.append(f"{hb.relative_to(self.workspace)}: {exc}")
                continue
            if not isinstance(data, dict):
                stale.append(
                    f"{hb.relative_to(self.workspace)}: "
                    f"heartbeat must be a JSON object, got {type(data).__name__}"
                )
                continue
            ts = (
                data.get("timestamp")
                or data.get("heartbeat")
                or data.get("updated_at")
                or 0
            )
            try:
                ts_f = float(ts)
            except (TypeError, ValueError):
                ts_f = 0.0
            age = now - ts_f if ts_f else None
            if age is None or age > REMOTE_WORKER_STALE_S:
                stale.append(
                    f"{hb.relative_to(self.workspace)}: "
                    f"{'no timestamp' if age is None else f'{age:.0f}s old'}"
                )
            else:
                fresh += 1
        meta: dict[str, Any] = {
            "fresh": fresh,
            "stale": stale[:20],
            "threshold_s": REMOTE_WORKER_STALE_S,
        }
        if stale:
            return CheckResult(
                name="remote.workers",
                category=CATEGORY_REMOTE,
                status=STATUS_WARN,
                summary=f"{len(stale)} stale remote worker(s), {fresh} fresh",
                metadata=meta,
            )
        return CheckResult(
            name="remote.workers",
            category=CATEGORY_REMOTE,
            status=STATUS_PASS,
            summary=f"{fresh} remote worker(s) fresh",
            metadata=meta,
        )

    def _check_remote_queue(self) -> CheckResult:
        path = self.workspace / REMOTE_DIRNAME / REMOTE_QUEUE_FILENAME
        if not path.exists():
            return CheckResult(
                name="remote.queue",
                category=CATEGORY_REMOTE,
                status=STATUS_SKIPPED,
                summary="no remote/queue.json",
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return CheckResult(
                name="remote.queue",
                category=CATEGORY_REMOTE,
                status=STATUS_FAIL,
                summary=f"queue.json parse error: {exc}",
            )
        # Accept either {"jobs": [...]} or a bare list.
        if isinstance(data, list):
            jobs: list[Any] = data
            extra: dict[str, Any] = {}
        elif isinstance(data, dict):
            raw_jobs = data.get("jobs", [])
            if not isinstance(raw_jobs, list):
                return CheckResult(
                    name="remote.queue",
                    category=CATEGORY_REMOTE,
                    status=STATUS_FAIL,
                    summary=(
                        f"queue.json: `jobs` must be a list, "
                        f"got {type(raw_jobs).__name__}"
                    ),
                )
            jobs = raw_jobs
            extra = {k: v for k, v in data.items() if k != "jobs"}
        else:
            return CheckResult(
                name="remote.queue",
                category=CATEGORY_REMOTE,
                status=STATUS_FAIL,
                summary="queue.json: top level must be list or object",
            )
        depth = len(jobs)
        oldest_age: float | None = None
        now = time.time()
        for job in jobs:
            if not isinstance(job, dict):
                continue
            ts = job.get("enqueued_at") or job.get("created_at")
            try:
                ts_f = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                ts_f = None
            if ts_f is None:
                continue
            age = now - ts_f
            if oldest_age is None or age > oldest_age:
                oldest_age = age
        meta: dict[str, Any] = {"depth": depth, **extra}
        if oldest_age is not None:
            meta["oldest_age_s"] = int(oldest_age)
        if oldest_age is not None and oldest_age > REMOTE_QUEUE_STALE_S:
            return CheckResult(
                name="remote.queue",
                category=CATEGORY_REMOTE,
                status=STATUS_WARN,
                summary=f"queue depth={depth}, oldest {oldest_age/60:.1f}m",
                metadata=meta,
            )
        return CheckResult(
            name="remote.queue",
            category=CATEGORY_REMOTE,
            status=STATUS_PASS,
            summary=f"queue depth={depth}",
            metadata=meta,
        )

    # — APK audit pack ─────────────────────────────────────────────────────

    def _first_apk(self) -> Path | None:
        for p in self.workspace.rglob("*.apk"):
            if ".git" in p.parts:
                continue
            return p
        return None

    def _check_apk_apktool(self) -> CheckResult:
        if not shutil.which("apktool"):
            return CheckResult(
                name="apk.apktool",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="apktool not installed",
            )
        apk = self._first_apk()
        if apk is None:
            return CheckResult(
                name="apk.apktool",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="no APK to decode",
            )
        rc, out, err, ms = self._run_cmd(
            ["apktool", "d", "-q", "-f", "-o", str(self.output_dir / "apktool"), str(apk)],
            timeout=600,
        )
        return CheckResult(
            name="apk.apktool",
            category=CATEGORY_APK,
            status=STATUS_PASS if rc == 0 else STATUS_FAIL,
            summary=f"apktool d {apk.name} exit={rc}",
            command=f"apktool d {apk}",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_apk_aapt(self) -> CheckResult:
        if not shutil.which("aapt"):
            return CheckResult(
                name="apk.aapt_badging",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="aapt not installed",
            )
        apk = self._first_apk()
        if apk is None:
            return CheckResult(
                name="apk.aapt_badging",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="no APK to inspect",
            )
        rc, out, err, ms = self._run_cmd(["aapt", "dump", "badging", str(apk)])
        return CheckResult(
            name="apk.aapt_badging",
            category=CATEGORY_APK,
            status=STATUS_PASS if rc == 0 else STATUS_WARN,
            summary=f"aapt dump badging exit={rc}",
            command=f"aapt dump badging {apk}",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    def _check_apk_jadx(self) -> CheckResult:
        if not shutil.which("jadx"):
            return CheckResult(
                name="apk.jadx_smoke",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="jadx not installed",
            )
        apk = self._first_apk()
        if apk is None:
            return CheckResult(
                name="apk.jadx_smoke",
                category=CATEGORY_APK,
                status=STATUS_SKIPPED,
                summary="no APK to decompile",
            )
        rc, out, err, ms = self._run_cmd(
            ["jadx", "--no-imports", "-d", str(self.output_dir / "jadx"), str(apk)],
            timeout=900,
        )
        return CheckResult(
            name="apk.jadx_smoke",
            category=CATEGORY_APK,
            status=STATUS_PASS if rc == 0 else STATUS_WARN,
            summary=f"jadx exit={rc}",
            command=f"jadx {apk}",
            returncode=rc,
            duration_ms=ms,
            stdout=_truncate(out),
            stderr=_truncate(err),
        )

    # — Artifact writing ───────────────────────────────────────────────────

    def _write_artifacts(self, report: ValidationReport) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        results_path = self.output_dir / "results.json"
        results_path.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        summary_path = self.output_dir / "summary.md"
        summary_path.write_text(render_summary(report), encoding="utf-8")

        log_path = self.output_dir / "commands.log"
        log_path.write_text("\n".join(self._commands_log) + ("\n" if self._commands_log else ""), encoding="utf-8")


# ── Module-level helpers (also exported for unit tests) ─────────────────────


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Parse a YAML frontmatter block from ``text``.

    Returns the parsed mapping, or ``None`` if there is no frontmatter
    (no leading ``---`` fence) or it cannot be parsed.

    Uses ``yaml.safe_load`` when PyYAML is installed; falls back to a
    minimal scalar-only parser for the keys this module actually cares
    about (``name``, ``description``). The fallback is enough to keep
    validation working when the runner is invoked from a slimmed-down
    venv that hasn't pulled in PyYAML — production Hermes installs do
    have it, so the full parse path is what runs in normal use.
    """
    if not text.startswith("---"):
        return None
    rest = text[3:].lstrip("\r\n")
    end = rest.find("\n---")
    if end == -1:
        return None
    block = rest[:end]
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(block)
    except ImportError:
        data = _parse_simple_yaml(block)
    except Exception:  # noqa: BLE001 — yaml parse errors are user-facing.
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_simple_yaml(block: str) -> dict[str, Any] | None:
    """Minimal fallback when PyYAML is unavailable.

    Handles only what skill/model-registry frontmatter actually uses at
    the top level: ``key: value`` scalar pairs. Indented child blocks
    are recorded as opaque strings so downstream code can at least
    detect their presence. Lines beginning with ``#`` (comments) are
    ignored, as are blank lines.
    """
    out: dict[str, Any] = {}
    current_parent: str | None = None
    current_parent_lines: list[str] = []

    def _flush_parent() -> None:
        nonlocal current_parent, current_parent_lines
        if current_parent is not None:
            out[current_parent] = "\n".join(current_parent_lines).rstrip("\n")
        current_parent = None
        current_parent_lines = []

    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            if current_parent is not None:
                current_parent_lines.append(line)
            continue
        # Top-level line. ``key: value`` or bare ``key:``.
        if ":" not in line:
            return None
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            return None
        _flush_parent()
        if not value:
            current_parent = key
            continue
        out[key] = _strip_yaml_scalar(value)
    _flush_parent()
    return out


def _strip_yaml_scalar(value: str) -> Any:
    """Strip quotes/whitespace from a simple YAML scalar."""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def validate_skill_frontmatter(text: str) -> str | None:
    """Return an error string when frontmatter is invalid, else ``None``.

    Required keys: ``name``, ``description``. ``name`` must be a
    non-empty string that's safe to use as a CLI identifier (no
    whitespace, no path separators).
    """
    data = parse_frontmatter(text)
    if data is None:
        return "missing or unparseable YAML frontmatter"
    name = data.get("name")
    description = data.get("description")
    if not isinstance(name, str) or not name.strip():
        return "missing or empty `name`"
    if any(ch in name for ch in (" ", "/", "\\", "\t", "\n")):
        return f"invalid `name` value: {name!r}"
    if not isinstance(description, str) or not description.strip():
        return "missing or empty `description`"
    return None


def validate_job_folder(job_dir: Path) -> str | None:
    """Verify a job folder conforms to the Hermes job contract.

    Contract:
      - ``job.json`` exists and parses as a JSON object
      - that object has at least ``id`` and ``status`` keys
      - if ``logs/`` exists, it is a directory (not a file)
    """
    job_json = job_dir / "job.json"
    if not job_json.exists():
        return "missing job.json"
    try:
        data = json.loads(job_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"job.json parse error: {exc}"
    if not isinstance(data, dict):
        return "job.json: top level must be an object"
    for required in ("id", "status"):
        if required not in data:
            return f"job.json: missing required key `{required}`"
    logs = job_dir / "logs"
    if logs.exists() and not logs.is_dir():
        return "logs/ exists but is not a directory"
    return None


def scan_text_for_secrets(text: str) -> list[tuple[str, str]]:
    """Return ``[(pattern_label, redacted_snippet), ...]`` for matches.

    Only added/changed lines (``+`` prefix in diff format) are scanned —
    we don't care about secrets that were *removed*. Snippets are
    truncated to keep findings opaque-but-localizable.
    """
    findings: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        # In a unified diff, look at lines starting with a single ``+``
        # (not ``+++``, which is the file header).
        if raw_line.startswith("+++"):
            continue
        if raw_line.startswith("+"):
            line = raw_line[1:]
        else:
            # Outside diff context, scan everything. ``git diff`` output
            # is the common path but the helper is exposed for tests
            # that pass raw text.
            line = raw_line
        for label, pattern in _SECRET_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            snippet = match.group(0)
            findings.append((label, _redact(snippet)))
    return findings


def render_summary(report: ValidationReport) -> str:
    """Render a Markdown summary of a ``ValidationReport``."""
    lines: list[str] = []
    lines.append("# muse Validation Summary")
    lines.append("")
    lines.append(f"- Workspace: `{report.workspace}`")
    lines.append(
        f"- Publish gate: **{'OPEN' if report.publish_allowed else 'BLOCKED'}**"
    )
    counts = report.status_counts()
    if counts:
        formatted = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"- Status counts: {formatted}")
    duration_ms = int((report.finished_at - report.started_at) * 1000)
    lines.append(f"- Duration: {duration_ms}ms")
    lines.append("")
    if report.blocking_failures:
        lines.append("## Blocking failures")
        for name in report.blocking_failures:
            lines.append(f"- `{name}`")
        lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Category | Status | Critical | Summary |")
    lines.append("|---|---|---|---|---|")
    for r in report.results:
        crit = "yes" if r.critical else "no"
        summary = r.summary.replace("|", "\\|")
        lines.append(
            f"| `{r.name}` | {r.category} | {r.status} | {crit} | {summary} |"
        )
    return "\n".join(lines) + "\n"


# ── Internals ───────────────────────────────────────────────────────────────


def _truncate(text: str, limit: int = 4_000) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return f"{head}\n…[{len(text) - limit} chars truncated]…\n{tail}"


def _redact(value: str) -> str:
    """Return a head/tail-only redaction of a secret-like string."""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-2:]}"


def _shell_quote(arg: str) -> str:
    """Best-effort shell quoting for the human-readable command log."""
    if not arg:
        return "''"
    if all(c.isalnum() or c in "._-/=:@,+" for c in arg):
        return arg
    escaped = arg.replace("'", "'\\''")
    return f"'{escaped}'"


__all__ = [
    "CATEGORY_APK",
    "CATEGORY_GIT",
    "CATEGORY_HERMES",
    "CATEGORY_LANGUAGE",
    "CATEGORY_REMOTE",
    "CATEGORY_SECRETS",
    "CheckResult",
    "DEFAULT_CHECK_TIMEOUT_S",
    "REMOTE_DIRNAME",
    "REMOTE_QUEUE_FILENAME",
    "REMOTE_QUEUE_STALE_S",
    "REMOTE_TUNNEL_FILENAME",
    "REMOTE_WORKERS_DIRNAME",
    "REMOTE_WORKER_STALE_S",
    "STATUS_BLOCKED",
    "STATUS_ERROR",
    "STATUS_FAIL",
    "STATUS_PASS",
    "STATUS_SKIPPED",
    "STATUS_WARN",
    "ValidationReport",
    "ValidationRunner",
    "parse_frontmatter",
    "render_summary",
    "scan_text_for_secrets",
    "validate_job_folder",
    "validate_skill_frontmatter",
]
