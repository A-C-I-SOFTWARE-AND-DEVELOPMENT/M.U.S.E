# M.U.S.E Device Consolidation Audit

## Outcome

The canonical workspace is `C:\Users\Echer\.hermes\M.U.S.E`. It was fast-forwarded from `d5a564f3d` to the newest verified local commit, `2ff498bf9`, then placed on `codex/muse-atlas-universe-consolidation`. No tracked user edit was overwritten.

The approved duplicate cleanup is complete. All listed duplicate repositories, old worktrees, updater clones, extracted source archives, duplicate reports, cockpit copies, and stale M.U.S.E-specific temp workspaces were removed after recovery checks. Free space rose from 34,603,212,800 bytes to approximately 105.1 billion bytes at final verification, an observed gain of about **65.7 GiB**. The exact free-byte reading fluctuates as Windows and OneDrive perform background work.

The scan covered user-profile repositories, Git worktrees, OneDrive project folders, Downloads, Temp updater remnants, installed runtimes, desktop installations, WSL, standalone archives, PDFs, Word documents, source snapshots, promotional assets, voice/n8n prototypes, and supporting Unreal/MuseTalk projects.

## Canonical and protected state

Do not delete these as duplicate source:

| Path | Reason |
| --- | --- |
| `C:\Users\Echer\.hermes\M.U.S.E` | Canonical development workspace |
| `C:\Users\Echer\AppData\Local\hermes\hermes-agent` | Active installed runtime; first `muse` on PATH and used by the gateway task |
| `C:\Users\Echer\AppData\Local\hermes\gateway-service` | Active scheduled gateway service |
| `C:\Users\Echer\AppData\Local\muse` | Desktop executable targeted by the current shortcut |
| `C:\Users\Echer\AppData\Local\com.aci.muse` | Desktop WebView/user state |
| `C:\Users\Echer\AppData\Local\hermes\backup-pre-018-20260710-171029` | Stateful config/database/skills backup, not a source duplicate |
| `C:\aria-ml\MuseTalk` | Separate lip-sync dependency candidate for Cinema Stage |
| `C:\Users\Echer\Desktop\projects\unreal-mcp` | Separate live Unreal-control dependency candidate |
| WSL `/root/NemoClaw` | Separate active project with Hermes integration |

The n8n secret file remains outside Git. Its variable names were inventoried, but values were never printed or copied. It may be removed only after secrets are deliberately migrated or rotated.

## Material absorbed into active locations

- Newest Desktop/Omni/Fusion/Fleet source history through `2ff498bf9`.
- Static Atlas, Observatory, Studio, legacy cockpit, PWA icons, and vendored browser runtime under `web/public/`.
- Unified dashboard build staging script under `scripts/deploy/`.
- Local Supabase development configuration under `supabase/`; all sensitive values are environment references.
- Clean-room Mustang-inspired PBR demonstration asset under `demo_assets/1960s_mustang/`.
- Historical M.U.S.E marketing set under `assets/marketing/muse-2026-legacy/` with a new provenance warning.
- 2026 desktop product benchmark under `docs/research/`.
- 337 unique or locally modified source/evidence files under `recovered-agent-sources/device-consolidation-2026-07-12/`, plus its manifest.

## Material intentionally archived, not activated

- The recovered cinematic studio is feature-rich but uses an independent Next.js/Prisma stack and unconstrained dependency ranges. Its domain flows will be mined into the existing Studio/Omni architecture.
- The Android avatar/action overlay predates the current Android service layout. Its authority model and animation states are useful; its manifest and service code are not drop-in replacements.
- The capability/conversation package is coherent but untested in the current runtime. It is a candidate for a test-first integration.
- The UE5.7 scaffold is unverified and contains template defects; the current device/repo targets UE5.6 in other places. It is evidence, not production code.
- The voice prototype's frontend is useful, while its full-tool `--yolo` proxy and broad CORS are incompatible with the current least-privilege architecture.
- The old delegate working-tree edit has the right empty-toolset intent but an empty `elif` body. It is preserved only to recover the requirement.
- A unique static OpenClaw Omni preview and two hardware-tuning scripts were archived as evidence. They are not active implementations.
- A 700 MB cache of voxel scene iterations and a Minecraft-named resource archive were visually audited, then rejected for production and redistribution. Clean-room environment and traversal lessons are recorded without retaining the third-party assets.

## Recovered audit and document findings

### Code audit PDF

Two 636,798-byte PDFs were byte-identical (`SHA-256 139BDA0736943EA803367137E83B683D74F9DB38BADB417A9F354FE9B9359194`). The 48-page report audited commit `d524a5777`, 30 commits behind the selected baseline, and did not run the full test suites. Its 149 findings are leads requiring current-code reproduction.

High-value checks retained:

- fail-closed transport/authentication and Android backup/cleartext controls;
- no silent-success paths in CI, plugin auth, render jobs, or prebuild scripts;
- per-attempt API telemetry and complete turn lifecycle evidence;
- deterministic lease creation and timezone-aware scheduling;
- URL-scheme validation before terminal hyperlink rendering;
- actionable error, offline, retry, rollback, and degraded states in every UI;
- dependency bounds, pinned CI actions, checksums, and truthful release gates.

### Rebrand report

The 19-page Word report recommends one public identity over compatibility-preserving internals. The obsolete recommendation was to make “Jarvis” public. The applicable architectural rule is retained without reviving that brand: M.U.S.E is the public identity; `hermes_*`, `HERMES_HOME`, package IDs, service names, and compatibility shims remain until a tested migration proves a rename worthwhile. Public narrative, pathways, evidence, owner gates, and rollback should be coherent and visible.

### Research and blueprints

The recovered MUSE research memo supports selective causal memory, verifier-backed skills, ephemeral specialists, bounded context packets, and a practical 2D operational layer paired with an optional cinematic software galaxy. The engineering blueprint reinforces component registries, repository cartography, evidence gates, replayable orchestration, and remote-worker contracts. These principles are reflected in the approved Atlas Crown specification.

## Code fixes queued for test-first porting

The Codex working-tree overlay contains current-value fixes absent from `2ff498bf9`:

1. Native Windows ACP file-URI handling and deterministic line-ending normalization.
2. Consistent `HOME` handling in sensitive-path and LSP workspace resolution.
3. Windows shell-hook parsing, Git Bash routing, and one retry for `STATUS_DLL_INIT_FAILED`.
4. Best-effort log rollover when another Windows process holds the file.
5. Bounded canonicalization cache for replayed tool-call JSON.
6. One `post_api_request` event for successful, invalid, interrupted, and exception outcomes with per-attempt latency.
7. Observer-only `post_turn` lifecycle hook.
8. Explicit empty child toolsets meaning “no tools,” without MCP inheritance.

These are not applied as old patches. Each receives a current-code failing test, root-cause check, minimal implementation, and focused regression run.

## Deletion manifest

Deletion is allowed only after the recovery tree and active copies pass hash/secret checks and the active `muse` command and scheduled gateway still resolve to protected paths.

| Candidate | Approx. size | Basis |
| --- | ---: | --- |
| `C:\Users\Echer\M.U.S.E` and linked `M.U.S.E-feat-keys` | 8.19 GiB | Newest history fast-forwarded; linked branch is behind; local-only work recovered |
| `C:\Users\Echer\OneDrive\Desktop\projects\M.U.S.E` | 11.72 GiB | Commit is 30 behind; all untracked source/assets and tracked working overlay recovered |
| Codex 2026-05-26 workspace and worktrees | 3.89 GiB | Old ancestors; modified files and tests recovered |
| `C:\Users\Echer\hermes-agent` | 1.44 GiB | Old ancestor; design sync and broken local edit recovered |
| `C:\Users\Echer\OneDrive\Desktop\projects\hermes-agent` | 0.61 GiB | Private old branch; untracked packages/docs and working overlay recovered |
| `C:\Users\Echer\repos\hermes-agent` | 0.25 GiB | Unique commit behavior is already present/superseded in active history |
| Antigravity and Google AI Studio clones | 0.45 GiB | Clean old ancestors |
| `AppData\Local\hermes\M.U.S.E` | 0.62 GiB | Old fallback install; not the active scheduled runtime |
| Temp updater/full-clone remnants | about 0.8 GiB | Disposable downloads, partial clones, and exact latest temporary clone |
| Full-source archives and duplicate report files | about 0.11 GiB | Fingerprinted and extracted or summarized |
| Root cockpit text/HTML duplicates | 0.001 GiB | Byte-identical to centralized static Atlas/Studio files |
| `AppData\Local\M.U.S.E` | 0.006 GiB | Duplicate desktop executable directory; shortcut targets lowercase `muse` |

The initial projection was roughly 28 GiB. The observed gain was about 65.7 GiB because hydrated OneDrive allocation and generated dependency/build trees occupied substantially more local disk than their logical source estimates. The active runtime, live desktop state, backups, external dependencies, and credentials remain excluded.

Every candidate in the table is now absent. The stale checkout that initially retained an empty directory handle was traced to an orphaned `muse cockpit serve --port 8765` process tree; only that non-listening tree was stopped. The active cockpit listener on port 8765 remained running.

## Verification performed

1. The 337 recovered source/evidence files plus manifest were scanned with no credential-pattern hits.
2. Copied source, visual, document, archive, and representative binary hashes matched; intentional fake-token redactions were documented.
3. `git fsck --no-dangling --no-reflogs` passed and both recovered private refs resolve.
4. `Get-Command muse` resolves to `C:\Users\Echer\AppData\Local\hermes\hermes-agent\venv\Scripts\muse.exe`.
5. The `Hermes_Gateway` scheduled task still executes `C:\Users\Echer\AppData\Local\hermes\gateway-service\Hermes_Gateway.cmd`.
6. All protected runtime, desktop-state, backup, MuseTalk, and Unreal-control paths exist.
7. Static JavaScript syntax, JSON parsing, and Git whitespace checks passed after the corrected asset-manifest path was used.
8. Every recursive deletion used an exact absolute allowlist, canonical-workspace collision check, and native PowerShell removal.
9. A post-delete scan found no remaining M.U.S.E source archive outside the canonical/protected locations.

Two tiny integration prototypes remain intentionally protected rather than silently destroyed: `C:\Users\Echer\muse-n8n` retains a local secret file pending deliberate credential migration or rotation, and `C:\Users\Echer\Desktop\projects\muse-voice` remains until its shortcut and safe voice path are repointed into the active product. Their non-secret source has already been recovered.
