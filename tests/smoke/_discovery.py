"""Module discovery and import-failure classification for the smoke layer.

Why this exists
---------------
``hermes_cli`` (~620 modules), ``gateway`` (~120), ``agent`` (~254) and
``tools`` (~160) are the four largest packages in the repository and were
recorded with **zero** test files.  Nobody can write meaningful unit tests
for ~460k lines in one pass.  What *is* achievable, and what would have
caught the class of breakage this repository has actually suffered (a bad
merge leaving a dangling import), is a layer that asserts the cheap
structural invariants:

* every module in those packages imports cleanly,
* every registered CLI command resolves and renders its ``--help``,
* every gateway platform adapter and HTTP route registers without error,
* every declared console-script entry point resolves to a callable.

Everything here is **discovered from disk at collection time**, never from a
hand-maintained list, so the suite grows with the repository automatically.

Discovery rules
---------------
``vendor/`` directories are excluded: ``pyproject.toml``'s ``[tool.ty.src]``
already declares them "vendored byte-identical upstream payloads ... data,
not first-party code", and they carry their own ``VENDOR.md`` do-not-edit
rule.  Directories named ``tests`` are excluded because pytest collects
those modules itself; importing them a second time under a dotted name
would double-register them.

Classification
--------------
Not every import failure is a defect, and the difference matters:

* ``import fcntl`` on Windows is a platform fact, not a bug -> SKIP.
* a missing optional third-party SDK is a deployment choice -> SKIP.
* a ``ModuleNotFoundError`` naming a **first-party** top-level package is a
  dangling import -> FAIL.  This is the merge-damage detector and it must
  never be downgraded to a skip.
* anything else (``KeyError`` at module scope, ``AttributeError``,
  ``SyntaxError``, ...) -> FAIL.

The first-party set is computed from the repository root, so a package
added tomorrow is protected the same day.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The four packages §5.2 records with 0 test files.  Extend this list rather
# than the tests: everything downstream is derived from it.
ZERO_TEST_PACKAGES: tuple[str, ...] = ("hermes_cli", "gateway", "agent", "tools")

# Floor per package.  A discovery bug that silently returned 3 modules would
# otherwise make this whole layer vacuously green.  These are deliberately
# well below the real counts observed on 2026-08-17 (1,155 modules across the
# four packages) so ordinary deletions do not trip them, but a collapse does.
MIN_DISCOVERED: dict[str, int] = {
    "hermes_cli": 400,
    "gateway": 90,
    "agent": 180,
    "tools": 110,
}

_PRUNED_DIR_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        # See module docstring: declared vendored payloads, excluded by the
        # repository's own tooling config.
        "vendor",
        # pytest collects these itself.
        "tests",
    }
)

# Stdlib modules that only exist on POSIX.  Importing one on Windows is a
# platform fact and is skipped with that reason, never failed.
_POSIX_ONLY_STDLIB = frozenset(
    {
        "fcntl",
        "termios",
        "tty",
        "pty",
        "grp",
        "pwd",
        "posix",
        "resource",
        "syslog",
        "spwd",
        "crypt",
        "nis",
        "readline",
    }
)

# ... and the mirror image, for when this suite runs on Linux/macOS.
_WINDOWS_ONLY_STDLIB = frozenset({"winreg", "msvcrt", "winsound", "_winapi"})

# Substrings that mark a failure as hardware/driver related rather than a
# code defect.  Matched case-insensitively against the exception text.
_HARDWARE_MARKERS = (
    "cuda",
    "cudnn",
    "nvml",
    "no gpu",
    "gpu is not available",
    "libcublas",
    "directml",
    "rocm",
)

# Substrings that mark a failure as a missing credential.  A module that
# refuses to import without an API key is a deployment fact here.
_CREDENTIAL_MARKERS = (
    "api_key",
    "api key",
    "access_token",
    "access key",
    "credential",
    "secret_key",
    "not authenticated",
    "no token",
)


@dataclass(frozen=True)
class ImportVerdict:
    """Outcome of classifying an import failure."""

    action: str  # "fail" or "skip"
    reason: str


@lru_cache(maxsize=1)
def first_party_top_level() -> frozenset[str]:
    """Top-level importable names that live in this repository.

    Computed from disk so it never goes stale.  A ``ModuleNotFoundError``
    whose root package is in this set is a dangling first-party import — the
    exact failure mode a bad merge produces — and is always a hard failure.
    """
    names: set[str] = set()
    for entry in REPO_ROOT.iterdir():
        if entry.name in _PRUNED_DIR_NAMES or entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "__init__.py").is_file():
            if entry.name.isidentifier():
                names.add(entry.name)
        elif entry.is_file() and entry.suffix == ".py":
            if entry.stem.isidentifier():
                names.add(entry.stem)
    return frozenset(names)


def discover_modules(package: str) -> list[str]:
    """Return every importable dotted module name under *package*.

    Walks the filesystem; no import is performed here.  Directories in
    :data:`_PRUNED_DIR_NAMES` and any path segment that is not a valid Python
    identifier are excluded, because such a path has no dotted name at all.
    """
    base = REPO_ROOT / package
    if not base.is_dir():
        return []
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in _PRUNED_DIR_NAMES)
        parts = Path(dirpath).resolve().relative_to(REPO_ROOT).parts
        if any(not part.isidentifier() for part in parts):
            continue
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            stem = filename[:-3]
            if stem == "__init__":
                found.add(".".join(parts))
            elif stem.isidentifier():
                found.add(".".join((*parts, stem)))
    return sorted(found)


@lru_cache(maxsize=1)
def all_discovered_modules() -> tuple[str, ...]:
    """Every module across every package in :data:`ZERO_TEST_PACKAGES`."""
    modules: list[str] = []
    for package in ZERO_TEST_PACKAGES:
        modules.extend(discover_modules(package))
    return tuple(modules)


def _missing_root(exc: BaseException) -> str | None:
    name = getattr(exc, "name", None)
    if isinstance(name, str) and name:
        return name.split(".")[0]
    return None


def classify_import_failure(module_name: str, exc: BaseException) -> ImportVerdict:
    """Decide whether *exc* from importing *module_name* is a defect.

    Returns an :class:`ImportVerdict` whose ``action`` is ``"fail"`` or
    ``"skip"``.  The reason string is always specific enough to act on — a
    skip that does not say what is missing is indistinguishable from a bug
    swept under the rug.
    """
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()

    if isinstance(exc, ModuleNotFoundError):
        root = _missing_root(exc)
        if root:
            if root in first_party_top_level():
                return ImportVerdict(
                    "fail",
                    f"{module_name} imports first-party module {exc.name!r}, "
                    f"which does not exist. Dangling first-party import "
                    f"(root package {root!r} is in this repository).",
                )
            if os.name == "nt" and root in _POSIX_ONLY_STDLIB:
                return ImportVerdict(
                    "skip",
                    f"requires POSIX-only stdlib module {root!r}; "
                    f"this platform is {sys.platform}",
                )
            if os.name != "nt" and root in _WINDOWS_ONLY_STDLIB:
                return ImportVerdict(
                    "skip",
                    f"requires Windows-only stdlib module {root!r}; "
                    f"this platform is {sys.platform}",
                )
            return ImportVerdict(
                "skip",
                f"optional third-party dependency {root!r} is not installed "
                f"in this environment",
            )

    if any(marker in lowered for marker in _HARDWARE_MARKERS):
        return ImportVerdict("skip", f"requires GPU/accelerator hardware: {text}")

    if any(marker in lowered for marker in _CREDENTIAL_MARKERS):
        return ImportVerdict("skip", f"requires a credential at import time: {text}")

    return ImportVerdict(
        "fail",
        f"{module_name} failed to import: {text}",
    )
