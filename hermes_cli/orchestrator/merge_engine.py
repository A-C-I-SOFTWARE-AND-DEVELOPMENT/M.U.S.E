"""Unified-diff merge engine.

We don't try to be a full three-way merger. Instead we parse a diff into
per-file hunks and detect whether two diffs touch overlapping line
ranges in the same file. Two diffs are "conflict-free" if no file
appears in both, or — for files that appear in both — none of their
hunks overlap. Conflict-free diffs are merged by concatenating their
hunks in stable file order.

This is enough to satisfy the orchestrator's "merge if compatible"
contract; anything more sophisticated is delegated to ``git apply``
or a real merge tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FILE_RE = re.compile(r"^\+\+\+\s+(?:b/)?(\S+)\s*$")
_OLD_FILE_RE = re.compile(r"^---\s+(?:a/)?(\S+)\s*$")
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    body: list[str] = field(default_factory=list)

    def serialize(self) -> str:
        header = (
            f"@@ -{self.old_start},{self.old_count} "
            f"+{self.new_start},{self.new_count} @@"
        )
        return "\n".join([header, *self.body])

    def overlaps(self, other: "Hunk") -> bool:
        a0, a1 = self.new_start, self.new_start + max(self.new_count, 1) - 1
        b0, b1 = other.new_start, other.new_start + max(other.new_count, 1) - 1
        return not (a1 < b0 or b1 < a0)


@dataclass
class FilePatch:
    path: str
    old_path: str
    header_lines: list[str] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)

    def serialize(self) -> str:
        parts: list[str] = []
        parts.extend(self.header_lines)
        for h in self.hunks:
            parts.append(h.serialize())
        return "\n".join(parts)


def parse_diff(diff: str) -> dict[str, FilePatch]:
    """Parse a unified diff into ``{path: FilePatch}``.

    Robust against blank diffs and trailing newlines. Unknown header
    lines (``diff --git``, ``index``, ``new file mode``, etc.) are
    captured under the current file's ``header_lines`` so they
    round-trip when we re-serialize.
    """

    if not diff or not diff.strip():
        return {}

    files: dict[str, FilePatch] = {}
    current: FilePatch | None = None
    current_hunk: Hunk | None = None
    pending_headers: list[str] = []
    pending_old: str | None = None

    for line in diff.splitlines():
        old_m = _OLD_FILE_RE.match(line)
        new_m = _FILE_RE.match(line)
        hunk_m = _HUNK_RE.match(line)

        if old_m:
            pending_old = old_m.group(1)
            pending_headers.append(line)
            current_hunk = None
            continue
        if new_m:
            path = new_m.group(1)
            current = FilePatch(
                path=path, old_path=pending_old or path,
                header_lines=[*pending_headers, line],
            )
            files[path] = current
            pending_headers = []
            pending_old = None
            current_hunk = None
            continue
        if hunk_m:
            if current is None:
                # malformed: hunk without a file — skip
                continue
            old_start = int(hunk_m.group(1))
            old_count = int(hunk_m.group(2) or 1)
            new_start = int(hunk_m.group(3))
            new_count = int(hunk_m.group(4) or 1)
            current_hunk = Hunk(old_start, old_count, new_start, new_count, [])
            current.hunks.append(current_hunk)
            continue

        if current_hunk is not None:
            current_hunk.body.append(line)
        else:
            pending_headers.append(line)

    return files


def has_conflicts(diff_a: str, diff_b: str) -> bool:
    """True iff diffs touch overlapping line ranges in the same file."""
    fa = parse_diff(diff_a)
    fb = parse_diff(diff_b)
    common = set(fa.keys()) & set(fb.keys())
    for path in common:
        for ha in fa[path].hunks:
            for hb in fb[path].hunks:
                if ha.overlaps(hb):
                    return True
    return False


@dataclass
class MergeResult:
    diff: str
    merged_files: list[str]
    conflicts: list[str]

    @property
    def ok(self) -> bool:
        return not self.conflicts


def merge_diffs(diffs: list[str]) -> MergeResult:
    """Merge a list of unified diffs.

    Returns a :class:`MergeResult` whose ``diff`` is the concatenation
    of non-conflicting per-file patches and whose ``conflicts`` lists
    files that had overlapping hunks between two or more inputs.
    """

    parsed = [parse_diff(d) for d in diffs if d]
    if not parsed:
        return MergeResult(diff="", merged_files=[], conflicts=[])

    merged: dict[str, FilePatch] = {}
    conflicts: set[str] = set()

    for files in parsed:
        for path, patch in files.items():
            if path in conflicts:
                continue
            if path not in merged:
                merged[path] = patch
                continue
            # Two patches for the same path — check hunk overlap.
            existing = merged[path]
            conflict = False
            for h_new in patch.hunks:
                for h_old in existing.hunks:
                    if h_new.overlaps(h_old):
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                conflicts.add(path)
                merged.pop(path, None)
            else:
                # Combine hunks, sorted by new_start for stability.
                combined = sorted(
                    existing.hunks + patch.hunks, key=lambda h: h.new_start
                )
                existing.hunks = combined

    body_parts = [merged[p].serialize() for p in sorted(merged.keys())]
    diff_out = "\n".join(body_parts)
    if diff_out and not diff_out.endswith("\n"):
        diff_out += "\n"
    return MergeResult(
        diff=diff_out,
        merged_files=sorted(merged.keys()),
        conflicts=sorted(conflicts),
    )


def apply_diff(
    workdir: Path | str, diff: str, *, runner=None
) -> bool:
    """Apply ``diff`` to ``workdir`` using ``git apply --check`` + ``--apply``.

    Tests pass a fake ``runner`` so this never touches a real workspace.
    Returns True iff both check and apply exit 0.
    """
    from hermes_cli.workers.base import _real_runner  # avoid cycle at import time

    workdir = Path(workdir)
    if not diff.strip():
        return True
    runner = runner or _real_runner
    # Stream the diff via a temp file so we don't have to wire stdin into
    # the runner contract.
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".diff", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(diff)
        path = tf.name
    try:
        rc, _ = runner(["git", "apply", "--check", path], workdir, None)
        if rc != 0:
            return False
        rc, _ = runner(["git", "apply", path], workdir, None)
        return rc == 0
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


__all__ = [
    "FilePatch",
    "Hunk",
    "MergeResult",
    "apply_diff",
    "has_conflicts",
    "merge_diffs",
    "parse_diff",
]
