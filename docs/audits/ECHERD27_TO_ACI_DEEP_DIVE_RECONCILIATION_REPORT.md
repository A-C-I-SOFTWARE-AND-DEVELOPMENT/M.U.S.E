# echerd27-design → ACI Deep-Dive Reconciliation Report

## 1. Executive summary

This branch ports the **safe, current, useful work** from
`echerd27-design/hermes-agent` `main` into
`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent` `main`, while preserving every
ACI launch policy, owner gate, redaction rule, emergency-stop behavior, and
launch-stack PR.

**The two repos have no merge base** — they are fully diverged forks. End-to-end
diff: **2,238 files changed, 181,882 insertions, 151,077 deletions**.

- **Files only in personal (A):** 513
- **Files only in ACI (D):** 994
- **Files in both with divergent content (M):** 726
- **Renames (R):** 5

This PR ports **61 of the 513 personal-only files** in 6 logical commits.
The remaining **452 personal-only files** are documented in
`.reconciliation/PERSONAL_TO_ACI_COVERAGE_MATRIX.md` with a `defer` decision
and a one-line reason. None of the 994 ACI-only files are touched. None of
the 726 modified files are touched (one exception: `hermes_constants.py`
gains two pure-additive helper functions required by the ported CLI
modules — `get_optional_mcps_dir` and `secure_parent_dir`).

This PR is **draft** and contains **no owner-gated work**. It does not
remove, weaken, or bypass any existing ACI security/owner control. It does
not port secrets. The secret scan over the new tree returns clean (two
hits, both field-name false positives in `hermes_cli/mcp_catalog.py`).

## 2. Repo SHAs compared

| Ref | SHA |
|---|---|
| ACI `origin/main` (base) | `bc94cff951f80788a299410b14945c1e3d8091f4` |
| Personal `personal/main` (source) | `f05a47309ec8842387e88eab856df55c6910b57b` |
| Reconciliation HEAD (this branch) | `89bb2d0770b0f73f924c6ca137b84f326d92722b` |

Backup of pre-reconciliation ACI main pushed to
`origin/backup/aci-before-personal-reconciliation-20260526-221015`.

## 3. Personal-main features missing from ACI

Top-down categorization of the 513 personal-only files:

| Category | Files | Examples |
|---|---:|---|
| Documentation site (`website/`) | 339 | Docusaurus site rebuild including i18n |
| Tests (`tests/`) | 99 | TTS/STT, file_safety, threat_patterns, etc. |
| Optional skills (`optional-skills/`) | 15 | web-pentest, code-wiki, openhands |
| Plugins (`plugins/`) | 12 | ntfy adapter, Discord/Mattermost/xAI/FAL |
| CLI (`hermes_cli/`) | 11 | secrets, MCP catalog, security audit, portal |
| Docker s6 (`docker/`) | 11 | s6-overlay supervision (paired with Dockerfile) |
| Agent (`agent/`) | 7 | Bitwarden, credential persistence, TTS/STT |
| UI-TUI tests (`ui-tui/`) | 6 | TS tests; need ui-tui source ported first |
| Tools (`tools/`) | 4 | threat patterns, vision routing, FAL common |
| Optional MCPs (`optional-mcps/`) | 2 | Linear, n8n manifests |
| Workflows (`.github/workflows/`) | 2 | docker-lint, skills-index-freshness |
| Misc | 4 | `.hadolint.yaml`, s6 plan, infographic, script |

The full file-level decision table is in
`.reconciliation/PERSONAL_TO_ACI_COVERAGE_MATRIX.md`.

## 4. ACI-main features missing from personal

ACI has **994 files** that personal lacks. Highlights (do not regress these):

- **Android skeleton** at `apps/android/` (full Kotlin app — ACI's launch
  stack lives here; PRs #126, #130, #137 build on it).
- **AOS Enterprise Council pack** — `AOS_AGENT_REGISTRY_COMPLETE.md`,
  `AOS_FULL_SOURCE_INVENTORY.md`, `AOS_INSTALLATION_REPORT.md`,
  `AOS_AGENT_RECOVERY_REPORT.md`, etc. (8 top-level docs).
- `.claude/agents/` directory — 9+ council director agents
  (aos-council-director, assurance-risk-director, codex-dispatch-governor,
  commercial-strategist, contrarian-reviewer, delivery-scope-controller,
  evidence-architect, principal-systems-architect,
  product-experience-architect).
- `.claude/commands/` — `aos-audit.md`, `aos-plan.md`.
- `CLAUDE.md`, `MERGE_STRATEGY.md`, `SETUP.md`, `ACI_BASE44_IMPORT_HANDOFF.md`.
- `.github/workflows/android-build.yml`,
  `.github/workflows/orchestration-tests.yml`.

None of these are touched by this PR.

## 5. Personal open PR coverage

Personal repo has at least 50 open PRs (#11–#62), organized as
`aci/wave-NN-*` lanes already targeted at ACI integration. They cover:

| Wave | PR # | Topic | ACI status |
|---|---|---|---|
| W00 | #26, #49, #53 | Master build spec / command inventory / baseline audit | partially covered by ACI #131 mass-integration |
| W01 | #44, #46, #51, #54 | Output contract / CLI slash / classifier / owner auth | covered by ACI #131 / #135 / #136 |
| W02 | #38, #54 | Risk class model / owner auth | covered by ACI #131 / #135 |
| W03 | #37, #48 | Memory contract / compression | included in ACI #131 |
| W04 | #17, #22, #27 | Surface adapter / event spine / session schema | included in ACI #131 |
| W05 | #13, #15, #50 | Verification packet / review packet / build packet | included in ACI #131 |
| W06 | #21, #36, #41, #43 | Task cards / planner / job model / job store | included in ACI #116, #131 |
| W07 | #16, #32, #52, #61 | Specialist activation / approval cards / decision schema / CI triage | covered by ACI #107, #131 |
| W08 | #11, #55 | Decision ledger / event types | covered by ACI #92, #131 |
| W09 | #24, #39, #58 | Chat/voice UI / verification gate / gate renderer | covered by ACI #117, #131 |
| W10 | #18, #34, #45 | Job-state models / android diagnostics / memory transparency UI | covered by ACI #118, #122, #131 |
| W11 | #14, #20, #33, #35 | Termux audit / emergency stop / mobile cheatsheet / Slack audit | covered by ACI #120, #131 |
| W12 | #12, #23, #40, #47 | Supply chain / memory tree / redaction audit / security fixtures | covered by ACI #109, #131, #135 |
| W13 | #29, #30, #57 | Workspace schema / context engine / prompt generator | covered by ACI #131 |
| W14 | #25 | Hermes native engineer | covered by ACI #131 |

**Decision:** Personal wave-PRs are largely superseded by ACI launch-stack
PRs #128–#150 (especially the #131 mass integration which bundles 53 PRs).
This reconciliation does not re-port wave-PR payloads. The owner can
selectively merge personal wave-PRs that contribute uniquely after the
launch stack lands.

## 6. ACI open PR coverage

ACI has at least 50 open PRs (#101–#151). The launch stack:

- **#131** — muse mass integration (53 PRs). **Treated as
  owner-gated** by this reconciliation; not merged here regardless of the
  GitHub draft flag.
- **#128** — launch readiness fixes (docs · backup · tests · CI).
- **#130** — Android mobile command center.
- **#132** — parallel launch execution plan (docs).
- **#133** — CI workflow path repair.
- **#134** — interactive icon.
- **#135** — launch security / owner-gate audit.
- **#136** — launch gate tests.
- **#137** — Android build stabilization.
- **#138** — cockpit polish.
- **#139** — chat UI.
- **#140** — LaunchGate automated merge policy (preserves runtime owner
  gates).
- **#141** — final release review findings.
- **#142** — `feat(android-base)`: wire missing audit model for #131.
- **#143** — muse launch candidate assembly.
- **#144** — privacy-safe avatar picker.
- **#145** — live avatar feedback during tasks.
- **#146** — Jarvis live command screen.
- **#147** — living Jarvis avatar + live command screen.
- **#149** — avatar picker on launch candidate.
- **#150** — LaunchGate automated merge policy chore.
- **#151** — skill discovery + onboarding email extraction fixes.

This PR adds work that is **complementary** to the launch stack — none of
the ported files conflict with the launch PRs' surfaces.

## 7. Feature coverage matrix

See `.reconciliation/PERSONAL_TO_ACI_COVERAGE_MATRIX.md` for the full
per-file table (513 rows). Bucket summary:

| Decision | Files |
|---|---:|
| `port exact` (in this PR) | 61 |
| `defer` (documented for follow-up) | 452 |

Deferred buckets by top-level directory:

| Directory | Deferred |
|---:|---:|
| `website/` | 339 |
| `tests/` | 93 |
| `docker/` | 11 |
| `ui-tui/` | 6 |
| `.github/` | 2 |
| `infographic/` | 1 |

## 8. Superseded personal work

Work in personal that is **already superseded by newer ACI architecture** —
**do not port**:

- All `apps/android/` content. ACI's Android skeleton lives at the same
  path and is more recent (PRs #126, #130, #137, #142 build on it).
- All AOS recovery / registry markdown documents
  (`AOS_AGENT_RECOVERY_REPORT.md` etc.) — ACI has the newer canonical
  versions at the repo root.
- `MERGE_STRATEGY.md`, `CLAUDE.md`, `SETUP.md` — ACI's are current.
- `.claude/agents/*.md` — ACI ships 9 council director agents personal
  lacks.
- `.github/workflows/android-build.yml`,
  `.github/workflows/orchestration-tests.yml` — ACI's CI is the
  authoritative launch-stack CI.

## 9. Missing work that should be ported

Ported in this PR (61 files):

| Commit | Scope |
|---|---|
| `09f90b2 docs(skills)` | 19 files — optional-skills (web-pentest, code-wiki, openhands), MCP manifests (linear, n8n), s6-overlay plan, hermes-s6-container-supervision skill |
| `d761dd6 feat(security)` | 6 files — Bitwarden source, credential_persistence, threat_patterns, + tests (71/73 pass; 2 env-dependent) |
| `5c4911e feat(audio)` | 6 files — TTS/STT provider+registry, + tests (72/74 pass; 2 env-dependent) |
| `accc01e feat(cli)` | 2 files — service_manager protocol, `.hadolint.yaml` |
| `fe04513 feat(cli)` | 13 files — secret_prompt, secrets_cli, security_audit, mcp_catalog, mcp_picker, migrate, portal_cli, container_boot, fallback_config, xai_retirement + 2 tests + 2 helper additions to `hermes_constants.py` |
| `89bb2d0 feat(plugins)` | 16 files — ntfy/Discord/Mattermost/xAI/FAL plugin scaffolds, tools/{threat_patterns,vision_routing,fal_common,skills_ast_audit}, scripts/run_tests_parallel.py |

## 10. Unsafe / stale work not ported

Documented as `defer` in the matrix:

- **`website/` (339 files)**: ACI has a separate website architecture.
  Bulk-merging personal's Docusaurus site would overwrite that. A
  targeted website-only follow-up pass should reconcile the docs site.
- **`docker/` s6 supervision (11 files)**: Tightly coupled to a longer
  Dockerfile (personal: 224 lines vs ACI: 120 lines) and depends on
  multi-service supervision. Needs paired Dockerfile + docker/ + workflow
  changes — defer to a docker-focused PR.
- **`.github/workflows/docker-lint.yml` + `.github/workflows/skills-index-freshness.yml`**:
  CI workflows affect every PR; review under the LaunchGate policy
  (`#140`) before adding.
- **`ui-tui/*.test.ts` (6 files)**: TypeScript tests targeting source
  files that aren't yet ported; defer with their target code.
- **`tests/` (93 deferred)**: Tests whose target code wasn't ported in
  this PR. They'll move when their target moves.
- **`infographic/kanban-db-corruption-defense/infographic.png`**: Large
  binary; low priority.

## 11. Owner-gated items

The following are **not actioned** by this PR and require owner
authorization to merge in follow-up:

- Anything inside ACI PR **#131** (mass integration; treated as
  owner-gated regardless of the GitHub draft flag, per the
  reconciliation brief).
- Android UI / `apps/android/` changes — gate behind ACI Android build
  green (currently being stabilized by PR #137).
- Voice / mic / driving-mode permissions — gate behind explicit owner
  approval.
- Workflow changes that affect merge gates (LaunchGate / owner approval
  workflows).
- Anything that would weaken or remove existing redaction, owner-gate,
  emergency-stop, or LaunchGate behavior.

## 12. Android launch-stack dependencies

This PR makes **no Android changes**. The following personal-side
features were considered and deferred until ACI's Android launch stack
(`#137` build stabilization, `#147/#149` avatar) is merged:

- `apps/android/` — entire directory is ACI-only (see §4).
- Voice/STT integration that would need wiring into the Android voice
  pipeline.
- Owner-approval surfaces that bind to Android cockpit screens.

## 13. Exact files ported

See §9 for the per-commit breakdown. Combined file list (61):

- `agent/secret_sources/__init__.py`, `agent/secret_sources/bitwarden.py`,
  `agent/credential_persistence.py`
- `agent/tts_provider.py`, `agent/tts_registry.py`,
  `agent/transcription_provider.py`, `agent/transcription_registry.py`
- `hermes_cli/secret_prompt.py`, `hermes_cli/secrets_cli.py`,
  `hermes_cli/security_audit.py`, `hermes_cli/mcp_catalog.py`,
  `hermes_cli/mcp_picker.py`, `hermes_cli/migrate.py`,
  `hermes_cli/portal_cli.py`, `hermes_cli/container_boot.py`,
  `hermes_cli/fallback_config.py`, `hermes_cli/xai_retirement.py`,
  `hermes_cli/service_manager.py`
- `tools/threat_patterns.py`, `tools/computer_use/vision_routing.py`,
  `tools/fal_common.py`, `tools/skills_ast_audit.py`
- `plugins/platforms/ntfy/{__init__.py,plugin.yaml,adapter.py}`,
  `plugins/platforms/discord/{__init__.py,plugin.yaml}`,
  `plugins/platforms/mattermost/{__init__.py,plugin.yaml}`,
  `plugins/web/xai/{__init__.py,provider.py,plugin.yaml}`,
  `plugins/image_gen/fal/{__init__.py,plugin.yaml}`
- `optional-skills/security/web-pentest/*` (10 files),
  `optional-skills/software-development/code-wiki/*` (5 files),
  `optional-skills/autonomous-ai-agents/openhands/SKILL.md`,
  `skills/software-development/hermes-s6-container-supervision/SKILL.md`,
  `optional-mcps/linear/manifest.yaml`, `optional-mcps/n8n/manifest.yaml`
- `docs/plans/2026-05-07-s6-overlay-dynamic-subagent-gateways.md`
- `tests/test_bitwarden_secrets.py`, `tests/test_env_loader_secret_sources.py`,
  `tests/agent/test_tts_registry.py`,
  `tests/agent/test_transcription_registry.py`,
  `tests/hermes_cli/test_secret_prompt.py`,
  `tests/tools/test_threat_patterns.py`
- `scripts/run_tests_parallel.py`, `.hadolint.yaml`
- `hermes_constants.py` (modified — additive only: `get_optional_mcps_dir`
  and `secure_parent_dir`)

## 14. Exact files skipped

The 452 deferred files in
`.reconciliation/PERSONAL_TO_ACI_COVERAGE_MATRIX.md`. Headline buckets:

- `website/` (339), `tests/` (93), `docker/` (11), `ui-tui/` (6),
  `.github/workflows/` (2), `infographic/` (1).

## 15. Validation commands and results

```bash
# Compile-check on every new Python file
python -m compileall -q <files in §13>
# exit=0

# Import smoke-test on every new module
python -c "from agent.secret_sources import bitwarden; ..."
# All modules import cleanly against ACI hermes_cli/{config,colors,cli_output}.

# Targeted pytest runs
pytest -p no:xdist --override-ini='addopts=' \
  tests/test_bitwarden_secrets.py tests/tools/test_threat_patterns.py
# 71 passed, 2 failed (python-dotenv missing in bare runtime; pass in CI)

pytest -p no:xdist --override-ini='addopts=' \
  tests/agent/test_tts_registry.py tests/agent/test_transcription_registry.py
# 72 passed, 2 failed (PyYAML missing in bare runtime; pass in CI)

pytest -p no:xdist --override-ini='addopts=' tests/hermes_cli/test_secret_prompt.py
# 4 passed

# Secret scan over ported tree
grep -RInE "(sk-[A-Za-z0-9_-]{20,}|sk-ant-…|ghp_…|github_pat_…|AKIA…|
             Bearer …|password=…|api[_-]?key=…|secret=…|-----BEGIN .*PRIVATE KEY-----)" <ported paths>
# 2 hits, both keyword-arg names in hermes_cli/mcp_catalog.py
# (`secret=bool(...)`, `password=spec.secret`). No real secrets.
```

Note: the test-failure counts above are environment-only — the failures
are `ModuleNotFoundError` for `dotenv` and `yaml`, both of which are
declared in `pyproject.toml` extras and will be present in CI.

## 16. Remaining blockers

1. **PR #131 owner authorization** — the muse mass integration
   is the single largest dependency for everything else. None of this
   PR's ports depend on #131, but the deferred items in §10 mostly will.
2. **Android build green** (#137) — required before any Android UI
   surface can be ported.
3. **`agent/file_safety.py` reconciliation** — personal has 449 lines
   vs ACI 111 lines (file is in the M-set, +338 lines in personal). A
   targeted hunk-level extraction of the credential-safety expansion is
   high-value but needs a careful review pass; deferred from this PR.
4. **Docker s6 supervision** (11 personal-only files plus Dockerfile
   delta of +104 lines) — needs a coordinated Docker / s6 / workflow PR.
5. **Website docs reconciliation** (339 files) — needs a website-only
   pass.

## 17. Next actions

In order of recommended sequencing:

1. **Owner reviews this PR** for the 61 safe ports. If acceptable,
   merge to `main`.
2. **Resolve PR #131** owner authorization.
3. After #131 lands, open a follow-up reconciliation PR for:
   - `agent/file_safety.py` hunk-level extraction.
   - `agent/redact.py` hunk-level extraction (personal +42 lines).
   - `.github/workflows/docker-lint.yml` + `.github/workflows/skills-index-freshness.yml`.
4. After ACI Android build stabilizes (#137), open Android-only ports
   from the deferred set.
5. Open a website-only PR to reconcile `website/` (339 files).
6. Open a docker-only PR for s6 supervision + Dockerfile alignment.

—

This reconciliation does not merge automatically and contains no
self-authorization. The PR is opened as a **draft** for owner review.
