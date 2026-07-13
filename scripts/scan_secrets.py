#!/usr/bin/env python3
"""Repo secret-scan gate — wires ``hermes_cli.secrets_policy`` into CI / commits.

``hermes_cli/secrets_policy.py`` is the repo's single source of truth for
"what counts as a secret". It is already used at *publish* time
(``release_readiness_doctor``, ``decision_engine``, the cockpit handlers),
but nothing scanned commits or pull-request diffs. This script closes that
gap without adding a single new regex: it is a thin CLI over the existing
``scan_text`` / ``scan_file`` detectors.

Why diff mode is the default
----------------------------
A naive whole-tree scan over this repo surfaces ~19k findings, ~18.6k of
which are the low-precision ``high_entropy`` heuristic firing on long URLs
and base64 in docs. That heuristic is correct for a *redactor* (a false
positive is recoverable) but useless as a *blocking gate*. So the gate:

* scans only **added** lines (``+``) of a diff by default — existing,
  already-reviewed fixtures never re-trip it; and
* blocks only on **high-confidence** kinds (``known_prefix``, ``pem_block``,
  and ``env_name`` assignments that carry a value). ``high_entropy`` is
  reported as advisory and only blocks under ``--strict``.

Suppression
-----------
* Path allowlist (``--allow-path`` globs, plus a small built-in set for
  lockfiles and ``.env.example``) — these are credential *names*/placeholders
  by design, not values.
* Inline ``# pragma: allowlist secret`` on the offending line.

Exit codes: ``0`` clean, ``1`` blocking finding(s), ``2`` usage / git error.

Examples
--------
    # CI gate: scan the PR against its merge base
    python scripts/scan_secrets.py --base origin/main

    # local pre-commit: scan staged changes
    python scripts/scan_secrets.py --staged

    # full advisory audit of every tracked file
    python scripts/scan_secrets.py --tree
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

# Allow running both as ``python scripts/scan_secrets.py`` (no package
# context) and as a module. The repo root is the parent of ``scripts/``.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hermes_cli import secrets_policy as sp  # noqa: E402


# High-confidence detector kinds — these block by default. ``high_entropy``
# is deliberately excluded (advisory only) unless ``--strict`` is passed.
BLOCKING_KINDS: frozenset[str] = frozenset({"known_prefix", "pem_block", "env_name"})
ADVISORY_KINDS: frozenset[str] = frozenset({"high_entropy"})

# Inline escape hatch. A line carrying this marker is never reported.
ALLOWLIST_PRAGMA = "pragma: allowlist secret"

# A GitHub Actions expression as the *entire* assigned value — e.g.
# ``APPLE_CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}``.
# That is a *reference* to a secret, never the secret value itself; workflow
# files are full of these and they were the recurring ``env_name`` false
# positives that turned PR checks red (muse-desktop-release.yml, PR #423).
ACTIONS_EXPR_VALUE_PATTERN = re.compile(r"^\s*\$\{\{[^}]*\}\}\s*$")

# A shell/compose interpolation as the *entire* assigned value — e.g.
# ``POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`` or ``TOKEN: ${TOKEN:-}``.
# Same reasoning as the Actions expression above: the line passes a secret
# *by reference* to the runtime environment; no credential material is on
# the line (docker-compose.yml env passthroughs were the recurring case).
COMPOSE_INTERPOLATION_VALUE_PATTERN = re.compile(r"^\s*\$\{[^}]+\}\s*$")

# Mirrors the env-style assignment shape that the canonical ``env_name``
# detector in ``hermes_cli.secrets_policy.scan_text`` matches, so we can
# re-extract the assigned value for the Actions-expression check above.
_ENV_ASSIGNMENT_PATTERN = re.compile(r"\s*([A-Z][A-Z0-9_]*)\s*[:=]\s*(.+?)\s*$")

# Built-in path allowlist: credential *names* / placeholders live here by
# design, and lockfiles are machine-generated high-entropy noise.
DEFAULT_ALLOW_GLOBS: tuple[str, ...] = (
    "*.lock",
    "uv.lock",
    "package-lock.json",
    "*.example",
    ".env.example",
)


@dataclass(frozen=True)
class Hit:
    """A finding tied to a concrete location, ready to print (redacted)."""

    path: str
    line: int
    kind: str
    excerpt: str


def _run_git(args: Sequence[str]) -> str:
    """Run a read-only git command from the repo root; return stdout."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            # Diffs can carry historical lines that are not valid UTF-8
            # (e.g. a truncated multi-byte sequence in a deleted file).
            # Replace undecodable bytes instead of crashing — replacement
            # characters cannot form a credential, and removed lines are
            # never scanned anyway.
            errors="replace",
            check=True,
        )
    except FileNotFoundError:  # pragma: no cover - git always present in CI
        print("error: git not found on PATH", file=sys.stderr)
        raise SystemExit(2)
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or exc.stdout or "").strip()
        print(f"error: git {' '.join(args)} failed: {msg}", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def _is_allowed(path: str, allow_globs: Sequence[str]) -> bool:
    name = Path(path).name
    for pattern in allow_globs:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


def iter_added_lines(diff_text: str) -> Iterator[tuple[str, int, str]]:
    """Yield ``(path, new_line_number, added_text)`` for every ``+`` line.

    Parses a unified diff, tracking the new-file line counter from each
    ``@@ -a,b +c,d @@`` hunk header so reported line numbers point at the
    file as it will exist after the change.
    """
    current = "<unknown>"
    new_lineno = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            if target == "/dev/null":
                current = "<deleted>"
            else:
                current = target[2:] if target.startswith("b/") else target
            continue
        if raw.startswith("--- "):
            continue
        if raw.startswith("@@"):
            # @@ -old,cnt +new,cnt @@ optional section heading
            try:
                plus = raw.split("+", 1)[1]
                new_start = plus.split(",", 1)[0].split(" ", 1)[0]
                new_lineno = int(new_start)
            except (IndexError, ValueError):
                new_lineno = 0
            continue
        if raw.startswith("+"):
            yield current, new_lineno, raw[1:]
            new_lineno += 1
        elif raw.startswith("-"):
            continue
        elif raw.startswith("\\"):
            # "\ No newline at end of file"
            continue
        else:
            # context line (leading space) or blank
            new_lineno += 1


def _is_actions_expression_assignment(text: str) -> bool:
    """True if ``text`` assigns a pure GitHub Actions expression to a name.

    ``NAME: ${{ secrets.NAME }}`` / ``NAME=${{ env.NAME }}`` pass secrets
    *by reference*; no credential material is on the line. Anything beyond
    the lone expression (e.g. ``NAME: hunter2-${{ ... }}``) does not match
    and still flags.
    """
    m = _ENV_ASSIGNMENT_PATTERN.match(text)
    return bool(m and ACTIONS_EXPR_VALUE_PATTERN.match(m.group(2)))


def _is_interpolation_assignment(text: str) -> bool:
    """True if ``text`` assigns a pure ``${VAR}`` interpolation to a name.

    ``NAME: ${NAME}`` / ``NAME=${NAME:-default}`` pass secrets *by
    reference* (compose/shell interpolation); no credential material is on
    the line. Anything beyond the lone interpolation (e.g.
    ``NAME: hunter2-${SALT}``) does not match and still flags.
    """
    m = _ENV_ASSIGNMENT_PATTERN.match(text)
    return bool(m and COMPOSE_INTERPOLATION_VALUE_PATTERN.match(m.group(2)))


def _scan_line(path: str, lineno: int, text: str) -> list[Hit]:
    """Run the canonical detector on one line; suppress pragma lines."""
    if ALLOWLIST_PRAGMA in text:
        return []
    hits: list[Hit] = []
    for f in sp.scan_text(text, location=path):
        if f.kind == "env_name" and _is_actions_expression_assignment(text):
            # A workflow-expression reference, not a value — see
            # ACTIONS_EXPR_VALUE_PATTERN above.
            continue
        if f.kind == "env_name" and _is_interpolation_assignment(text):
            # A compose/shell interpolation reference, not a value — see
            # COMPOSE_INTERPOLATION_VALUE_PATTERN above.
            continue
        hits.append(Hit(path=path, line=lineno, kind=f.kind, excerpt=f.excerpt))
    return hits


def _pem_block_hit(path: str, numbered: Sequence[tuple[int, str]]) -> Hit | None:
    """Detect a multi-line PEM private key across a set of lines.

    ``secrets_policy.scan_text`` is line-oriented, so when a private key is
    added in its normal multi-line PEM form no single line carries both the
    BEGIN and END markers and ``pem_block`` is never reported (the body only
    trips advisory ``high_entropy``). We re-check the joined block against the
    canonical ``PEM_BLOCK_PATTERN`` (which is DOTALL) so the declared blocking
    kind actually blocks. Reuses the canonical pattern — no new regex.
    """
    joined = "\n".join(t for _, t in numbered)
    if ALLOWLIST_PRAGMA in joined or not sp.PEM_BLOCK_PATTERN.search(joined):
        return None
    begin = next(
        (no for no, t in numbered if "BEGIN" in t and "PRIVATE KEY" in t),
        numbered[0][0] if numbered else 0,
    )
    return Hit(
        path=path,
        line=begin,
        kind="pem_block",
        excerpt="-----BEGIN …PRIVATE KEY----- (multi-line block, redacted)",
    )


def scan_diff_text(diff_text: str, allow_globs: Sequence[str]) -> list[Hit]:
    hits: list[Hit] = []
    by_file: dict[str, list[tuple[int, str]]] = {}
    for path, lineno, text in iter_added_lines(diff_text):
        if path in ("<deleted>", "<unknown>") or _is_allowed(path, allow_globs):
            continue
        hits.extend(_scan_line(path, lineno, text))
        by_file.setdefault(path, []).append((lineno, text))
    for path, numbered in by_file.items():
        pem = _pem_block_hit(path, numbered)
        if pem is not None:
            hits.append(pem)
    return hits


def scan_tree(allow_globs: Sequence[str]) -> list[Hit]:
    tracked = _run_git(["ls-files"]).splitlines()
    hits: list[Hit] = []
    for path in tracked:
        if not path or _is_allowed(path, allow_globs):
            continue
        p = (_REPO_ROOT / path)
        if not p.is_file():
            continue
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # binary / unreadable — scan_file would skip it too
        numbered = list(enumerate(lines, start=1))
        for idx, text in numbered:
            hits.extend(_scan_line(path, idx, text))
        pem = _pem_block_hit(path, numbered)
        if pem is not None:
            hits.append(pem)
    return hits


def partition(hits: Iterable[Hit], *, strict: bool) -> tuple[list[Hit], list[Hit]]:
    """Split hits into (blocking, advisory) per the configured kind policy."""
    block_kinds = BLOCKING_KINDS | (ADVISORY_KINDS if strict else frozenset())
    blocking: list[Hit] = []
    advisory: list[Hit] = []
    for h in hits:
        (blocking if h.kind in block_kinds else advisory).append(h)
    return blocking, advisory


def _print_hits(title: str, hits: Sequence[Hit], stream) -> None:
    print(title, file=stream)
    for h in hits:
        print(f"  {h.path}:{h.line} [{h.kind}] {h.excerpt}", file=stream)


def _resolve_diff(args: argparse.Namespace) -> str:
    if args.tree:
        return ""  # not used in tree mode
    if args.staged:
        return _run_git(["diff", "--no-color", "--cached"])
    if args.base:
        # three-dot: diff against the merge base, matching the lint workflow.
        return _run_git(["diff", "--no-color", f"{args.base}...HEAD"])
    return _run_git(["diff", "--no-color", "HEAD"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan_secrets.py",
        description=(
            "Block commits/PRs that add high-confidence secrets, reusing "
            "hermes_cli.secrets_policy. Diff mode (default) scans only added "
            "lines; --tree scans every tracked file (advisory)."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--base",
        metavar="REF",
        help="diff against the merge base of REF and HEAD (e.g. origin/main)",
    )
    mode.add_argument(
        "--staged", action="store_true", help="scan staged (index) changes"
    )
    mode.add_argument(
        "--tree", action="store_true", help="scan every tracked file (advisory)"
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="also block on the low-precision high_entropy heuristic",
    )
    p.add_argument(
        "--allow-path",
        action="append",
        default=[],
        metavar="GLOB",
        help="extra path glob to skip (repeatable)",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    allow_globs = (*DEFAULT_ALLOW_GLOBS, *args.allow_path)

    if args.tree:
        hits = scan_tree(allow_globs)
        scope = "tracked files"
    else:
        diff_text = _resolve_diff(args)
        hits = scan_diff_text(diff_text, allow_globs)
        scope = (
            f"merge-base {args.base}...HEAD"
            if args.base
            else "staged changes"
            if args.staged
            else "working tree vs HEAD"
        )

    blocking, advisory = partition(hits, strict=args.strict)

    if advisory:
        _print_hits(
            f"advisory ({len(advisory)} high-entropy match(es) — not blocking):",
            advisory,
            sys.stderr,
        )

    if blocking:
        _print_hits(
            f"BLOCKED: {len(blocking)} potential secret(s) in {scope}:",
            blocking,
            sys.stderr,
        )
        print(
            "\nIf a match is a false positive, add `# pragma: allowlist secret` "
            "to the line\nor pass --allow-path for fixture paths. Values are "
            "never printed.",
            file=sys.stderr,
        )
        return 1

    print(f"ok: no high-confidence secrets in {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
