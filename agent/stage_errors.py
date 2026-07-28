"""Structured error handling for pipeline stages.

Wraps stage execution in a consistent error boundary that captures context,
logs structured errors, and produces machine-readable failure reports.
"""
from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Error severity levels for pipeline failures."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class StageError:
    """Structured error from a pipeline stage failure."""
    stage: str
    message: str
    severity: Severity = Severity.ERROR
    exception_type: str = ""
    exception_message: str = ""
    traceback: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": self.message,
            "severity": self.severity.value,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "traceback": self.traceback,
            "context": self.context,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"StageError(stage={self.stage!r}, severity={self.severity.value}, message={self.message!r})"


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    stage: str
    success: bool
    duration_s: float = 0.0
    artifacts: list[str] = field(default_factory=list)
    error: StageError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        d = {
            "stage": self.stage,
            "success": self.success,
            "duration_s": round(self.duration_s, 3),
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }
        if self.error:
            d["error"] = self.error.to_dict()
        return d


def stage_handler(
    stage_name: str,
    *,
    reraise: bool = True,
    default: T | None = None,
    log_level: int = logging.ERROR,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that wraps a pipeline stage with structured error handling.

    Captures exceptions, logs them with full context, and optionally
    re-raises or returns a default value.

    Args:
        stage_name: Human-readable name for the stage.
        reraise: If True, re-raise the exception after logging.
        default: Value to return if reraise is False and an exception occurs.
        log_level: Logging level for captured errors.

    Example::

        @stage_handler("asset_generation", reraise=False, default=[])
        def generate_assets(manifest):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - t0
                logger.debug(
                    "Stage '%s' completed successfully in %.1fs",
                    stage_name, duration,
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - t0
                error = StageError(
                    stage=stage_name,
                    message=f"Stage '{stage_name}' failed after {duration:.1f}s",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    traceback=traceback.format_exc(),
                )
                logger.log(
                    log_level,
                    "Stage '%s' failed: %s: %s",
                    stage_name, type(e).__name__, e,
                    exc_info=True,
                )
                if reraise:
                    raise
                return default  # type: ignore[return-value]

        return wrapper

    return decorator


def collect_stage_errors(results: list[StageResult]) -> list[StageError]:
    """Extract all errors from a list of stage results."""
    return [r.error for r in results if r.error is not None]


def summarize_stages(results: list[StageResult]) -> dict[str, Any]:
    """Generate a summary report from stage results.

    Useful for checkpoint files and CI annotations.
    """
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed
    total_duration = sum(r.duration_s for r in results)
    return {
        "total_stages": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{passed / total * 100:.1f}%" if total else "N/A",
        "total_duration_s": round(total_duration, 2),
        "stages": [r.to_dict() for r in results],
        "errors": [e.to_dict() for e in collect_stage_errors(results)],
    }
