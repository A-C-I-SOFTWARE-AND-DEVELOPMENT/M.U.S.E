"""The production build excludes ``recovered-agent-sources/`` — and keeps it.

Work Packet §4.2, §11 ("Exclude the broken delegate prototype from the
production build").

Two obligations hold **at the same time**, and this module exists because it is
easy to satisfy one by breaking the other:

1. **Exclude.** ``recovered-agent-sources/`` must not reach any production build
   artifact. It is the byte-preserved archival snapshot of the 2026-07-12
   device-consolidation recovery — historical evidence, not live code.
2. **Retain.** The tree must stay on disk. It contains the archive's only
   whole-tree compile failure::

       recovered-agent-sources/device-consolidation-2026-07-12/
         working-tree-overlays/broken-delegate-prototype/tools/delegate_tool.py
       line 970 -> IndentationError: expected an indented block after
                   'elif' statement on line 968

   Being broken is precisely what the path name declares. That file is the
   audit's evidence, so **deleting it or "repairing" it is not the fix**;
   excluding it from the build is.

If ``test_the_broken_delegate_prototype_is_still_broken_on_purpose`` fails, do
not silence it. Someone has edited archival evidence, and the right response is
to restore the byte-preserved file, not to update this expectation.

The declared exclusion lives in ``[tool.muse.production-build]`` in
``pyproject.toml``; ``MANIFEST.in``, ``[tool.setuptools.packages.find]``,
``[tool.ruff]`` and ``[tool.ty.src]`` mirror it. This module checks the mirrors
agree, that setuptools really does drop the tree, that the production file set
compiles with zero syntax failures, and that the evidence survives.
"""

from __future__ import annotations

import os
import tomllib
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
MANIFEST_IN = REPO_ROOT / "MANIFEST.in"

#: The archival tree. Excluded from the build, retained on disk.
ARCHIVE_DIR = "recovered-agent-sources"

#: The one file §4.2 names. Relative POSIX path, as written in pyproject.toml.
BROKEN_PROTOTYPE = (
    "recovered-agent-sources/device-consolidation-2026-07-12/"
    "working-tree-overlays/broken-delegate-prototype/tools/delegate_tool.py"
)

#: The exact recorded failure. CPython reports the line the block should have
#: started on (970), naming the ``elif`` it belongs to (968).
BROKEN_PROTOTYPE_ERROR_LINE = 970

#: Directories that are tool output, dependency payloads or virtualenvs. These
#: are *not* part of the packet's exclusion policy — they are simply not source
#: code, and no build ever ships them. Kept separate from the declared
#: production-build exclusions on purpose.
NON_SOURCE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".ty_cache",
        "node_modules",
        "site-packages",
        "dist",
        "build",
        ".gradle",
        ".eggs",
        ".idea",
    }
)

#: Sanity floor for the production scan. The point is that
#: ``test_production_python_file_set_has_zero_syntax_failures`` cannot pass by
#: scanning nothing. The working tree held 5,267 files when this was written;
#: 3,000 leaves room for the tree to shrink without turning the test vacuous.
MIN_EXPECTED_PRODUCTION_FILES = 3000


def _load_pyproject() -> dict:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _production_build_table() -> dict:
    cfg = _load_pyproject()
    try:
        return cfg["tool"]["muse"]["production-build"]
    except KeyError:  # pragma: no cover - the assertion below is the message
        pytest.fail(
            "pyproject.toml has no [tool.muse.production-build] table. That "
            "table is the single source of truth for what the production "
            "build excludes (Work Packet §4.2, §11); every other exclusion "
            "in the file mirrors it."
        )


def _iter_python_files(root: Path, *, skip_dirs: frozenset[str]) -> list[Path]:
    """Every ``*.py`` under *root*, skipping *skip_dirs* by directory name."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in place so os.walk never descends into the skipped trees, and
        # never into a virtualenv (identified by its pyvenv.cfg marker rather
        # than by guessing at its directory name).
        dirnames[:] = [
            d
            for d in dirnames
            if d not in skip_dirs
            and not d.endswith(".egg-info")
            and not (Path(dirpath) / d / "pyvenv.cfg").is_file()
        ]
        for filename in filenames:
            if filename.endswith(".py"):
                found.append(Path(dirpath) / filename)
    return found


def _syntax_failures(paths: list[Path]) -> list[tuple[str, str, int | None, str]]:
    """Compile each path; return ``(relpath, error type, line, message)``."""
    failures: list[tuple[str, str, int | None, str]] = []
    # Compiling thousands of files re-emits every SyntaxWarning in the tree
    # (invalid escape sequences and the like). Those are real, but they are not
    # what this gate measures, and echoing them on every run buries the one
    # signal that matters. Only a hard compile failure counts here.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        for path in paths:
            source = path.read_bytes()
            try:
                # Compile the raw bytes so PEP 263 coding declarations and BOMs
                # are honoured exactly as the interpreter would honour them.
                compile(source, str(path), "exec", dont_inherit=True)
            except SyntaxError as exc:
                failures.append(
                    (
                        path.relative_to(REPO_ROOT).as_posix(),
                        type(exc).__name__,
                        exc.lineno,
                        exc.msg,
                    )
                )
            except ValueError as exc:
                # e.g. source containing a null byte — still a "this file will
                # not load" failure, still disqualifying for a production build.
                failures.append(
                    (
                        path.relative_to(REPO_ROOT).as_posix(),
                        "ValueError",
                        None,
                        str(exc),
                    )
                )
    return failures


# --------------------------------------------------------------------------
# 1. The exclusion is declared, once, in a machine-readable place.
# --------------------------------------------------------------------------


def test_pyproject_declares_the_production_build_exclusion() -> None:
    table = _production_build_table()

    assert ARCHIVE_DIR in table["exclude"], (
        f"{ARCHIVE_DIR!r} must be listed in "
        "[tool.muse.production-build].exclude — it is the archival snapshot, "
        "not live code (Work Packet §4.2)."
    )
    assert BROKEN_PROTOTYPE in table["retained-evidence"], (
        "The broken delegate prototype must be named in "
        "[tool.muse.production-build].retained-evidence so that a future "
        "reader knows the file is kept deliberately (Work Packet §11)."
    )


def test_declared_exclusions_are_repo_relative_directories_that_exist() -> None:
    """An exclusion pointing at nothing silently protects nothing."""
    for entry in _production_build_table()["exclude"]:
        target = REPO_ROOT / entry
        assert target.is_dir(), (
            f"[tool.muse.production-build].exclude names {entry!r}, which is "
            "not a directory in this repository. Either the tree was deleted "
            "(it must be retained — Work Packet §11) or the entry is stale."
        )


# --------------------------------------------------------------------------
# 2. Every packaging mirror agrees with the declaration.
# --------------------------------------------------------------------------


def test_manifest_in_prunes_every_declared_exclusion() -> None:
    assert MANIFEST_IN.is_file(), (
        "MANIFEST.in is missing. It is what keeps the archival tree out of a "
        "source distribution."
    )
    directives = {
        line.strip()
        for line in MANIFEST_IN.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for entry in _production_build_table()["exclude"]:
        assert f"prune {entry}" in directives, (
            f"MANIFEST.in must contain 'prune {entry}' to mirror "
            "[tool.muse.production-build].exclude."
        )


def test_manifest_in_actually_drops_the_broken_prototype_from_an_sdist() -> None:
    """Run MANIFEST.in through setuptools' own template processor.

    This is behaviour, not text: the same ``FileList`` the sdist command uses
    is seeded with two real repository paths and told to process every
    directive in MANIFEST.in. The archived file must be gone afterwards and a
    genuine production file must survive.
    """
    from setuptools._distutils.filelist import FileList

    kept = os.path.join("hermes_cli", "__init__.py")
    pruned = os.path.join(*BROKEN_PROTOTYPE.split("/"))

    file_list = FileList()
    file_list.files = [kept, pruned]
    for line in MANIFEST_IN.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            file_list.process_template_line(stripped)

    assert pruned not in file_list.files, (
        "MANIFEST.in did not prune the broken delegate prototype; it would "
        "ship in an sdist."
    )
    assert kept in file_list.files, (
        "MANIFEST.in pruned a production file. The exclusion is too broad."
    )


def test_setuptools_package_discovery_drops_the_archive() -> None:
    """setuptools must not discover a single package inside the archive.

    Three discoveries run, because the first assertion alone would be vacuous:

    * ``configured`` — the real include/exclude from pyproject.toml.
    * ``control`` — a permissive include with **no** exclude, proving the
      finder does reach into the archive and would happily package it.
    * ``guarded`` — the same permissive include **with** the configured
      exclude, proving the exclude is what removes it.
    """
    from setuptools import find_namespace_packages

    cfg = _load_pyproject()
    find_cfg = cfg["tool"]["setuptools"]["packages"]["find"]
    include = list(find_cfg.get("include", ["*"]))
    exclude = list(find_cfg.get("exclude", []))

    assert exclude, (
        "[tool.setuptools.packages.find] declares no exclude. The include "
        "allowlist keeps the archive out only as a side effect; one added "
        "'*' entry would undo that silently."
    )

    def _archived(names: list[str]) -> list[str]:
        return [n for n in names if n == ARCHIVE_DIR or n.startswith(ARCHIVE_DIR + ".")]

    configured = find_namespace_packages(
        where=str(REPO_ROOT), include=include, exclude=exclude
    )
    assert _archived(configured) == [], (
        "The configured package discovery found packages inside "
        f"{ARCHIVE_DIR}/: {_archived(configured)[:5]}"
    )

    control = find_namespace_packages(
        where=str(REPO_ROOT), include=[f"{ARCHIVE_DIR}*"], exclude=[]
    )
    assert control, (
        "Control discovery found nothing inside the archive, so the check "
        "above proves nothing. Has the tree been deleted? It must be "
        "retained (Work Packet §11)."
    )

    guarded = find_namespace_packages(
        where=str(REPO_ROOT), include=[f"{ARCHIVE_DIR}*"], exclude=exclude
    )
    assert guarded == [], (
        "The configured exclude did not suppress the archive; discovery still "
        f"yields {guarded[:5]}"
    )


def test_lint_and_typecheck_mirror_the_declared_exclusions() -> None:
    """ruff and ty must skip what the build skips.

    A tool that parses the archive reports the deliberate IndentationError as
    a defect on every run, and a permanently-red tool is a tool nobody reads.
    """
    cfg = _load_pyproject()
    ruff_exclude = cfg["tool"]["ruff"]["extend-exclude"]
    ty_exclude = cfg["tool"]["ty"]["src"]["exclude"]

    for entry in _production_build_table()["exclude"]:
        assert entry in ruff_exclude, f"[tool.ruff].extend-exclude is missing {entry!r}"
        assert entry in ty_exclude, f"[tool.ty.src].exclude is missing {entry!r}"


# --------------------------------------------------------------------------
# 3. The production file set compiles. Zero syntax failures (§4.2 acceptance).
# --------------------------------------------------------------------------


def test_production_python_file_set_has_zero_syntax_failures() -> None:
    """Compile every production Python file. Acceptance is zero failures.

    This is Work Packet §4.2's acceptance criterion run as a test rather than
    as a one-off script: the production file set is the working tree minus the
    declared ``[tool.muse.production-build]`` exclusions and minus tool output.
    """
    skip_dirs = NON_SOURCE_DIRS | set(_production_build_table()["exclude"])
    paths = _iter_python_files(REPO_ROOT, skip_dirs=frozenset(skip_dirs))

    assert len(paths) >= MIN_EXPECTED_PRODUCTION_FILES, (
        f"Only {len(paths)} Python files were scanned, below the "
        f"{MIN_EXPECTED_PRODUCTION_FILES} sanity floor. A pass on a nearly "
        "empty file set is not evidence of anything."
    )

    failures = _syntax_failures(paths)
    assert failures == [], (
        f"{len(failures)} production file(s) failed to compile:\n"
        + "\n".join(f"  {p}:{line} {kind}: {msg}" for p, kind, line, msg in failures)
    )


def test_the_exclusion_is_load_bearing_for_the_compile_check() -> None:
    """Scanning the archive reproduces exactly one failure: the prototype.

    Without this, the clean result above could be read as "the exclusion is
    unnecessary". It is necessary — and this pins the fact that the archive
    contributes one and only one failure, so a *second* broken archived file
    appearing later is a change worth noticing rather than a silent addition
    to an ignored pile.
    """
    archive_root = REPO_ROOT / ARCHIVE_DIR
    paths = _iter_python_files(archive_root, skip_dirs=NON_SOURCE_DIRS)
    assert paths, f"{ARCHIVE_DIR}/ holds no Python files — has it been deleted?"

    failures = _syntax_failures(paths)
    failing_paths = [p for p, _kind, _line, _msg in failures]

    assert failing_paths == [BROKEN_PROTOTYPE], (
        "The archive's compile failures changed. Expected exactly the one "
        f"documented in Work Packet §4.2, got: {failing_paths}"
    )


# --------------------------------------------------------------------------
# 4. The evidence is retained. Do not "fix" these by deleting the file.
# --------------------------------------------------------------------------


def test_the_excluded_broken_prototype_is_still_present_on_disk() -> None:
    """Excluded from the build, retained in the repository. Both, always."""
    target = REPO_ROOT / BROKEN_PROTOTYPE

    assert target.is_file(), (
        f"{BROKEN_PROTOTYPE} is gone. It is the audit's single documented "
        "whole-tree compile failure (Work Packet §4.2) and must be RETAINED "
        "as historical evidence while being EXCLUDED from the build. If it "
        "was deleted to make a build or lint run pass, restore it — the "
        "exclusion in pyproject.toml and MANIFEST.in is the supported fix."
    )
    assert target.stat().st_size > 0, f"{BROKEN_PROTOTYPE} is present but empty."

    relative = target.relative_to(REPO_ROOT).as_posix()
    assert any(
        relative.startswith(entry + "/")
        for entry in _production_build_table()["exclude"]
    ), (
        f"{relative} is retained but no longer sits under a declared "
        "production-build exclusion, so it would now ship."
    )


def test_the_broken_delegate_prototype_is_still_broken_on_purpose() -> None:
    """The evidence has not been quietly repaired.

    A green line here means the archived prototype still reproduces the exact
    failure the audit recorded. If this fails because the file now compiles,
    someone edited byte-preserved evidence; restore it rather than updating
    this expectation.
    """
    target = REPO_ROOT / BROKEN_PROTOTYPE

    with pytest.raises(SyntaxError) as caught:
        compile(target.read_bytes(), str(target), "exec", dont_inherit=True)

    error = caught.value
    assert isinstance(error, IndentationError), (
        f"Expected the recorded IndentationError, got {type(error).__name__}: {error}"
    )
    assert error.lineno == BROKEN_PROTOTYPE_ERROR_LINE, (
        f"Expected the failure at line {BROKEN_PROTOTYPE_ERROR_LINE}, got "
        f"line {error.lineno}: {error.msg}"
    )
    assert "elif" in (error.msg or ""), (
        f"Expected the recorded 'elif' block message, got: {error.msg}"
    )
