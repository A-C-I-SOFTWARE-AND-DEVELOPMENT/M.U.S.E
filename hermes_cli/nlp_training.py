"""Natural-language compiler training: dataset validation + Together fine-tune dispatch.

This module is the *outbound* half of the JARVIS Prime training pipeline. Where
``hermes_cli/jarvis_prime/nlp_training.py`` exports validated NL-compile traces
*into* the local learning dataset, this module:

1. **Scans** the repo (including gitignored ``data/`` trees) for training JSONL.
2. **Validates** each dataset against strict quality gates (format, secrets,
   duplicates, conversational structure, tool-call JSON, diversity).
3. **Approves** only datasets that pass every gate — recording owner-authorized
   approval metadata.
4. **Dispatches** an owner-gated Together AI LoRA SFT job with duplicate/cost
   guards. A paid job is only ever created with an explicit
   ``--yes-start-paid-training`` flag, a passing dataset, and a present
   ``TOGETHER_API_KEY``.

Provider policy: **Together AI is the default** (active managed fine-tuning,
conversational JSONL + ``check_file`` validation). OpenAI is fallback only (its
fine-tuning platform is winding down). HuggingFace AutoTrain is not selected
(unmaintained). Replicate/Modal are out of scope for the first generic target.

Secrets are read from ``~/.hermes/.env`` (never hardcoded) and are never
printed. The Together SDK is imported lazily so this module stays importable and
testable without it installed.

CLI::

    python -m hermes_cli.nlp_training scan
    python -m hermes_cli.nlp_training validate data/approved/together_train.jsonl
    python -m hermes_cli.nlp_training approve data/approved/together_train.jsonl --only-if-valid
    python -m hermes_cli.nlp_training together-create-job data/approved/together_train.jsonl --yes-start-paid-training
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, cast

# --------------------------------------------------------------------------
# Paths & constants
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
APPROVED_DIR = DATA_DIR / "approved"

INVENTORY_PATH = DATA_DIR / "training_inventory.json"
QUALITY_REPORT_PATH = DATA_DIR / "training_quality_report.json"
SELECTED_PATH = DATA_DIR / "training_selected_dataset.json"
JOBS_PATH = DATA_DIR / "training_jobs.json"

MIN_EXAMPLES = 10
WARN_EXAMPLES = 50
DUP_WARN_RATE = 0.10  # warn when >10% of rows are exact duplicates

DEFAULT_BASE_MODEL = "Qwen/Qwen3-8B"
DEFAULT_HYPERPARAMS: dict[str, Any] = {
    "train_on_inputs": "auto",
    "lora": True,
    "n_epochs": 3,
    "n_checkpoints": 1,
    "learning_rate": 1e-5,
    "warmup_ratio": 0,
    "batch_size": "max",
    "weight_decay": 0,
    "max_grad_norm": 1.0,
}

OWNER_AUTHORIZATION = "explicit authorization in Claude Code prompt"

# Glob patterns to scan (filesystem walk includes gitignored files).
SCAN_GLOBS = (
    "data/**/*.jsonl",
    "source-data/**/*.jsonl",
    "datasets/**/*.jsonl",
    "**/*train*.jsonl",
    "**/*trajectory*.jsonl",
    "**/*trajectories*.jsonl",
    "**/*nl_compile*.jsonl",
    "**/*owner*approved*.jsonl",
)

# Directories never worth scanning for datasets.
_SCAN_EXCLUDE = (".git", "node_modules", ".venv", "venv", "__pycache__")

# Placeholder/low-quality assistant targets (any match => blocking).
_PLACEHOLDER_RE = re.compile(
    r"(?i)\b(todo|tbd|placeholder|your\s+(answer|response|text)\s+here|"
    r"insert\s+(here|response)|lorem ipsum|fill\s+in|xxx+|coming soon)\b"
)

# Secret detectors — labels only are surfaced, never the matched value.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"gh[posru]_[A-Za-z0-9]{30,}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}")),
    ("together_key", re.compile(r"(?i)together[_-]?api[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9]{32,}")),
    ("generic_secret_assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[=:]\s*['\"]?[A-Za-z0-9._\-]{16,}")),
    ("dotenv_credential_line", re.compile(
        r"(?im)^[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\s*=\s*\S+")),
)

_ALLOWED_ROLES = frozenset({"system", "user", "assistant", "tool"})


class TrainingError(RuntimeError):
    """Raised for clean, user-facing failures (no traceback dump in the CLI)."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_signature(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def find_secrets(text: str) -> list[str]:
    """Return the *labels* of any secret types detected (never the values)."""

    return sorted({label for label, pat in _SECRET_PATTERNS if pat.search(text)})


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@dataclass
class ValidationResult:
    path: str
    sha256: str
    size_bytes: int
    num_examples: int
    detected_format: str  # "conversational" | "prompt" | "tool_call" | "unknown" | "empty"
    ok: bool
    blocking_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_rate: float = 0.0
    estimated_trainable_examples: int = 0
    approved_for_training: bool = False
    approval_basis: str = ""
    owner_authorization: str = OWNER_AUTHORIZATION
    category_counts: dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "num_examples": self.num_examples,
            "detected_format": self.detected_format,
            "pass": self.ok,
            "blocking_errors": self.blocking_errors,
            "warnings": self.warnings,
            "duplicate_rate": round(self.duplicate_rate, 4),
            "estimated_trainable_examples": self.estimated_trainable_examples,
            "approved_for_training": self.approved_for_training,
            "approval_basis": self.approval_basis,
            "owner_authorization": self.owner_authorization,
            "category_counts": self.category_counts,
            "timestamp": self.timestamp,
        }


def _detect_format(rows: list[Any]) -> str:
    if not rows:
        return "empty"
    has_messages = any(isinstance(r, dict) and "messages" in r for r in rows)
    has_prompt = any(isinstance(r, dict) and "prompt" in r and "messages" not in r for r in rows)
    has_tool = any(
        isinstance(r, dict)
        and any(isinstance(m, dict) and m.get("tool_calls") for m in (r.get("messages") or []))
        for r in rows
    )
    if has_tool:
        return "tool_call"
    if has_messages:
        return "conversational"
    if has_prompt:
        return "prompt"
    return "unknown"


def _category_of(row: dict[str, Any]) -> str:
    for key in ("category", "task_key", "task_category", "intent"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:40]
    # Fall back to the first few words of the first user message / prompt.
    text = ""
    for m in row.get("messages") or []:
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            text = m["content"]
            break
    if not text and isinstance(row.get("prompt"), str):
        text = row["prompt"]
    words = re.findall(r"[a-zA-Z]+", text.lower())[:3]
    return " ".join(words) or "uncategorized"


def _validate_conversation(row: dict[str, Any], idx: int) -> tuple[list[str], list[str], bool]:
    """Return (errors, warnings, trainable) for a single conversational row."""

    errors: list[str] = []
    warnings: list[str] = []
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        return [f"row {idx}: 'messages' missing or empty"], [], False

    roles = []
    has_tool_msg = False
    assistant_targets = 0
    for j, raw_m in enumerate(messages):
        if not isinstance(raw_m, dict):
            errors.append(f"row {idx} msg {j}: not an object")
            continue
        m = cast("dict[str, Any]", raw_m)
        role = m.get("role")
        if role not in _ALLOWED_ROLES:
            errors.append(f"row {idx} msg {j}: invalid role {role!r}")
            continue
        roles.append(role)
        if role == "tool":
            has_tool_msg = True
        content = m.get("content")
        # content may be legitimately empty on an assistant message that only
        # carries tool_calls; otherwise it must be a non-empty string.
        if role in ("system", "user"):
            if not isinstance(content, str) or not content.strip():
                errors.append(f"row {idx} msg {j}: empty {role} content")
        if role == "assistant":
            tool_calls = m.get("tool_calls")
            if tool_calls:
                _validate_tool_calls(tool_calls, idx, j, errors, warnings)
            if isinstance(content, str) and content.strip():
                assistant_targets += 1
                if _PLACEHOLDER_RE.search(content):
                    errors.append(f"row {idx} msg {j}: placeholder/low-quality assistant target")
                if re.search(r"<think>|</think>|<reasoning>", content, re.I):
                    warnings.append(
                        f"row {idx} msg {j}: reasoning markup in assistant target — strip "
                        "unless the provider expects reasoning fine-tuning")
            elif not tool_calls:
                errors.append(f"row {idx} msg {j}: empty assistant target")
            else:
                assistant_targets += 1  # tool-call-only assistant turn is a valid target

    # Structural: first non-system must be user; assistant must exist.
    non_system = [r for r in roles if r != "system"]
    if non_system and non_system[0] != "user":
        errors.append(f"row {idx}: first non-system message must be 'user', got {non_system[0]!r}")
    if "assistant" not in roles:
        errors.append(f"row {idx}: no assistant message (no training target)")

    # Alternation (strict only when there are no tool messages).
    convo = [r for r in non_system if r in ("user", "assistant")]
    for a, b in zip(convo, convo[1:]):
        if a == b:
            msg = f"row {idx}: consecutive {a!r} messages break user/assistant alternation"
            (warnings if has_tool_msg else errors).append(msg)
            break

    trainable = (not errors) and assistant_targets > 0
    return errors, warnings, trainable


def _validate_tool_calls(tool_calls: Any, idx: int, j: int,
                         errors: list[str], warnings: list[str]) -> None:
    if not isinstance(tool_calls, list) or not tool_calls:
        errors.append(f"row {idx} msg {j}: tool_calls is not a non-empty list")
        return
    for k, raw_tc in enumerate(tool_calls):
        tc = cast("dict[str, Any]", raw_tc) if isinstance(raw_tc, dict) else None
        fn_obj = tc.get("function") if tc is not None else None
        if not isinstance(fn_obj, dict):
            errors.append(f"row {idx} msg {j} tool_call {k}: missing function object")
            continue
        fn = cast("dict[str, Any]", fn_obj)
        name = fn.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"row {idx} msg {j} tool_call {k}: missing function name")
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                json.loads(args)
            except json.JSONDecodeError:
                errors.append(f"row {idx} msg {j} tool_call {k}: arguments are not valid JSON")
        elif not isinstance(args, dict):
            errors.append(f"row {idx} msg {j} tool_call {k}: arguments missing or wrong type")


def validate_dataset(path: str | os.PathLike) -> ValidationResult:
    """Validate a JSONL dataset against every training quality gate."""

    path = Path(path)
    blocking: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        return ValidationResult(
            path=str(path), sha256="", size_bytes=0, num_examples=0,
            detected_format="missing", ok=False,
            blocking_errors=[f"file not found: {path}"])

    size_bytes = path.stat().st_size
    sha256 = _sha256_file(path)

    # UTF-8 validity.
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return ValidationResult(
            path=str(path), sha256=sha256, size_bytes=size_bytes, num_examples=0,
            detected_format="unknown", ok=False,
            blocking_errors=[f"not valid UTF-8: {exc}"])

    rows: list[Any] = []
    for lineno, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            blocking.append(f"line {lineno}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(obj, dict):
            blocking.append(f"line {lineno}: row is not a JSON object")
            continue
        rows.append(obj)

    num_examples = len(rows)
    fmt = _detect_format(rows)

    # Secret scan over the whole file (labels only).
    secret_labels = find_secrets(raw)
    if secret_labels:
        blocking.append("possible secrets detected: " + ", ".join(secret_labels))

    # Size gates.
    if num_examples < MIN_EXAMPLES:
        blocking.append(f"only {num_examples} example(s); need >= {MIN_EXAMPLES}")
    elif num_examples < WARN_EXAMPLES:
        warnings.append(f"only {num_examples} examples; >= {WARN_EXAMPLES} recommended")

    # Duplicate rate.
    signatures = [_row_signature(r) for r in rows]
    unique = len(set(signatures))
    duplicate_rate = (num_examples - unique) / num_examples if num_examples else 0.0
    if duplicate_rate > DUP_WARN_RATE:
        warnings.append(f"high duplicate rate: {duplicate_rate:.0%}")

    trainable = 0
    category_counts: dict[str, int] = {}

    if fmt in ("conversational", "tool_call"):
        for i, row in enumerate(rows):
            errs, warns, ok = _validate_conversation(row, i)
            # Cap noisy per-row errors so the report stays readable.
            for e in errs[:5]:
                blocking.append(e)
            warnings.extend(warns[:3])
            if ok:
                trainable += 1
            category_counts[_category_of(row)] = category_counts.get(_category_of(row), 0) + 1
    elif fmt == "prompt":
        # Prompt-only rows are *generation input*, not SFT targets.
        blocking.append(
            "prompt-only dataset: no assistant targets — this is batch-runner "
            "generation input, not fine-tuning data (run batch_runner.py to "
            "produce trajectories, then convert)")
        for row in rows:
            category_counts[_category_of(row)] = category_counts.get(_category_of(row), 0) + 1
    else:
        blocking.append(f"unrecognized dataset format: {fmt}")

    # Diversity: flag a dataset dominated by a single pattern.
    if category_counts:
        top = max(category_counts.values())
        if num_examples >= MIN_EXAMPLES and top / num_examples > 0.8:
            warnings.append(
                f"low diversity: one pattern is {top/num_examples:.0%} of the dataset")

    ok = not blocking
    return ValidationResult(
        path=str(path), sha256=sha256, size_bytes=size_bytes, num_examples=num_examples,
        detected_format=fmt, ok=ok, blocking_errors=blocking, warnings=warnings,
        duplicate_rate=duplicate_rate, estimated_trainable_examples=trainable,
        category_counts=category_counts)


# --------------------------------------------------------------------------
# Scan / approve / select
# --------------------------------------------------------------------------


def _excluded(path: Path) -> bool:
    return any(part in _SCAN_EXCLUDE for part in path.parts)


def scan(root: str | os.PathLike | None = None) -> dict[str, Any]:
    """Find candidate training JSONL files (incl. gitignored) and write inventory."""

    root_path = Path(root) if root else REPO_ROOT
    found: dict[str, Path] = {}
    for pattern in SCAN_GLOBS:
        for p in root_path.glob(pattern):
            if p.is_file() and not _excluded(p):
                found[str(p.resolve())] = p

    inventory = {
        "scanned_at": _now_iso(),
        "root": str(root_path),
        "globs": list(SCAN_GLOBS),
        "count": len(found),
        "datasets": [],
    }
    for p in sorted(found.values(), key=lambda x: str(x)):
        try:
            rel = str(p.relative_to(root_path))
        except ValueError:
            rel = str(p)
        inventory["datasets"].append({
            "path": rel,
            "abs_path": str(p),
            "size_bytes": p.stat().st_size,
            "sha256": _sha256_file(p),
        })
    _write_json(INVENTORY_PATH, inventory)
    return inventory


def _approval_basis(res: ValidationResult) -> str:
    name = Path(res.path).name.lower()
    bits = []
    if "approved" in name or "owner" in res.path.lower():
        bits.append("owner-approved path")
    if res.detected_format in ("conversational", "tool_call"):
        bits.append(f"validated {res.detected_format} SFT format")
    bits.append(f"{res.estimated_trainable_examples} trainable examples")
    if res.warnings:
        bits.append(f"{len(res.warnings)} non-blocking warning(s)")
    return "; ".join(bits)


def approve(path: str | os.PathLike, only_if_valid: bool = True) -> ValidationResult:
    """Validate a dataset and (if it passes) mark it owner-approved for training."""

    res = validate_dataset(path)
    if res.ok and res.estimated_trainable_examples >= MIN_EXAMPLES:
        res.approved_for_training = True
        res.approval_basis = _approval_basis(res)
    else:
        res.approved_for_training = False
        if not res.ok:
            res.approval_basis = "blocked by quality gates"
        else:
            res.approval_basis = (
                f"insufficient trainable examples "
                f"({res.estimated_trainable_examples} < {MIN_EXAMPLES})")
        if only_if_valid:
            res.approved_for_training = False
    _upsert_quality_report(res)
    return res


def _upsert_quality_report(res: ValidationResult) -> None:
    report = _read_json(QUALITY_REPORT_PATH, {"datasets": []})
    datasets = [d for d in report.get("datasets", []) if d.get("path") != res.path]
    datasets.append(res.to_dict())
    _write_json(QUALITY_REPORT_PATH, {"generated_at": _now_iso(), "datasets": datasets})


def _selection_key(d: dict[str, Any]) -> tuple:
    name = Path(d["path"]).name.lower()
    owner = 1 if ("approved" in name or "owner" in d["path"].lower()) else 0
    fmt_rank = {"tool_call": 2, "conversational": 2, "prompt": 0}.get(
        str(d.get("detected_format")), 1)
    diversity = len(d.get("category_counts") or {})
    return (owner, fmt_rank, diversity, d.get("estimated_trainable_examples", 0))


def select_best_dataset() -> Optional[dict[str, Any]]:
    """Pick the best owner-approved dataset and write training_selected_dataset.json."""

    report = _read_json(QUALITY_REPORT_PATH, {"datasets": []})
    approved = [d for d in report.get("datasets", []) if d.get("approved_for_training")]
    if not approved:
        return None
    best = max(approved, key=_selection_key)
    selected = {"selected_at": _now_iso(), "dataset": best}
    _write_json(SELECTED_PATH, selected)
    return best


# --------------------------------------------------------------------------
# Conversion: Hermes / ShareGPT trajectories -> Together conversational JSONL
# --------------------------------------------------------------------------

_ROLE_MAP = {
    "human": "user",
    "user": "user",
    "gpt": "assistant",
    "assistant": "assistant",
    "system": "system",
    "tool": "tool",
    "function": "tool",
    "observation": "tool",
}


def _normalize_turns(row: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    """Coerce a trajectory row into OpenAI/Together role/content messages."""

    turns = row.get("messages") or row.get("conversations") or row.get("conversation")
    if not isinstance(turns, list) or not turns:
        return None
    out: list[dict[str, Any]] = []
    for raw_t in turns:
        if not isinstance(raw_t, dict):
            return None
        t = cast("dict[str, Any]", raw_t)
        role = t.get("role") or _ROLE_MAP.get(str(t.get("from", "")).lower())
        role = _ROLE_MAP.get(str(role).lower(), role)
        content = t.get("content")
        if content is None:
            content = t.get("value")
        if role not in _ALLOWED_ROLES:
            return None
        msg: dict[str, Any] = {"role": role}
        if content is not None:
            msg["content"] = content
        if t.get("tool_calls"):
            msg["tool_calls"] = t["tool_calls"]
        out.append(msg)
    return out


def _trajectory_is_failed(row: dict[str, Any]) -> bool:
    if row.get("success") is False:
        return True
    if row.get("error"):
        return True
    status = str(row.get("status", "")).lower()
    return status in {"failed", "error", "partial", "incomplete", "corrupted"}


def convert_trajectories(
    path: str | os.PathLike,
    *,
    allow_partial: bool = False,
    val_split_min: int = 50,
    val_fraction: float = 0.1,
) -> dict[str, Any]:
    """Convert a trajectories JSONL into Together conversational train/valid sets."""

    path = Path(path)
    if not path.is_file():
        raise TrainingError(f"trajectory file not found: {path}")

    converted: list[dict[str, Any]] = []
    skipped = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(row, dict):
            skipped += 1
            continue
        if _trajectory_is_failed(row) and not allow_partial:
            skipped += 1
            continue
        msgs = _normalize_turns(row)
        if not msgs:
            skipped += 1
            continue
        # Reject rows with no usable assistant target.
        if not any(
            m.get("role") == "assistant"
            and (isinstance(m.get("content"), str) and m["content"].strip() or m.get("tool_calls"))
            for m in msgs
        ):
            skipped += 1
            continue
        converted.append({"messages": msgs})

    if not converted:
        raise TrainingError(
            f"no convertible rows in {path} (skipped {skipped}); "
            "source has no high-quality assistant targets")

    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    train_path = APPROVED_DIR / "together_train.jsonl"
    valid_path = APPROVED_DIR / "together_valid.jsonl"

    n_val = int(len(converted) * val_fraction) if len(converted) >= val_split_min else 0
    train_rows = converted[n_val:]
    val_rows = converted[:n_val]

    with open(train_path, "w", encoding="utf-8") as fh:
        for r in train_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if val_rows:
        with open(valid_path, "w", encoding="utf-8") as fh:
            for r in val_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {
        "source": str(path),
        "train_path": str(train_path),
        "valid_path": str(valid_path) if val_rows else None,
        "converted": len(converted),
        "train": len(train_rows),
        "valid": len(val_rows),
        "skipped": skipped,
        "allow_partial": allow_partial,
    }


# --------------------------------------------------------------------------
# Together AI dispatch (owner-gated, cost-guarded)
# --------------------------------------------------------------------------


def _load_env() -> None:
    """Load ~/.hermes/.env (+ project .env fallback) using the Hermes loader."""

    try:
        from hermes_cli.env_loader import load_hermes_dotenv
        from hermes_constants import get_hermes_home

        load_hermes_dotenv(hermes_home=get_hermes_home(), project_env=REPO_ROOT / ".env")
    except Exception:  # pragma: no cover - never fatal; env may already be set
        pass


def _require_api_key() -> str:
    _load_env()
    key = os.environ.get("TOGETHER_API_KEY", "").strip()
    if not key:
        raise TrainingError(
            "TOGETHER_API_KEY not set. Add it to ~/.hermes/.env "
            "(TOGETHER_API_KEY=...) — never hardcode it.")
    return key


def _together_client():
    key = _require_api_key()
    try:
        from together import Together  # noqa: PLC0415  # ty: ignore[unresolved-import]
    except ImportError as exc:
        raise TrainingError(
            "the 'together' package is not installed. Run: pip install together") from exc
    return Together(api_key=key)


def together_check_file(path: str | os.PathLike) -> dict[str, Any]:
    """Run Together's client-side ``check_file`` validator (after local gates)."""

    res = validate_dataset(path)
    if not res.ok:
        raise TrainingError(
            "local quality gates failed; not running Together check_file:\n  - "
            + "\n  - ".join(res.blocking_errors))
    try:
        from together.utils import check_file  # noqa: PLC0415  # ty: ignore[unresolved-import]
    except ImportError as exc:
        raise TrainingError("the 'together' package is not installed.") from exc
    report = check_file(str(path))
    return dict(report)


def _jobs_state() -> dict[str, Any]:
    return _read_json(JOBS_PATH, {"uploads": [], "jobs": []})


def _save_jobs_state(state: dict[str, Any]) -> None:
    _write_json(JOBS_PATH, state)


def _hyperparams_key(model: str, hyperparams: dict[str, Any]) -> str:
    return json.dumps({"model": model, "hp": hyperparams}, sort_keys=True)


def together_upload(path: str | os.PathLike) -> dict[str, Any]:
    """Validate, run Together check_file, then upload with ``purpose='fine-tune'``."""

    path = Path(path)
    res = validate_dataset(path)
    if not res.ok:
        raise TrainingError(
            "dataset failed local quality gates; refusing to upload:\n  - "
            + "\n  - ".join(res.blocking_errors))
    check = together_check_file(path)
    if check.get("is_check_passed") is False:
        raise TrainingError(f"Together check_file failed: {check}")

    client = _together_client()
    uploaded = client.files.upload(file=str(path), purpose="fine-tune", check=True)
    file_id = getattr(uploaded, "id", None) or (uploaded.get("id") if isinstance(uploaded, dict) else None)

    state = _jobs_state()
    record = {
        "file_id": file_id,
        "path": str(path),
        "sha256": res.sha256,
        "size_bytes": res.size_bytes,
        "num_examples": res.num_examples,
        "uploaded_at": _now_iso(),
    }
    state["uploads"].append(record)
    _save_jobs_state(state)
    return record


def _existing_job_for(sha256: str, hp_key: str, client=None) -> Optional[str]:
    for job in _jobs_state().get("jobs", []):
        if job.get("dataset_sha256") == sha256 and job.get("hyperparams_key") == hp_key:
            return job.get("job_id")
    if client is not None:
        try:
            for remote in client.fine_tuning.list():
                jid = getattr(remote, "id", None)
                tf = getattr(remote, "training_file", None)
                if jid and tf and tf in {u.get("file_id") for u in _jobs_state().get("uploads", [])}:
                    return jid
        except Exception:  # pragma: no cover - remote list is best-effort
            pass
    return None


def together_create_job(
    path_or_file_id: str,
    *,
    base_model: str = DEFAULT_BASE_MODEL,
    hyperparams: Optional[dict[str, Any]] = None,
    yes_start_paid_training: bool = False,
    suffix: Optional[str] = None,
) -> dict[str, Any]:
    """Create a Together LoRA SFT job — owner-gated, duplicate/cost-guarded."""

    hyperparams = {**DEFAULT_HYPERPARAMS, **(hyperparams or {})}

    # Resolve the dataset identity WITHOUT any network call yet.
    candidate = Path(path_or_file_id)
    is_path = candidate.is_file()
    if is_path:
        res = validate_dataset(candidate)
        if not res.ok:
            raise TrainingError(
                "dataset failed local quality gates; refusing to create a paid job:\n  - "
                + "\n  - ".join(res.blocking_errors))
        sha256 = res.sha256
    else:
        sha256 = next(
            (u["sha256"] for u in _jobs_state().get("uploads", []) if u.get("file_id") == path_or_file_id),
            "")

    hp_key = _hyperparams_key(base_model, hyperparams)

    # Local duplicate/cost guard (no network).
    local_dup = _existing_job_for(sha256, hp_key, client=None)
    if local_dup:
        raise TrainingError(
            f"a job already exists for this dataset+model+hyperparams: {local_dup}. "
            "Refusing to create a duplicate paid job.")

    # Owner/cost gate — enforced BEFORE any upload or job creation.
    if not yes_start_paid_training:
        raise TrainingError(
            "refusing to start a PAID training job without --yes-start-paid-training. "
            "Re-run with that flag to proceed (owner-authorized).")

    # --- paid path: now talk to Together ---
    client = _together_client()
    if is_path:
        file_id = together_upload(candidate)["file_id"]
    else:
        file_id = path_or_file_id

    remote_dup = _existing_job_for(sha256, hp_key, client=client)
    if remote_dup:
        raise TrainingError(
            f"a remote job already exists for this dataset+config: {remote_dup}. "
            "Refusing to create a duplicate paid job.")

    created = client.fine_tuning.create(
        training_file=file_id,
        model=base_model,
        n_epochs=hyperparams["n_epochs"],
        n_checkpoints=hyperparams["n_checkpoints"],
        learning_rate=hyperparams["learning_rate"],
        lora=hyperparams["lora"],
        batch_size=hyperparams["batch_size"],
        warmup_ratio=hyperparams["warmup_ratio"],
        weight_decay=hyperparams["weight_decay"],
        max_grad_norm=hyperparams["max_grad_norm"],
        train_on_inputs=hyperparams["train_on_inputs"],
        **({"suffix": suffix} if suffix else {}),
    )
    job_id = getattr(created, "id", None) or (created.get("id") if isinstance(created, dict) else None)

    state = _jobs_state()
    job_record = {
        "job_id": job_id,
        "training_file": file_id,
        "model": base_model,
        "hyperparams": hyperparams,
        "hyperparams_key": hp_key,
        "dataset_sha256": sha256,
        "created_at": _now_iso(),
        "status": getattr(created, "status", None),
    }
    state["jobs"].append(job_record)
    _save_jobs_state(state)
    return job_record


def _job_call(method: str, job_id: str, **kwargs):
    client = _together_client()
    api = client.fine_tuning
    fn = getattr(api, method, None)
    if fn is None:  # pragma: no cover - SDK surface differences
        raise TrainingError(f"Together SDK has no fine_tuning.{method}")
    return fn(job_id, **kwargs)


def together_status(job_id: str):
    return _job_call("retrieve", job_id)


def together_events(job_id: str):
    return _job_call("list_events", job_id)


def together_metrics(job_id: str):
    # Metrics are exposed via the job object / events depending on SDK version.
    return _job_call("retrieve", job_id)


def together_cancel(job_id: str):
    return _job_call("cancel", job_id)


def together_download(job_id: str, out_dir: str | os.PathLike = "data/models"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = _together_client()
    return client.fine_tuning.download(job_id, output=str(out))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hermes_cli.nlp_training",
        description="Validate training datasets and dispatch Together AI fine-tune jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="Find candidate training JSONL (incl. gitignored)")

    p_val = sub.add_parser("validate", help="Validate a dataset against quality gates")
    p_val.add_argument("path")

    p_app = sub.add_parser("approve", help="Approve a dataset for training if it passes")
    p_app.add_argument("path")
    p_app.add_argument("--only-if-valid", action="store_true", default=True,
                       help="(default) only approve when all gates pass")

    sub.add_parser("select", help="Select the best owner-approved dataset")

    p_conv = sub.add_parser("convert", help="Convert trajectories -> Together JSONL")
    p_conv.add_argument("path")
    p_conv.add_argument("--allow-partial", action="store_true", default=False)

    p_up = sub.add_parser("together-upload", help="Validate + upload a dataset to Together")
    p_up.add_argument("path")

    p_job = sub.add_parser("together-create-job", help="Create a Together LoRA SFT job")
    p_job.add_argument("path_or_file_id")
    p_job.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    p_job.add_argument("--suffix", default=None)
    p_job.add_argument("--yes-start-paid-training", action="store_true", default=False,
                       help="REQUIRED to actually create a paid job")

    for name, helptext in (
        ("together-status", "Retrieve a job's status"),
        ("together-events", "List a job's events"),
        ("together-metrics", "Show a job's metrics"),
        ("together-cancel", "Cancel a job"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("job_id")

    p_dl = sub.add_parser("together-download", help="Download a finished model")
    p_dl.add_argument("job_id")
    p_dl.add_argument("--out", default="data/models")

    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            inv = scan()
            print(f"found {inv['count']} dataset(s); inventory -> {INVENTORY_PATH}")
            _print(inv)
            return 0
        if args.command == "validate":
            res = validate_dataset(args.path)
            _print(res.to_dict())
            return 0 if res.ok else 1
        if args.command == "approve":
            res = approve(args.path, only_if_valid=True)
            _print(res.to_dict())
            print(f"approved_for_training: {res.approved_for_training}")
            return 0 if res.approved_for_training else 1
        if args.command == "select":
            best = select_best_dataset()
            if not best:
                print("no owner-approved dataset available; nothing selected")
                return 1
            print(f"selected -> {SELECTED_PATH}")
            _print(best)
            return 0
        if args.command == "convert":
            out = convert_trajectories(args.path, allow_partial=args.allow_partial)
            _print(out)
            return 0
        if args.command == "together-upload":
            _print(together_upload(args.path))
            return 0
        if args.command == "together-create-job":
            rec = together_create_job(
                args.path_or_file_id, base_model=args.base_model, suffix=args.suffix,
                yes_start_paid_training=args.yes_start_paid_training)
            print(f"created job {rec.get('job_id')}")
            _print(rec)
            return 0
        if args.command == "together-status":
            _print(together_status(args.job_id))
            return 0
        if args.command == "together-events":
            _print(together_events(args.job_id))
            return 0
        if args.command == "together-metrics":
            _print(together_metrics(args.job_id))
            return 0
        if args.command == "together-cancel":
            _print(together_cancel(args.job_id))
            return 0
        if args.command == "together-download":
            _print(together_download(args.job_id, out_dir=args.out))
            return 0
    except TrainingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


__all__ = [
    "ValidationResult",
    "validate_dataset",
    "find_secrets",
    "scan",
    "approve",
    "select_best_dataset",
    "convert_trajectories",
    "together_check_file",
    "together_upload",
    "together_create_job",
    "together_status",
    "together_events",
    "together_metrics",
    "together_cancel",
    "together_download",
    "TrainingError",
    "DEFAULT_BASE_MODEL",
    "DEFAULT_HYPERPARAMS",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())

