"""Run language quality gates defined under ``~/.hermes/quality_gates/``."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from hermes_cli.harness.config import CODE_EXTENSIONS, HarnessSettings

logger = logging.getLogger(__name__)

_EXT_TO_GATE = {
    ".py": "python.yaml",
    ".js": "javascript.yaml",
    ".jsx": "javascript.yaml",
    ".ts": "javascript.yaml",
    ".tsx": "javascript.yaml",
    ".go": "go.yaml",
    ".rs": "rust.yaml",
}

_BLOCKING = frozenset({"blocker", "critical"})


@dataclass
class GateStepResult:
    name: str
    severity: str
    ok: bool
    skipped: bool = False
    output: str = ""
    auto_fix: bool = False


@dataclass
class GateRunResult:
    ok: bool
    language: str
    gate_file: str
    steps: List[GateStepResult] = field(default_factory=list)
    should_escalate: bool = False
    summary: str = ""

    def blocking_failures(self) -> List[GateStepResult]:
        return [s for s in self.steps if not s.ok and not s.skipped and s.severity in _BLOCKING]


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("quality_gates: failed to read %s: %s", path, exc)
        return {}
    return data if isinstance(data, Mapping) else {}


def resolve_gate_file(settings: HarnessSettings, path: Path) -> Optional[Path]:
    directory = settings.quality_gates_directory
    if directory is None:
        return None
    if settings.quality_auto_detect_language:
        name = _EXT_TO_GATE.get(path.suffix.lower())
    else:
        name = None
    name = name or settings.quality_default_gate
    candidate = Path(directory) / name
    return candidate if candidate.is_file() else None


def find_project_root(path: Path) -> Path:
    cur = path.resolve().parent
    markers = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", ".git")
    for _ in range(12):
        for m in markers:
            if (cur / m).exists():
                return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return path.resolve().parent


def _command_available(command: str) -> bool:
    exe = command.strip().split()[0] if command.strip() else ""
    if not exe:
        return False
    if exe in {"python", "python3", "node", "npx", "go", "cargo", "rustc"}:
        return shutil.which(exe) is not None
    # module form: python -m X — always try
    if exe == "python" or command.strip().startswith("python "):
        return True
    return shutil.which(exe) is not None


def _expand_command(template: str, file_path: Path, project_root: Path) -> str:
    module = file_path.stem
    test_file = file_path.parent / f"test_{file_path.name}"
    # Use POSIX-ish paths in shell snippets so ``python -c "…open('C:\Users…')"``
    # does not hit unicodeescape on Windows.
    file_s = file_path.resolve().as_posix()
    test_s = test_file.resolve().as_posix()
    project_s = project_root.resolve().as_posix()
    cmd = template.replace("{file}", file_s)
    cmd = cmd.replace("{test_file}", test_s)
    cmd = cmd.replace("{module}", module)
    cmd = cmd.replace("{project}", project_s)
    if "tsc --noEmit" in cmd and file_path.suffix.lower() in {".ts", ".tsx"}:
        tsconfig = project_root / "tsconfig.json"
        if tsconfig.is_file():
            cmd = f"npx tsc -p {tsconfig.as_posix()} --pretty false"
    return cmd


def _run_shell(
    command: str,
    cwd: Path,
    *,
    name: str,
    severity: str,
    auto_fix: bool = False,
    skip_if_missing: bool = False,
    timeout: int = 120,
) -> GateStepResult:
    """Run a gate shell command and map exit/timeout into ``GateStepResult``."""
    first = command.strip().split()[0] if command.strip() else ""
    if skip_if_missing and first not in {"python", "python3", "node"}:
        if first not in {"npx", "npm"} and shutil.which(first) is None and not command.strip().startswith("python"):
            return GateStepResult(
                name=name,
                severity=severity,
                ok=True,
                skipped=True,
                output=f"{first} not installed",
                auto_fix=auto_fix,
            )
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        if not ok and skip_if_missing and _looks_like_missing_tool(out, first):
            return GateStepResult(
                name=name, severity=severity, ok=True, skipped=True, output=out[:2000], auto_fix=auto_fix
            )
        return GateStepResult(
            name=name, severity=severity, ok=ok, output=out[:4000], auto_fix=auto_fix
        )
    except subprocess.TimeoutExpired:
        return GateStepResult(
            name=name, severity=severity, ok=False, output="timeout", auto_fix=auto_fix
        )
    except Exception as exc:
        if skip_if_missing:
            return GateStepResult(
                name=name, severity=severity, ok=True, skipped=True, output=str(exc), auto_fix=auto_fix
            )
        return GateStepResult(
            name=name, severity=severity, ok=False, output=str(exc), auto_fix=auto_fix
        )


def run_gate_step(
    *,
    name: str,
    severity: str,
    command: Optional[str],
    check_src: Optional[str],
    auto_fix: bool,
    skip_if_missing: bool,
    file_path: Path,
    project_root: Path,
    timeout: int = 90,
) -> GateStepResult:
    if check_src and not command:
        # Inline python assert checks from YAML — run in isolated eval with file path
        local = {"__builtins__": __builtins__, "os": os}
        try:
            code = check_src.replace("{file}", Path(file_path).resolve().as_posix())
            exec(compile(code, f"<gate:{name}>", "exec"), local, local)
            return GateStepResult(name=name, severity=severity, ok=True, auto_fix=auto_fix)
        except AssertionError as exc:
            # Missing sibling tests etc. — treat as skip when skip_if_missing
            if skip_if_missing:
                return GateStepResult(
                    name=name,
                    severity=severity,
                    ok=True,
                    skipped=True,
                    output=str(exc),
                    auto_fix=auto_fix,
                )
            return GateStepResult(
                name=name, severity=severity, ok=False, output=str(exc), auto_fix=auto_fix
            )
        except Exception as exc:
            if skip_if_missing:
                return GateStepResult(
                    name=name, severity=severity, ok=True, skipped=True, output=str(exc), auto_fix=auto_fix
                )
            return GateStepResult(
                name=name, severity=severity, ok=False, output=str(exc), auto_fix=auto_fix
            )

    if not command:
        return GateStepResult(name=name, severity=severity, ok=True, skipped=True)

    expanded = _expand_command(command, file_path, project_root)
    return _run_shell(
        expanded,
        project_root,
        name=name,
        severity=severity,
        auto_fix=auto_fix,
        skip_if_missing=skip_if_missing,
        timeout=timeout,
    )


def _looks_like_missing_tool(output: str, tool: str) -> bool:
    low = (output or "").lower()
    needles = (
        "not found",
        "not recognized",
        "no module named",
        "cannot find",
        "is not recognized",
        "unrecognized arguments",
        "no such option",
        "file or directory not found",
        "could not determine executable to run",
        "this is not the tsc command you are looking for",
        "eslint couldn't find an eslint.config",
    )
    return any(n in low for n in needles)


def _condition_matches(condition: Optional[str], file_path: Path) -> bool:
    """Evaluate simple gate ``condition`` strings from quality_gates YAML.

    Supported forms (case-insensitive):
      - ``file ends with .ts or .tsx``
      - ``file ends with .js, .jsx, .mjs``
    Unknown / empty conditions default to True (run the gate).
    """
    if not condition or not str(condition).strip():
        return True
    text = str(condition).strip().lower()
    suffix = file_path.suffix.lower()
    if text.startswith("file ends with"):
        rest = text[len("file ends with") :].strip()
        parts = [
            p.strip()
            for chunk in rest.replace(",", " or ").split(" or ")
            for p in [chunk]
            if p.strip()
        ]
        exts: List[str] = []
        for part in parts:
            ext = part if part.startswith(".") else f".{part}"
            exts.append(ext)
        return suffix in exts
    return True


def run_quality_gates(
    settings: HarnessSettings,
    file_path: str | Path,
    *,
    max_autofix_rounds: int = 3,
) -> GateRunResult:
    """Run the matching language gate against *file_path*."""
    path = Path(file_path)
    if path.suffix.lower() not in CODE_EXTENSIONS:
        return GateRunResult(ok=True, language="", gate_file="", summary="non-code skipped")

    if not settings.enabled or not settings.quality_gates_enabled:
        return GateRunResult(ok=True, language="", gate_file="", summary="gates disabled")

    gate_path = resolve_gate_file(settings, path)
    if gate_path is None:
        return GateRunResult(ok=True, language="", gate_file="", summary="no gate file")

    data = _load_yaml(gate_path)
    language = str(data.get("language") or path.suffix)
    steps_cfg = data.get("gates") if isinstance(data.get("gates"), list) else []
    project_root = find_project_root(path)

    all_results: List[GateStepResult] = []
    for _round in range(max(1, max_autofix_rounds)):
        round_results: List[GateStepResult] = []
        ran_autofix = False
        for raw in steps_cfg:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("name") or "unnamed")
            severity = str(raw.get("severity") or "major").lower()
            auto_fix = bool(raw.get("auto_fix", False))
            skip_if_missing = bool(raw.get("skip_if_missing", False))
            command = raw.get("command")
            check_src = raw.get("check")
            condition = raw.get("condition")
            if not _condition_matches(
                str(condition) if condition is not None else None, path
            ):
                round_results.append(
                    GateStepResult(
                        name=name,
                        severity=severity,
                        ok=True,
                        skipped=True,
                        output=f"condition not met: {condition}",
                        auto_fix=auto_fix,
                    )
                )
                continue
            # node --check only understands JS — never use it as a TS blocker.
            cmd_s = str(command) if command else ""
            if (
                cmd_s.strip().startswith("node --check")
                and path.suffix.lower() in {".ts", ".tsx"}
            ):
                round_results.append(
                    GateStepResult(
                        name=name,
                        severity=severity,
                        ok=True,
                        skipped=True,
                        output="node --check skipped for TypeScript (use type_check)",
                        auto_fix=auto_fix,
                    )
                )
                continue
            step = run_gate_step(
                name=name,
                severity=severity,
                command=cmd_s if command else None,
                check_src=str(check_src) if check_src else None,
                auto_fix=auto_fix,
                skip_if_missing=skip_if_missing,
                file_path=path.resolve(),
                project_root=project_root,
            )
            round_results.append(step)
            if auto_fix and not step.ok and not step.skipped:
                ran_autofix = True
        all_results = round_results
        blocking = [s for s in round_results if not s.ok and not s.skipped and s.severity in _BLOCKING]
        if not blocking:
            break
        if not ran_autofix:
            break

    blocking = [s for s in all_results if not s.ok and not s.skipped and s.severity in _BLOCKING]
    ok = len(blocking) == 0
    parts = []
    for s in all_results:
        flag = "SKIP" if s.skipped else ("PASS" if s.ok else "FAIL")
        parts.append(f"{s.name}:{flag}({s.severity})")
    summary = "; ".join(parts)
    return GateRunResult(
        ok=ok,
        language=language,
        gate_file=str(gate_path),
        steps=all_results,
        should_escalate=not ok and settings.auto_escalate,
        summary=summary,
    )


def format_gate_tool_error(result: GateRunResult, file_path: str) -> str:
    lines = [
        f"harness quality gate FAILED for {file_path}",
        f"gate={result.gate_file}",
        f"summary={result.summary}",
        "Write is on disk; fix failures or escalate. Blocking steps:",
    ]
    for s in result.blocking_failures():
        lines.append(f"- {s.name} [{s.severity}]: {(s.output or '')[:500]}")
    if result.should_escalate:
        lines.append("_harness_escalate=true")
    return "\n".join(lines)
