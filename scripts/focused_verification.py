#!/usr/bin/env python3
"""The focused verification run, as a standing gate. Work Packet §4.2, §8.2, §14.2.

The packet records a focused run over the modules that carry the architecture:
Agent Factory, Agent Market, Blackboard, Grainler, the swarm executor and
coordinator, the AXIOM bridge, GraphRAG, Memory Tree, and the Research Fabric
ratchet and benchmarks. It is the one result the packet labels OBSERVED rather
than REPO-RECORDED, and §14.2 asks for it to become a standing gate rather than
a number quoted from a PDF.

This is that gate. It runs only the focused set, so it stays fast enough to be
run on every change — the full suite is a different tool for a different job.

**On the count.** The packet recorded 116 passed / 0 failed in 2.35 s under
Python 3.13.5, against the pinned archive. This gate is pinned to nothing: it
reports what the current tree produces. Those numbers should NOT be expected to
match, and a mismatch is not a failure — the file set, the revision and the
interpreter all differ. What the gate enforces is **zero failures**, not a
particular total. Asserting the total would make it a change-detector test, which
this repository's own guidance forbids.

The suite's configured ``addopts`` require xdist/timeout plugins. They are
installed now, but the gate overrides ``addopts`` anyway so it runs identically
on a machine that lacks them.

    python scripts/focused_verification.py
    python scripts/focused_verification.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The architecture-carrying subsystems this gate protects. Each entry is
# (subsystem, test path). A path that no longer exists is reported as a
# MISSING subsystem rather than silently dropped -- a gate that quietly
# shrinks is worse than no gate.
#
# CONSOLIDATION CONTRACT: this set starts empty because the consolidated repo
# begins from pristine upstream, where none of the fork's subsystems exist yet.
# Every port tranche that lands an architecture-carrying subsystem MUST append
# its row here in the same commit. See docs/consolidation/PORT-LEDGER.md.
FOCUSED_SET: tuple[tuple[str, str], ...] = (
)

SUMMARY_RE = re.compile(
    r"(?:(?P<passed>\d+) passed)?(?:, )?(?:(?P<failed>\d+) failed)?"
    r"(?:, )?(?:(?P<errors>\d+) error)?(?:, )?(?:(?P<skipped>\d+) skipped)?"
)


def python_exe() -> str:
    venv = REPO / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def run(json_out: bool = False) -> int:
    present, missing = [], []
    for subsystem, path in FOCUSED_SET:
        (present if (REPO / path).is_file() else missing).append((subsystem, path))

    if not present:
        print("no focused test file is present; the gate cannot run", file=sys.stderr)
        return 2

    started = time.time()
    proc = subprocess.run(
        [python_exe(), "-m", "pytest", *[p for _, p in present],
         "-p", "no:cacheprovider", "-o", "addopts=", "-q", "--no-header"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    elapsed = time.time() - started
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else ""
    counts = {k: int(v) for k, v in (SUMMARY_RE.search(summary) or
                                     re.match("", "")).groupdict(default="0").items()} \
        if SUMMARY_RE.search(summary) else {}

    failed = counts.get("failed", 0) + counts.get("errors", 0)
    result = {
        "subsystems_run": len(present),
        "subsystems_missing": [s for s, _ in missing],
        "passed": counts.get("passed", 0),
        "failed": counts.get("failed", 0),
        "errors": counts.get("errors", 0),
        "skipped": counts.get("skipped", 0),
        "seconds": round(elapsed, 2),
        "gate": "PASS" if failed == 0 and not missing else "FAIL",
        "packet_reference": "116 passed / 0 failed in 2.35s under Python 3.13.5, "
                            "against the pinned archive — a different revision and "
                            "interpreter. The totals are not expected to match; the "
                            "gate enforces zero failures, not a particular count.",
    }

    if json_out:
        print(json.dumps(result, indent=2))
    else:
        print(f"focused verification — {len(present)}/{len(FOCUSED_SET)} subsystems\n")
        for subsystem, _ in present:
            print(f"  included  {subsystem}")
        for subsystem, path in missing:
            print(f"  MISSING   {subsystem}  ({path})")
        print(f"\n  {summary}")
        print(f"  gate: {result['gate']}")
        if missing:
            print("\n  A subsystem's test file has moved or been deleted. The gate "
                  "fails rather than\n  quietly covering less than it claims.")
    return 0 if result["gate"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return run(json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
