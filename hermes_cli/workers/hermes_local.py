"""Hermes Local worker — repo evidence, file inventory, validation
command discovery, Git state, and publish prep.

Hermes Local is the always-available worker. It runs only against the
local filesystem and a small set of read-only ``git`` invocations; it
never touches the network, never executes project tests or build
commands, and never modifies files outside its own output directories.
Its job is to *discover* commands and surface evidence, leaving
execution to later phases.

Outputs (written under ``output_base``):

* ``shared-context/repo-map.md``  — top-level file map + entrypoints.
* ``shared-context/evidence.md``  — language/framework/package-manager
  evidence, risky files, doc entrypoints.
* ``shared-context/test-map.md``  — inferred validation commands per
  source file (pyproject, package.json, Makefile, README, AGENTS.md).
* ``shared-context/git-state.md`` — branch + ``git status --porcelain``.
* ``workers/hermes-local/output.md``  — human-readable run summary.
* ``workers/hermes-local/status.json`` — machine-readable status.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


# Files we look at to infer test/build/validation commands.
_VALIDATION_SOURCES = (
    "pyproject.toml",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Makefile",
    "GNUmakefile",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
)

# Files that, if present at the repo root, identify a language/runtime.
_LANGUAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"),
    "javascript": ("package.json", "package-lock.json"),
    "typescript": ("tsconfig.json",),
    "node": ("package.json",),
    "rust": ("Cargo.toml",),
    "go": ("go.mod",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts"),
    "kotlin": ("build.gradle.kts", "settings.gradle.kts"),
    "ruby": ("Gemfile",),
    "php": ("composer.json",),
    "docker": ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"),
    "nix": ("flake.nix", "shell.nix", "default.nix"),
}

_PACKAGE_MANAGER_MARKERS: dict[str, tuple[str, ...]] = {
    "pip": ("requirements.txt",),
    "uv": ("uv.lock", "pyproject.toml"),
    "poetry": ("poetry.lock",),
    "pipenv": ("Pipfile.lock", "Pipfile"),
    "npm": ("package-lock.json",),
    "pnpm": ("pnpm-lock.yaml",),
    "yarn": ("yarn.lock",),
    "bun": ("bun.lockb", "bun.lock"),
    "cargo": ("Cargo.lock",),
    "go-modules": ("go.sum",),
    "gradle": ("build.gradle", "build.gradle.kts"),
    "maven": ("pom.xml",),
    "make": ("Makefile", "GNUmakefile"),
}

# Filenames / patterns we flag as risky to touch or commit.
_RISKY_FILENAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "service-account.json",
})

_RISKY_SUFFIXES = (".pem", ".key", ".crt", ".pfx", ".p12", ".keystore", ".jks")

_DOC_ENTRYPOINT_CANDIDATES = (
    "README.md",
    "README.rst",
    "README",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "LICENSE",
    "docs/index.md",
    "docs/README.md",
)


@dataclass
class TestCommand:
    """One inferred validation command and where we found it."""

    # Tell pytest not to collect this dataclass as a test class.
    __test__ = False

    source: str        # e.g. "pyproject.toml", "Makefile"
    label: str         # human-friendly name, e.g. "pytest", "make test"
    command: str       # the actual command string

    def as_dict(self) -> dict:
        return {"source": self.source, "label": self.label, "command": self.command}


@dataclass
class WorkerStatus:
    """Machine-readable status emitted as status.json."""

    worker: str = "hermes-local"
    available: bool = True
    ok: bool = True
    started_at: str = ""
    finished_at: str = ""
    errors: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "worker": self.worker,
            "available": self.available,
            "ok": self.ok,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "errors": list(self.errors),
            "artifacts": list(self.artifacts),
        }


class HermesLocalWorker:
    """Always-available worker producing local repo evidence.

    Construct with ``root`` (the repo to inspect) and optionally
    ``output_base`` (where ``shared-context/`` and ``workers/`` are
    written). When ``output_base`` is None, outputs land under ``root``.
    """

    name = "hermes-local"

    def __init__(
        self,
        root: Path | str,
        output_base: Optional[Path | str] = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.output_base = (
            Path(output_base).resolve() if output_base is not None else self.root
        )

    # ── availability ────────────────────────────────────────────────────

    @classmethod
    def is_available(cls) -> bool:
        """Hermes Local has no external dependencies — always available."""
        return True

    # ── discovery primitives ───────────────────────────────────────────

    def top_level_map(self, limit: int = 200) -> list[dict]:
        """List the repo's top-level entries (sorted, dirs first).

        Returns at most ``limit`` entries. Hidden dot-entries are kept
        because they often carry signal (``.github/``, ``.env.example``).
        """
        if not self.root.exists():
            return []
        entries: list[dict] = []
        for child in sorted(self.root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            entries.append({
                "name": child.name,
                "kind": "dir" if child.is_dir() else "file",
            })
            if len(entries) >= limit:
                break
        return entries

    def detect_languages(self) -> list[str]:
        """Return language/runtime tags inferred from marker files."""
        found: list[str] = []
        for lang, markers in _LANGUAGE_MARKERS.items():
            if any((self.root / m).exists() for m in markers):
                found.append(lang)
        return found

    def detect_package_managers(self) -> list[str]:
        """Return package-manager tags inferred from lockfiles + manifests."""
        found: list[str] = []
        for pm, markers in _PACKAGE_MANAGER_MARKERS.items():
            if any((self.root / m).exists() for m in markers):
                found.append(pm)
        return found

    def detect_test_commands(self) -> list[TestCommand]:
        """Walk known source files and propose validation commands.

        This *infers* commands; it never executes them.
        """
        cmds: list[TestCommand] = []
        for source in _VALIDATION_SOURCES:
            path = self.root / source
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            cmds.extend(_infer_from_file(source, text))
        return _dedup_commands(cmds)

    def inspect_git_state(self) -> dict:
        """Read the current branch and porcelain status.

        Returns a dict with ``branch``, ``status`` (a list of porcelain
        lines), ``is_git_repo``, and any ``error`` we hit. We never
        modify the working tree.
        """
        if not (self.root / ".git").exists():
            return {
                "is_git_repo": False,
                "branch": "",
                "status": [],
                "error": "",
            }
        branch = _git(self.root, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        status_raw = _git(self.root, ["status", "--porcelain"])
        status_lines = [ln for ln in status_raw.splitlines() if ln.strip()]
        return {
            "is_git_repo": True,
            "branch": branch,
            "status": status_lines,
            "error": "",
        }

    def find_scripts(self) -> list[str]:
        """List candidate user-facing scripts under ``scripts/`` and ``bin/``."""
        out: list[str] = []
        for sub in ("scripts", "bin", "tools"):
            d = self.root / sub
            if not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.is_file():
                    out.append(f"{sub}/{p.name}")
        # Top-level executables / shell scripts.
        for p in sorted(self.root.iterdir()):
            if not p.is_file():
                continue
            if p.suffix in (".sh", ".ps1", ".cmd", ".bat"):
                out.append(p.name)
        return out

    def find_risky_files(self) -> list[str]:
        """Surface files whose presence at the repo root is a risk to commit."""
        out: list[str] = []
        if not self.root.is_dir():
            return out
        for p in sorted(self.root.iterdir()):
            if not p.is_file():
                continue
            name = p.name
            if name in _RISKY_FILENAMES or name.endswith(_RISKY_SUFFIXES):
                out.append(name)
        return out

    def find_docs_entrypoints(self) -> list[str]:
        """List doc entrypoints that exist in the repo."""
        out: list[str] = []
        for rel in _DOC_ENTRYPOINT_CANDIDATES:
            if (self.root / rel).exists():
                out.append(rel)
        return out

    # ── output writers ─────────────────────────────────────────────────

    def _shared_context_dir(self) -> Path:
        return self.output_base / "shared-context"

    def _worker_dir(self) -> Path:
        return self.output_base / "workers" / self.name

    def write_repo_map(self, entries: Iterable[dict]) -> Path:
        path = self._shared_context_dir() / "repo-map.md"
        lines = ["# Repo map", "", f"Root: `{self.root}`", "", "## Top level", ""]
        for e in entries:
            marker = "/" if e["kind"] == "dir" else ""
            lines.append(f"- `{e['name']}{marker}`")
        _atomic_write(path, "\n".join(lines).rstrip() + "\n")
        return path

    def write_evidence(
        self,
        languages: list[str],
        package_managers: list[str],
        risky_files: list[str],
        docs_entrypoints: list[str],
        scripts: list[str],
    ) -> Path:
        path = self._shared_context_dir() / "evidence.md"
        lines = [
            "# Repo evidence",
            "",
            "## Languages / runtimes detected",
            "",
        ]
        lines.extend(f"- {x}" for x in languages) if languages else lines.append("- (none detected)")
        lines += ["", "## Package managers detected", ""]
        lines.extend(f"- {x}" for x in package_managers) if package_managers else lines.append("- (none detected)")
        lines += ["", "## Scripts", ""]
        lines.extend(f"- `{x}`" for x in scripts) if scripts else lines.append("- (none found)")
        lines += ["", "## Risky files at repo root", ""]
        lines.extend(f"- `{x}`" for x in risky_files) if risky_files else lines.append("- (none found)")
        lines += ["", "## Docs entrypoints", ""]
        lines.extend(f"- `{x}`" for x in docs_entrypoints) if docs_entrypoints else lines.append("- (none found)")
        _atomic_write(path, "\n".join(lines).rstrip() + "\n")
        return path

    def write_test_map(self, commands: list[TestCommand]) -> Path:
        path = self._shared_context_dir() / "test-map.md"
        lines = [
            "# Validation command map",
            "",
            "These commands were *inferred* from repo files, not executed.",
            "Phase 08 (muse local) discovers; later phases choose what to run.",
            "",
        ]
        if not commands:
            lines += ["No validation commands inferred.", ""]
        else:
            grouped: dict[str, list[TestCommand]] = {}
            for c in commands:
                grouped.setdefault(c.source, []).append(c)
            for source, items in grouped.items():
                lines.append(f"## From `{source}`")
                lines.append("")
                for c in items:
                    lines.append(f"- **{c.label}** — `{c.command}`")
                lines.append("")
        _atomic_write(path, "\n".join(lines).rstrip() + "\n")
        return path

    def write_git_state(self, state: dict) -> Path:
        path = self._shared_context_dir() / "git-state.md"
        lines = ["# Git state", ""]
        if not state.get("is_git_repo"):
            lines += ["Not a git repository.", ""]
        else:
            lines += [
                f"- Branch: `{state.get('branch', '') or '(detached)'}`",
                "",
                "## `git status --porcelain`",
                "",
            ]
            status = state.get("status") or []
            if not status:
                lines.append("(clean)")
            else:
                lines.append("```")
                lines.extend(status)
                lines.append("```")
        _atomic_write(path, "\n".join(lines).rstrip() + "\n")
        return path

    def write_worker_output(
        self,
        languages: list[str],
        package_managers: list[str],
        commands: list[TestCommand],
        git_state: dict,
        artifacts: list[str],
    ) -> Path:
        path = self._worker_dir() / "output.md"
        lines = [
            f"# muse local — run summary",
            "",
            f"- Root: `{self.root}`",
            f"- Output base: `{self.output_base}`",
            f"- Languages: {', '.join(languages) or '(none)'}",
            f"- Package managers: {', '.join(package_managers) or '(none)'}",
            f"- Validation commands inferred: {len(commands)}",
            f"- Git repo: {'yes' if git_state.get('is_git_repo') else 'no'}",
        ]
        if git_state.get("is_git_repo"):
            lines.append(f"- Git branch: `{git_state.get('branch', '') or '(detached)'}`")
            lines.append(f"- Working tree changes: {len(git_state.get('status') or [])}")
        lines += ["", "## Artifacts written", ""]
        for a in artifacts:
            lines.append(f"- `{a}`")
        _atomic_write(path, "\n".join(lines).rstrip() + "\n")
        return path

    def write_status(self, status: WorkerStatus) -> Path:
        path = self._worker_dir() / "status.json"
        _atomic_write(path, json.dumps(status.as_dict(), indent=2, sort_keys=True) + "\n")
        return path

    # ── top-level entry point ──────────────────────────────────────────

    def run(self) -> WorkerStatus:
        """Gather evidence and write all artifacts. Never raises on
        repo-shape problems — failures are captured in
        ``WorkerStatus.errors`` so callers can decide how to react.
        """
        status = WorkerStatus(started_at=_utcnow())
        status_rel = self._rel("workers", self.name, "status.json")
        try:
            self._shared_context_dir().mkdir(parents=True, exist_ok=True)
            self._worker_dir().mkdir(parents=True, exist_ok=True)

            entries = self.top_level_map()
            languages = self.detect_languages()
            package_managers = self.detect_package_managers()
            commands = self.detect_test_commands()
            git_state = self.inspect_git_state()
            risky = self.find_risky_files()
            docs = self.find_docs_entrypoints()
            scripts = self.find_scripts()

            artifacts: list[str] = [
                self._rel("shared-context", "repo-map.md"),
                self._rel("shared-context", "evidence.md"),
                self._rel("shared-context", "test-map.md"),
                self._rel("shared-context", "git-state.md"),
                self._rel("workers", self.name, "output.md"),
                status_rel,
            ]
            self.write_repo_map(entries)
            self.write_evidence(languages, package_managers, risky, docs, scripts)
            self.write_test_map(commands)
            self.write_git_state(git_state)
            self.write_worker_output(
                languages, package_managers, commands, git_state, artifacts,
            )
            status.artifacts = artifacts
        except Exception as exc:
            status.ok = False
            status.errors.append(f"{type(exc).__name__}: {exc}")
            if not status.artifacts:
                status.artifacts = [status_rel]
        status.finished_at = _utcnow()
        # status.json is always written, even on failure — callers need
        # to see why a run failed without re-running the worker.
        try:
            self._worker_dir().mkdir(parents=True, exist_ok=True)
            self.write_status(status)
        except OSError as exc:
            status.errors.append(f"status-write-failed: {exc}")
        return status

    def _rel(self, *parts: str) -> str:
        """POSIX-style relative path used in artifact listings."""
        return "/".join(parts)


# ── helpers ───────────────────────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a same-directory tempfile rename.

    Same-directory rename is atomic on POSIX and best-effort on Windows;
    we use it so a half-written status.json never confuses a reader.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _git(root: Path, args: list[str], *, timeout: float = 5.0) -> str:
    """Run a read-only ``git`` command and return stdout (empty on failure)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""
    return result.stdout or ""


def _dedup_commands(commands: list[TestCommand]) -> list[TestCommand]:
    """Drop exact duplicates while preserving source/label provenance order."""
    seen: set[tuple[str, str, str]] = set()
    out: list[TestCommand] = []
    for c in commands:
        key = (c.source, c.label, c.command)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ── per-source command extractors ─────────────────────────────────────


def _infer_from_file(source: str, text: str) -> list[TestCommand]:
    """Dispatch to the right extractor for a known source file."""
    if source == "pyproject.toml":
        return _infer_from_pyproject(text)
    if source == "package.json":
        return _infer_from_package_json(text)
    if source in ("pnpm-lock.yaml", "yarn.lock"):
        return _infer_from_js_lockfile(source, text)
    if source in ("Makefile", "GNUmakefile"):
        return _infer_from_makefile(text)
    if source.startswith("build.gradle") or source.startswith("settings.gradle"):
        return _infer_from_gradle(text)
    if source in ("README.md", "AGENTS.md", "CONTRIBUTING.md"):
        return _infer_from_markdown(source, text)
    return []


_PYTEST_LINE = re.compile(r"^\s*\[tool\.pytest", re.MULTILINE)
_PYPROJECT_TEST_SCRIPT = re.compile(
    r'^\s*"?(test|tests|lint|typecheck|check)"?\s*=\s*"([^"\n]+)"',
    re.MULTILINE,
)


def _infer_from_pyproject(text: str) -> list[TestCommand]:
    out: list[TestCommand] = []
    if _PYTEST_LINE.search(text):
        out.append(TestCommand("pyproject.toml", "pytest", "pytest"))
        out.append(TestCommand("pyproject.toml", "pytest -q", "python -m pytest -q"))
    if "[tool.ty" in text:
        out.append(TestCommand("pyproject.toml", "ty check", "ty check"))
    if "[tool.ruff" in text:
        out.append(TestCommand("pyproject.toml", "ruff check", "ruff check ."))
    if "[tool.mypy" in text:
        out.append(TestCommand("pyproject.toml", "mypy", "mypy ."))
    for m in _PYPROJECT_TEST_SCRIPT.finditer(text):
        name, cmd = m.group(1), m.group(2)
        out.append(TestCommand("pyproject.toml", f"script:{name}", cmd))
    return out


_PACKAGE_JSON_SCRIPT = re.compile(r'"([a-zA-Z0-9:_\-]+)"\s*:\s*"([^"]+)"')


def _infer_from_package_json(text: str) -> list[TestCommand]:
    out: list[TestCommand] = []
    try:
        data = json.loads(text)
    except (ValueError, json.JSONDecodeError):
        return out
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return out
    for name, cmd in scripts.items():
        if not isinstance(name, str) or not isinstance(cmd, str):
            continue
        if name.lower() in {"test", "lint", "typecheck", "build", "check", "verify"}:
            out.append(TestCommand("package.json", f"npm run {name}", f"npm run {name}"))
    return out


def _infer_from_js_lockfile(source: str, text: str) -> list[TestCommand]:
    # Lockfile presence tells us which package manager to prefer; the
    # commands themselves come from package.json (the caller will have
    # added them already). We surface a "fallback" entry so consumers can
    # tell which PM the repo actually uses.
    pm = "pnpm" if source == "pnpm-lock.yaml" else "yarn"
    return [TestCommand(source, f"{pm} test", f"{pm} test")]


_MAKEFILE_TARGET = re.compile(r"^([a-zA-Z][a-zA-Z0-9_\-]*)\s*:", re.MULTILINE)


def _infer_from_makefile(text: str) -> list[TestCommand]:
    out: list[TestCommand] = []
    for m in _MAKEFILE_TARGET.finditer(text):
        target = m.group(1)
        if target.lower() in {"test", "tests", "lint", "check", "ci", "verify", "typecheck"}:
            out.append(TestCommand("Makefile", f"make {target}", f"make {target}"))
    return out


def _infer_from_gradle(text: str) -> list[TestCommand]:
    out: list[TestCommand] = []
    if "task" in text or "tasks" in text or "plugins" in text:
        out.append(TestCommand("gradle", "gradle test", "./gradlew test"))
        out.append(TestCommand("gradle", "gradle check", "./gradlew check"))
    return out


_MD_CODE_BLOCK = re.compile(r"```(?:bash|sh|shell|console)?\n(.*?)```", re.DOTALL)
_CMD_HINT = re.compile(
    r"^\s*\$?\s*((?:python\s+-m\s+pytest|pytest|pnpm\s+test|npm\s+test|yarn\s+test|"
    r"make\s+test|cargo\s+test|go\s+test|ruff\s+check|mypy|ty\s+check)\b[^\n]*)",
    re.MULTILINE,
)


def _infer_from_markdown(source: str, text: str) -> list[TestCommand]:
    out: list[TestCommand] = []
    seen: set[str] = set()
    for block in _MD_CODE_BLOCK.finditer(text):
        body = block.group(1)
        for m in _CMD_HINT.finditer(body):
            cmd = m.group(1).strip()
            if cmd in seen:
                continue
            seen.add(cmd)
            out.append(TestCommand(source, cmd.split()[0], cmd))
    return out
