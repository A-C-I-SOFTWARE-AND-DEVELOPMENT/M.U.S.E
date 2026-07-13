# Fabrication, Game, and Cinema Production Verification

**Date:** 2026-07-12

**Scope:** Production backend briefs 1-8

**Verification mode:** Static inspection only, by owner instruction

## Result

The production backend contracts are implemented in the approved write scope. Runtime evidence is intentionally not claimed: tests, lint, type checking, builds, quality gates, servers, Unreal, browser activity, and acceptance-artifact generation were explicitly prohibited for this pass.

The implementation fails closed when an engine, parser, provider, approval, gate result, eye render, rights record, or rollback source is unavailable. Private previews cannot authorize production promotion, and uncompiled source packages are never marked playable.

## Brief coverage

| Brief | Static evidence | Runtime status |
|---|---|---|
| 1. Engine discovery | Cross-platform UE 5 discovery requires a build tool and editor; UE 5.6 is preferred; empty/partial installs return `None`; UE/Godot/Unity scaffolds write UTF-8 and remain uncompiled | Not executed |
| 2. Provenance and asset gates | Immutable provenance, SHA-256 binding, rights/safety checks, fail-closed parser behavior, topology/budget validation, bundle evidence files, blocked items, and rollback source | Not executed |
| 3. Workspaces and previews | Git-worktree local leases, external provider adapters, owner approval, lifecycle persistence, checkpoint/sleep/resume/destroy, HMAC-SHA256 path/origin/expiry claims | Not executed |
| 4. Source mapping and fabrication | Revision-bound source refs, workspace and secret-path bounds, deterministic direct edits, unified diffs, command evidence, required gates, checkpointed Apply, rollback, and separately approved release staging | Not executed |
| 5. Game Foundry | Complete production-lane manifest, open-world blueprint seed marked as planned, source projects, declared command logs/exit codes/hashes, and package/smoke-controlled `playable` | Not executed |
| 6. Cinema and render QC | Metric two-camera stereo, depth/composition policies, deterministic left/right records and retry semantics, QC gates, OpenEXR/ACES/audio/editorial/archive packaging, checksums, external IMAX gate | Not executed |
| 7. Releases and rollback | Versioned release states, complete product/security/rights gates, owner approval, durable deployment evidence, previous-public preservation, provider rollback, and recovery instructions | Not executed |
| 8. Checkpoint | Scoped source/test/audit review plus `git diff --check`; prohibited runtime commands are recorded below | Static only |

## Security and truthfulness invariants

- Provenance public records contain a prompt reference, not raw prompt text.
- Unknown asset formats or missing parsers produce `unverified_parser_missing` and block publication.
- Preview claims are private, short-lived, HMAC-signed, path-bound, origin-bound, and explicitly ineligible for production.
- Workspace and source paths are resolved beneath their approved roots; destructive workspace cleanup rechecks that bound.
- Command execution uses argument vectors with `shell=False` semantics through `subprocess.run` defaults.
- Provider tokens and secrets are not serialized in workspace, fabrication, or release evidence.
- Release promotion requires passed verification, provenance, rights, security, performance, and accessibility gates plus a rollback source and owner approval.
- Failed publication does not replace the current public release and is recorded with `partial_success=false`.
- A cinema master requires two synchronized physical-camera eyes, passing stereo QC, existing OpenEXR outputs, and passed rights evidence.
- `imax_certified` remains `false`; certification is an external gate.

## Spec-test inventory

Static contract tests cover:

- engine preference, complete-install requirements, and honest absence;
- provenance hashes, licenses, allowed uses, parser absence, budgets, and rig compatibility;
- isolated leases, checkpoints, lifecycle states, signed preview boundaries, and unavailable providers;
- source revision/path/property bounds, workspace-only edits, diff evidence, failed gates, Apply checkpoints, and rollback;
- complete Game Foundry lanes and the package/smoke definition of playable;
- physical stereo cameras, misalignment/composition failures, deterministic retries, missing-eye rejection, and cinema package contents;
- private preview separation, release gate rejection, failed-publish preservation, and rollback to a prior durable release.

## Verification commands

The following commands from the production briefs were **not run**:

- Python Studio and universe test suites;
- Desktop tests, type checking, and build;
- MUSE checkpoint quality gate;
- Unreal, Godot, Unity, render, provider, server, and browser commands;
- local acceptance-artifact generation.

`git diff --check` was run as permitted. The final repository-wide invocation returned non-zero for one unrelated pre-existing edit outside this stream:

- `apps/synapse-ue/README.md:64` — blank line at end of file.

Those files are outside the exclusive write scope and were not changed. The scoped tracked-file `git diff --check` completed without whitespace errors; Git emitted only line-ending conversion warnings. New-file no-index checks are recorded in the production stream report.

## Acceptance and external gates

No fabricated acceptance hashes, provider availability, build success, package success, or certification result is recorded. At runtime, the implementation writes SHA-256 inventories, command stdout/stderr and exit codes, engine availability, provider deployment IDs/URLs/costs, stereo QC, and rollback evidence. Until those runtime records exist, the corresponding status remains unverified, unavailable, unbuilt, blocked, or externally required.

`service.py` and the desktop UI were intentionally untouched. The new backend modules expose standalone contracts for later service wiring without violating this stream's ownership boundary.
