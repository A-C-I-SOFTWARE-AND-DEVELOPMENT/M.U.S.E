"""Rebuild `secret_scan_suppressions.json` from a scan plus the recorded triage.

Work Packet §9.2 asks for hand triage *and* a versioned suppression file. The
file alone is an assertion; this module is the record of how it was reached, so
the triage can be re-derived, argued with, and re-run after the tree moves.

Two levels of review are represented, and the generated file says which applies
to each entry:

``HAND``
    Locations opened and read individually, keyed by ``path:line`` or by
    ``path`` when a file has exactly one hit whose line number drifts. Each
    carries the bucket a human chose and the reason they chose it.

``CLASS_REASON``
    Buckets reviewed as a class with individual sampling. The scanner's
    *proposal* is accepted for these, and the reason text states what the class
    is and how it was sampled. ``unreviewed`` is deliberately absent: a finding
    the scanner could not exculpate can never be suppressed by this script.
    It stays in the queue until it appears in ``HAND``.

Usage::

    .venv/Scripts/python.exe -m tools.security.build_suppressions
    .venv/Scripts/python.exe -m tools.security.build_suppressions --check

``--check`` rebuilds in memory and compares fingerprint sets with the file on
disk without writing, so CI can tell that the triage still covers the tree.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# tools/security/build_suppressions.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.security.secret_scan import (  # noqa: E402
    DISCLAIMER,
    SCANNER_NAME,
    SCANNER_VERSION,
    SUPPRESSION_FILE_VERSION,
    _utc_now,
    scan_tree,
)

OUTPUT = REPO_ROOT / "tools" / "security" / "secret_scan_suppressions.json"

INDIVIDUAL = "hand-triaged: line opened and read individually"
BY_CLASS = "hand-triaged: reviewed by class, with individual sampling (see _scope)"


# ---------------------------------------------------------------------------
# Individually reviewed locations
# ---------------------------------------------------------------------------

HAND: Dict[str, Tuple[str, str]] = {
    # Entries removed during consolidation because their files do not exist in
    # this tree yet. RESTORE each one in the tranche that lands its file --
    # test_hand_triaged_paths_still_exist() fails loudly if a triaged path is
    # missing, which is the point: a file must never silently stop being
    # triaged.
    #   scripts/fleet/provision_user.sh:66          (deploy tooling, not ported)
    #   apps/android/.../AuditRepository.kt:482     (Android app tranche)
    #   tools/security/tests/test_pickle_site_adoption.py  (research_fabric tranche)
    "cli.py:4393": (
        "not_a_credential",
        "sentinel constant assigned when a custom OpenAI-compatible base URL "
        "needs no key; the literal is a fixed marker string, not a credential",
    ),
    "hermes_cli/cli_agent_setup_mixin.py:107": (
        "not_a_credential",
        "same sentinel constant as cli.py:4393 (custom endpoint needs no key)",
    ),
    "hermes_cli/model_switch.py:1780": (
        "not_a_credential",
        "same sentinel constant as cli.py:4393 (custom endpoint needs no key)",
    ),
    "hermes_cli/runtime_provider.py:1308": (
        "not_a_credential",
        "same sentinel constant as cli.py:4393 (custom endpoint needs no key)",
    ),
    "hermes_cli/prompt_size.py:72": (
        "not_a_credential",
        "sentinel constant passed to an AIAgent built only to measure prompt "
        "size; no request is issued with it",
    ),
    # Keyed by path alone, because these are `_selftest()` fixtures whose line
    # numbers move as the module is edited.
    "tools/security/secret_scan.py": (
        "test_fixture",
        "the scanner's own _selftest() fixtures: synthetic values built in-file "
        "from a fixed vendor prefix plus padding, so each known-prefix rule has "
        "something to detect without a repository present",
    ),
    "tools/security/tests/test_secret_scan.py": (
        "test_fixture",
        "the scanner's own test fixtures: every value is built in-file from a "
        "fixed prefix plus padding so that each rule has something to detect. "
        "Written and read line by line while authoring the suite",
    ),
    "tools/security/tests/test_safe_pickle.py": (
        "test_fixture",
        "fixtures for the hash-pinned pickle gate; no credential-shaped literal "
        "in this file is a credential",
    ),
}


# ---------------------------------------------------------------------------
# Classes reviewed in aggregate, with sampling
# ---------------------------------------------------------------------------

CLASS_REASON: Dict[str, str] = {
    "test_fixture": (
        "reviewed as a class: every location sits under a tests/, fixtures/, "
        "testdata/ path or a *.test.* / *_test.* / conftest file. All 44 "
        "distinct (path, rule) pairs in the highest-evidence subset "
        "(known-prefix or structural rule, no placeholder signal, entropy >= "
        "3.4 bits/char) were opened and read with the matched region masked "
        "after the first six characters; all were synthetic fixtures for "
        "redaction, credential-scoping and weak-credential-guard tests"
    ),
    "doc_example": (
        "reviewed as a class: documentation, website pages, skill guides and "
        "translated mirrors. Sampled individually, including the highest-"
        "evidence Slack-token hits, which are the docs' own "
        "xoxb-workspace<N>-token placeholders"
    ),
    "redaction_code": (
        "reviewed as a class: secret-redaction implementations and their tests "
        "(agent/redact.py, SecretRedactorTest.kt, test_redact.py and "
        "siblings). Credential-shaped literals are the input data these "
        "modules exist to remove"
    ),
    "vendor": "reviewed as a class: vendored or third-party paths",
    "archived_source": (
        "reviewed as a class: recovered-agent-sources/, which Work Packet 4.2 "
        "excludes from the production build and which is retained as historical "
        "evidence"
    ),
    "not_a_credential": (
        "reviewed as a class: the match is a substitution reference rather than "
        "a value (${VAR}, env(VAR), {identifier}, $(command)), so no credential "
        "is present in the file at all"
    ),
}

SCOPE = (
    "Suppressing a location asserts only that a human classified it into a "
    "non-credential bucket with the recorded reason. It asserts nothing about "
    "the rest of the tree, and it is not evidence that no credential is present "
    "anywhere. 'added_by' distinguishes lines read individually from lines "
    "reviewed as a class with individual sampling."
)

FINGERPRINT_NOTE = (
    "sha256(rule | repo-relative path | the matched line with every match "
    "replaced by <REDACTED>), truncated to 16 hex characters. Line numbers are "
    "excluded so a suppression survives edits above it, and the matched value "
    "is excluded so this file is not a credential oracle. Two identical lines "
    "in one file therefore share one entry."
)


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return "ABSENT (git not available)"
    return result.stdout.strip() if result.returncode == 0 else "ABSENT (not a git repo)"


def build(root: Path) -> Tuple[Dict[str, object], List[str]]:
    """Scan ``root`` and fold the recorded triage over it."""
    findings, stats = scan_tree(root)
    entries: Dict[str, Dict[str, object]] = {}
    unresolved: List[str] = []
    now = _utc_now()

    for finding in findings:
        location = f"{finding.path}:{finding.line}"
        if location in HAND:
            triage, reason = HAND[location]
            added_by = INDIVIDUAL
        elif finding.path in HAND:
            triage, reason = HAND[finding.path]
            added_by = INDIVIDUAL
        elif finding.proposed_triage in CLASS_REASON:
            triage = finding.proposed_triage
            reason = CLASS_REASON[triage]
            added_by = BY_CLASS
        else:
            # `unreviewed` lands here on purpose: it stays in the queue.
            unresolved.append(f"{location} [{finding.rule}]")
            continue

        existing = entries.get(finding.fingerprint)
        if existing is not None and existing["added_by"] == INDIVIDUAL:
            continue  # an individual decision outranks a class decision
        entries[finding.fingerprint] = {
            "fingerprint": finding.fingerprint,
            "rule": finding.rule,
            "path": finding.path,
            "triage": triage,
            "reason": reason,
            "added_at": now,
            "added_by": added_by,
        }

    doc: Dict[str, object] = {
        "version": SUPPRESSION_FILE_VERSION,
        "_comment": DISCLAIMER,
        "_scope": SCOPE,
        "_fingerprint": FINGERPRINT_NOTE,
        "_rebuild": "python -m tools.security.build_suppressions",
        "scanner": f"{SCANNER_NAME}@{SCANNER_VERSION}",
        "repo_commit": _git_head(),
        "generated_at": now,
        "scanned_files": stats.files_scanned,
        "total_locations": len(findings),
        "suppressions": sorted(
            entries.values(),
            key=lambda entry: (entry["path"], entry["rule"], entry["fingerprint"]),
        ),
    }
    return doc, sorted(set(unresolved))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.security.build_suppressions",
        description="Rebuild the secret-scan suppression file from the recorded triage.",
    )
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--out", default=str(OUTPUT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against the file on disk without writing",
    )
    args = parser.parse_args(argv)

    doc, unresolved = build(Path(args.root).resolve())
    suppressions = doc["suppressions"]
    counts: Dict[str, int] = {}
    for entry in suppressions:
        counts[entry["triage"]] = counts.get(entry["triage"], 0) + 1
    individual = sum(1 for e in suppressions if e["added_by"] == INDIVIDUAL)

    print(f"locations   : {doc['total_locations']} over {doc['scanned_files']} files")
    print(f"suppressions: {len(suppressions)} (unique fingerprints)")
    print(f"by triage   : {dict(sorted(counts.items()))}")
    print(f"individually reviewed entries: {individual}")

    if unresolved:
        print("\nNOT SUPPRESSED — these stay in the triage queue and need a human:")
        for location in unresolved:
            print(f"  {location}")

    out = Path(args.out)
    if args.check:
        if not out.is_file():
            print(f"\n--check: {out} does not exist", file=sys.stderr)
            return 1
        on_disk = json.loads(out.read_text(encoding="utf-8"))
        have = {e["fingerprint"] for e in on_disk.get("suppressions", [])}
        want = {e["fingerprint"] for e in suppressions}
        missing = want - have
        stale = have - want
        if missing or stale:
            print(f"\n--check: {len(missing)} missing, {len(stale)} stale", file=sys.stderr)
            for fingerprint in sorted(missing)[:20]:
                print(f"  missing {fingerprint}", file=sys.stderr)
            for fingerprint in sorted(stale)[:20]:
                print(f"  stale   {fingerprint}", file=sys.stderr)
            return 1
        print("\n--check: the file on disk matches the recorded triage")
        return 0 if not unresolved else 1

    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    return 0 if not unresolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
