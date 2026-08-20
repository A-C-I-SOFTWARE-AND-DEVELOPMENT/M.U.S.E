#!/usr/bin/env python3
"""Classify every shared file the fork modified, so the port never guesses.

Run once. Commit the CSV. Do not re-derive it by hand.

The fork and this repo share history, but a merge in the fork's past
(``d938501dd3``) resolved 756 conflicts inconsistently in both directions --
taking some files wholesale from one side while keeping importers from the
other. Thirteen files lost roughly 794 upstream symbols that way.

So "what did the fork change" is the wrong question: the fork's tip is
contaminated by that merge and by the partial repairs that followed. This
script separates five very different situations:

``D``           Damage. Upstream symbols vanished from the fork's copy and did
                not move elsewhere. NEVER port this file from the fork tip.
                Port ``git diff FORKPOINT PREMERGE -- <path>`` -- the fork's
                *true* delta -- onto upstream's current file instead.
``BRANDING``    Every line the fork touched is a pure rename. Discard.
``BINARY-ASSET`` A logo, banner or favicon. Decided by eye, never merged.
``PORT-AS-IS``  The fork's delta applies cleanly onto upstream today.
                NOTE: "applies cleanly" answers *can we*, never *should we* --
                check the ``carries_brand`` column before taking one.
``PORT-DELTA``  Real work that needs hand-porting.

Usage:
    uv run python scripts/consolidation/triage_shared_files.py \\
        --out docs/consolidation/triage.csv
"""

from __future__ import annotations

import argparse
import ast
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

# Reference points. See docs/consolidation/PORT-LEDGER.md.
BASE = "a98aee47ce"  # upstream v0.20.0 -- the fork's merge base
FORKPOINT = "e2fd462ebe"  # true fork point
PREMERGE = "bb78a5bf1c"  # fork tip immediately before the bad merge
FORK = "8552232a8f"  # fork freeze commit
UPSTREAM = "2d92793045"  # upstream at consolidation start

# Where the fork's full tree is checked out, for the relocation index.
FORK_WORKTREE = Path(r"C:\Users\Echer\refs\muse-tip")

# Directories whose symbols do not count as "relocated" -- vendored or
# archival trees are not where a live definition legitimately moves to.
INDEX_SKIP = {
    ".git", "venv", ".venv", "node_modules", "__pycache__", "build", "dist",
    "website", "third_party", "site-packages",
}

# Applied to both sides before comparing, to decide "is this only a rename?"
BRANDING_SUBS = [
    (re.compile(r"M\.U\.S\.E\.?", re.I), "Hermes"),
    (re.compile(r"\bMUSE_"), "HERMES_"),
    (re.compile(r"\bMUSE\b"), "HERMES"),
    (re.compile(r"\bMuse\b"), "Hermes"),
    (re.compile(r"\bmuse\b"), "hermes"),
    (re.compile(r"\bsingularity\b", re.I), "default"),
    (re.compile(r"\bcaduceus\b", re.I), "default"),
    (re.compile(r"\bjarvis_prime\b", re.I), "prime"),
    (re.compile(r"\bjarvis\b", re.I), "prime"),
]


def git(*args: str, repo: Path | None = None) -> tuple[int, str]:
    """Run git, tolerating this tree's mixed encodings."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo) if repo else None,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


def git_bytes(*args: str) -> tuple[int, bytes]:
    """Run git in BINARY mode.

    Diffs must never round-trip through text decoding. ``errors="replace"``
    silently rewrites bytes it cannot decode, and the resulting patch no
    longer matches the blobs it came from -- ``git apply`` then reports a
    conflict that does not exist. Measured on one 5,776-byte diff: the
    text-mode capture lost 12 bytes and turned a clean apply into a failure.
    """
    proc = subprocess.run(["git", *args], capture_output=True)
    return proc.returncode, proc.stdout


# Blobs above this are not source we can meaningfully classify, and reading
# one can exhaust memory (a checkpoint committed into the fork's history did).
MAX_BLOB_BYTES = 4 * 1024 * 1024


def blob(ref: str, path: str) -> str | None:
    """File content at a ref, or None if absent or implausibly large."""
    code, size_out = git("cat-file", "-s", f"{ref}:{path}")
    if code != 0:
        return None
    try:
        if int(size_out.strip()) > MAX_BLOB_BYTES:
            return None
    except ValueError:
        return None
    code, out = git("show", f"{ref}:{path}")
    return out if code == 0 else None


def top_level_names(src: str) -> set[str]:
    """Module-level defs, classes and assignments. Empty set if unparseable."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def build_relocation_index(root: Path) -> set[str]:
    """Every module-level name defined anywhere in the fork tree.

    This is what stops a legitimate refactor from being reported as damage: a
    symbol that moved to another module is still present in the fork, just not
    where it used to be.
    """
    names: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in INDEX_SKIP]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            try:
                src = (Path(dirpath) / name).read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                continue
            names |= top_level_names(src)
    return names


def normalize(text: str) -> str:
    for pattern, repl in BRANDING_SUBS:
        text = pattern.sub(repl, text)
    return text


def normalize_ident(name: str) -> str:
    """Normalize a *symbol* name, where word boundaries do not apply.

    ``\\bmuse\\b`` cannot match inside ``test_muse_launcher_x``: ``_`` is a word
    character, so there is no boundary between it and ``m``. Symbol comparison
    therefore needs boundary-free substitution, or a branding rename of a
    snake_case function reads as a vanished symbol -- i.e. as merge damage.
    """
    lowered = name.lower()
    for src, dst in (("muse", "hermes"), ("jarvis_prime", "prime"), ("jarvis", "prime")):
        lowered = lowered.replace(src, dst)
    return lowered


def applies_cleanly(path: str) -> bool:
    """Does the fork's delta land on upstream today without conflict?

    Bytes end to end -- see ``git_bytes``.
    """
    code, diff = git_bytes("diff", BASE, FORK, "--", path)
    if code != 0 or not diff.strip():
        return False
    proc = subprocess.run(
        ["git", "apply", "--3way", "--check", "-"], input=diff, capture_output=True
    )
    return proc.returncode == 0


def is_branding_only(path: str) -> bool:
    """True when every line the fork touched is a pure rename.

    The whole-file comparison is the strict test; this is the honest one. A
    file can carry a rename sweep and nothing else while still differing from
    base in ways whole-file equality misses (reflowed docstrings, reordered
    imports). Here we compare only the lines the diff actually changed: if the
    removed set and the added set are equal once branding is normalized away,
    the change carries no meaning of its own.
    """
    code, raw = git_bytes("diff", "-U0", BASE, FORK, "--", path)
    if code != 0 or not raw.strip():
        return False
    text = raw.decode("utf-8", errors="replace")
    removed, added = [], []
    for line in text.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    if not removed and not added:
        return False
    return normalize("\n".join(removed)) == normalize("\n".join(added))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/consolidation/triage.csv")
    args = ap.parse_args()

    code, out = git("diff", "--name-only", "--diff-filter=M", f"{BASE}..{FORK}")
    if code != 0:
        print("could not list modified files; are all refs fetched?", file=sys.stderr)
        return 1
    paths = [p for p in out.splitlines() if p.strip()]
    print(f"{len(paths)} shared files modified by the fork", file=sys.stderr)

    print("indexing fork symbols for relocation detection...", file=sys.stderr)
    index = build_relocation_index(FORK_WORKTREE)
    print(f"  {len(index)} module-level names across the fork tree", file=sys.stderr)

    rows = []
    for i, path in enumerate(paths, 1):
        if i % 100 == 0:
            print(f"  {i}/{len(paths)}", file=sys.stderr)

        b, f, u = blob(BASE, path), blob(FORK, path), blob(UPSTREAM, path)
        row = {
            "path": path,
            "class": "",
            "gone_syms": "",
            "n_gone": 0,
            "lines_base": len(b.splitlines()) if b else "",
            "lines_premerge": "",
            "lines_fork": len(f.splitlines()) if f else "",
            "lines_upstream": len(u.splitlines()) if u else "",
            "applies_3way": "",
            "carries_brand": "",
            "tranche": "",
        }

        # Does the fork's change mention its own branding anywhere? A file can
        # apply cleanly and still be one we must not take: "applies cleanly"
        # answers *can we*, never *should we*.
        _, bd = git_bytes("diff", "-U0", BASE, FORK, "--", path)
        low = bd.decode("utf-8", errors="replace").lower()
        row["carries_brand"] = (
            "yes"
            if any(w in low for w in ("muse", "jarvis", "singularity", "caduceus"))
            else "no"
        )

        if u is None:
            # Upstream deleted it. Nothing to port onto.
            row["class"] = "UPSTREAM-GONE"
            rows.append(row)
            continue

        # --- Step 1: damage, before anything else -----------------------
        if path.endswith(".py") and b and f:
            m = blob(PREMERGE, path)
            row["lines_premerge"] = len(m.splitlines()) if m else ""
            fork_names = top_level_names(f)
            lost = top_level_names(b) - fork_names
            damaged = lost & top_level_names(u)
            # A symbol the fork merely RENAMED for branding is not damage.
            # `test_hermes_launcher_x` -> `test_muse_launcher_x` looks like a
            # vanished symbol until both sides are normalized.
            renamed = {normalize_ident(n) for n in fork_names}
            gone = sorted(
                s
                for s in damaged
                if s not in index and normalize_ident(s) not in renamed
            )
            if gone:
                row["class"] = "D"
                row["n_gone"] = len(gone)
                row["gone_syms"] = " ".join(gone[:20])
                rows.append(row)
                continue

        # --- Step 2: branding-only --------------------------------------
        if b is not None and f is not None and normalize(f) == normalize(b):
            row["class"] = "BRANDING"
            rows.append(row)
            continue
        if is_branding_only(path):
            row["class"] = "BRANDING"
            rows.append(row)
            continue

        # --- Step 3: binary assets --------------------------------------
        # git apply cannot 3-way a binary blob, so these would masquerade as
        # hand-port work. They are logos, banners and favicons: brand assets,
        # decided by eye, not merged.
        _, probe = git_bytes("diff", "--numstat", BASE, FORK, "--", path)
        if probe.startswith(b"-\t-\t"):
            row["class"] = "BINARY-ASSET"
            rows.append(row)
            continue

        # --- Step 4: clean delta ----------------------------------------
        clean = applies_cleanly(path)
        row["applies_3way"] = "yes" if clean else "no"
        row["class"] = "PORT-AS-IS" if clean else "PORT-DELTA"
        rows.append(row)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["class"]] = tally.get(r["class"], 0) + 1
    print(f"\nwrote {out_path}", file=sys.stderr)
    for cls, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {cls:<14} {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
