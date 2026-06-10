# FU-D1: Repo root tidy — releases/AOS/audit reports into docs/

- **Status:** in-review
- **Risk class:** additive (doc-only file moves + link rewrites; no runtime code change)
- **Branch:** `claude/fu-d1-root-tidy` · **Base:** `main` @ `e283d39ea0df678223eb2392f5b94f6b84af1606`
- **PR:** draft (Wave D G1)
- **Owner-gate required to merge?** no — strictly additive doc reorganization; no default runtime behavior change

## Intent (one paragraph)

The repo root carried 28 historical Markdown reports that belong in the
`docs/` tree: 13 `RELEASE_v0.*.md` release notes, 9 `AOS_*.md` recovery
artifacts (already mirrored in `docs/aos-recovery/`), and 6 audit /
integration reports. This task moves the release notes to a new
`docs/releases/` (with an index README), makes `docs/aos-recovery/`
the canonical home of the AOS artifacts (removing the root copies),
moves the 6 audit reports into the existing `docs/audits/`, and
rewrites every live inbound reference — no redirect stubs.
`CANONICAL_REPO.md` stays at root (bare-path fixture in
`tests/test_jarvis_prime_work_packet.py:34`).

## Key finding during build (brief correction)

The grain brief said the 3 differing root `AOS_*.md` copies were
*newer* than `docs/aos-recovery/`. Verification showed the opposite:
`docs/aos-recovery/` copies carry the WC-4 honesty annotations
(commit `d0108e5d4`) and the hermes→muse rebrand (commit `a7d660e63`,
2026-06-09), while the root copies were last touched at `1fd94e14d`
(2026-06-08) and still say "hermes". The root
`AOS_INSTALLATION_REPORT.md` had one longer shell comment (~261/177
figures) whose content the docs copy already carries in its header
note (lines 25-26). So **no overwrites were needed** — the docs
copies were kept as-is and the 9 stale root copies were `git rm`'d.

## Owned files (the ONLY files this task may write)

Moves (git mv / git rm):
- `RELEASE_v0.{2..14}.0.md` (13) → `docs/releases/`
- `AOS_*.md` (9, root) → removed (docs/aos-recovery/ canonical)
- `INTEGRATION_AUDIT.md`, `INTEGRATION_LOG.md`,
  `JARVIS_PRIME_SYNERGY_AUDIT.md`, `MERGE_STRATEGY.md`,
  `ECHERD27_TO_ACI_DEEP_DIVE_RECONCILIATION_REPORT.md`,
  `ACI_BASE44_IMPORT_HANDOFF.md` → `docs/audits/`

New:
- `docs/releases/README.md` (index)
- `docs/launch/followups/fu-d1-root-tidy.md` (this snapshot)

Link rewrites:
- `CLAUDE.md` (AOS report paths)
- `AGENTS.md` (recovery-artifacts paths)
- `SETUP.md` (ACI_BASE44_IMPORT_HANDOFF link)
- `docs/jarvis-prime-integration-demo-trace.md` (audit/log links)
- `docs/launch/LAUNCH_STATUS.md:80` (INTEGRATION_AUDIT live link)
- `scripts/contributor_audit.py` (docstring example)
- `skills/aos-enterprise-council/SKILL.md` (`../../AOS_*` refs)
- `skills/aos-enterprise-council/README.md` (root AOS refs)
- `docs/aos-recovery/README.md` (canonicality header inverted: this
  dir is now the source of truth, root copies removed)

Contract deviation (flagged for orchestrator review):
- `scripts/scan_secrets.py` — one-line robustness fix
  (`errors="replace"` on the `git diff` subprocess decode). Not in the
  original owned-files set, but unavoidable: origin/main's root
  `AOS_FULL_SOURCE_INVENTORY.md` contains a pre-existing truncated
  UTF-8 sequence (`\xe2\x80`, line 80 — an em-dash cut short), so any
  diff that deletes that file crashes the scanner with
  `UnicodeDecodeError`, failing both the mandated validation and the
  `secret-scan.yml` CI job on this PR. Replacement characters cannot
  form a credential and removed lines are never scanned, so detection
  behavior is unchanged. `tests/test_scan_secrets.py` (17 tests)
  passes. The ledger shows no other in-flight grain owning this file.
  Note: `docs/aos-recovery/AOS_FULL_SOURCE_INVENTORY.md` (byte-identical
  mirror, untouched here) carries the same corrupt byte — candidate for
  a follow-up one-byte repair.

## Plan (bounded steps)

1. `git mv` 13 release notes → `docs/releases/` + index README. ✓
2. Diff root vs docs AOS copies; keep newer (docs); `git rm` root 9. ✓
3. `git mv` 6 audit reports → `docs/audits/`. ✓
4. Rewrite all live inbound links; leave period-accurate history
   (`docs/launch/*` narratives, `docs/launch/followups/fu-18`/`wc-4`,
   `docs/aci/reports/R00_*`, `docs/audits/*` internal narrative,
   `docs/audits/hermes-file-inventory.md`, `.reconciliation/`). ✓
5. Verify MANIFEST.in unaffected (grafts only `skills` /
   `optional-skills` — no root .md files packaged). ✓

## Validation

- `uv run ruff check scripts/contributor_audit.py scripts/scan_secrets.py` → `All checks passed!` (exit 0)
- `uv run --extra dev python -m pytest tests/test_jarvis_prime_work_packet.py -q -o addopts=""` → `20 passed in 2.16s`
- `uv run --extra dev python -m pytest tests/test_scan_secrets.py -q -o addopts=""` → `17 passed in 0.89s`
- Zero-hit grep proof: markdown links / `../../`-style relative refs to
  the old root paths in non-historical files → 0 hits (grep exit 1)
- `python3 scripts/scan_secrets.py --base origin/main` → `ok: no
  high-confidence secrets in merge-base origin/main...HEAD` (exit 0;
  14 advisory high-entropy matches are path strings, non-blocking).
  Before the decode fix this command crashed with `UnicodeDecodeError`
  on the deleted root `AOS_FULL_SOURCE_INVENTORY.md` (see deviation
  note above).

## Residual / follow-on

- Period-accurate historical records intentionally still cite old root
  paths: `docs/launch/` narratives (LAUNCH_BRANCH_MATRIX,
  LAUNCH_READINESS_CHECKLIST, CI_WORKFLOW_REPAIR_REPORT, LAUNCH_STATUS
  bare-name mentions), `docs/launch/followups/fu-18-aos-honesty.md`,
  `wc-4-honesty-233-docs.md`, `docs/aci/reports/R00_*`,
  `docs/audits/hermes-file-inventory.md`, `.reconciliation/`. These
  narrate past states and were left as history by design.
- Release notes keep their original "Hermes Agent" branding — they are
  historical records of the upstream lineage and were not rebranded.
- External links (e.g. old GitHub URLs to root-level files) will 404 on
  the old paths; GitHub's fuzzy file finder mitigates. No redirect
  stubs per task contract.
