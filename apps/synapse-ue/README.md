# SYNAPSE — UE 5.6 scaffold (Prompt 0, STAGED)

This is the **Prompt 0 scaffold** from the SYNAPSE master plan
(`docs/plans/2026-06-10-project-synapse-master-plan.md` §13): the UE 5.6
C++ project skeleton with modules `SynapseCore` and `SynapseNet`
(`UMuseGatewayClient` + `UMuseSseClient`) over the frozen cockpit wire
contract (`docs/contracts/cockpit-wire-contract.md`).

**Why it lives here:** the standalone `SYNAPSE` GitHub repo could not be
created from the build session (403, out of scope for the session's
credentials), so the scaffold is **staged** at `apps/synapse-ue/` in the
M.U.S.E monorepo — **source-only, zero binary assets** — designed for
verbatim copy into the future SYNAPSE repo. Per the master plan §5, UE
binary assets do **not** belong in this monorepo; nothing binary is here.

## Layout

```
Synapse.uproject                  UE 5.6, modules SynapseCore + SynapseNet
Source/Synapse(.Editor).Target.cs Game + Editor targets
Source/SynapseCore/               Foundation module (log category, boilerplate)
Source/SynapseNet/                Gateway client: settings, HTTP subsystem, SSE
Config/                           Minimal DefaultEngine/DefaultGame ini
Content/.gitkeep                  Empty by policy — see file comment
docs/synapsenet.md                Module doc: threading, token, SSE, backoff
docs/testmap-setup.md             6-step in-editor BP test map instructions
tools/stub_gateway.py             Prompt 0 fallback stub (validated here)
.github/workflows/build-win64.yml CI for the FUTURE repo — inert here
.gitattributes / .gitignore       LFS rules + standard UE ignores
```

## Migration to the standalone SYNAPSE repo

1. **Copy the tree verbatim** — `apps/synapse-ue/` contents become the new
   repo **root** (so `Synapse.uproject` sits at root).
2. `git init` (private repo `SYNAPSE` under the org), `git lfs install`.
3. The shipped `.gitattributes` LFS rules are already in place — commit it
   **first** so every future binary asset is LFS-tracked from commit one.
4. Commit the rest; push.
5. `.github/workflows/build-win64.yml` is **intentionally inert here**
   (GitHub only runs workflows from a repo root's `.github/workflows/`);
   at the new repo root it goes live automatically. Register a
   self-hosted Windows runner with UE 5.6 + VS2022 (labels
   `[self-hosted, Windows, UE5_6]`) before expecting green.
6. Add `synapse/contract.lock` (wire-contract version pin, TDD §7) when
   the first contract-consuming feature lands.

## Validation status (honest, per the no-evidence-no-claim rule)

| What | Status |
|---|---|
| Python stub gateway: `/health` + `/v1/health` 200, capabilities 401-without/200-with bearer (real contract field names), SSE heartbeats | **VALIDATED in this container** — Prompt 0's documented fallback path; transcript in the delivery report |
| UBT compile (`SynapseEditor Win64 Development`, warnings-as-errors) | **NOT RUN HERE** — UE 5.6/UnrealBuildTool are not installed in this container. This is the documented **OWNER-BLOCKER**, not a failure. Compiling is the **first action on the owner's machine** |
| PIE test map printing `/v1/health` + capabilities | Deferred to the owner per `docs/testmap-setup.md` |

> **OWNER-BLOCKER (per Prompt 0):** pairing + compile needed. The scaffold
> cannot be proven end-to-end until (a) UBT compiles it on a machine with
> UE 5.6 + VS2022 and (b) a gateway is paired (or the stub is run) so the
> PIE handshake log can be captured. No output, no done — the Phase 0 exit
> gate stays open until those logs exist.

### First actions on the Legion

```bat
:: 1) Compile (iterate until clean; warnings-as-errors is on for Synapse* modules)
"C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\Build.bat" SynapseEditor Win64 Development -Project=<path>\Synapse.uproject -WaitMutex

:: 2) Automation smoke (headless; suites land with Phase 1, runs clean-empty today)
"C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" <path>\Synapse.uproject -ExecCmds="Automation RunTests Synapse.; Quit" -TestExit="Automation Test Queue Empty" -unattended -nopause -nullrhi -log
```

Then run the stub (`python tools\stub_gateway.py`), write the token to
`Saved\muse_token.txt` (default dev token `synapse-dev-token`, or set
`STUB_TOKEN`), and follow `docs/testmap-setup.md` to capture the PIE
handshake logs that close the gate.

## Module docs

- `docs/synapsenet.md` — architecture, threading rules, token security,
  SSE framing, backoff policy, validation matrix.
- Design authority: `docs/synapse/design/11-technical-design.md` (M.U.S.E
  repo) — module spec §2; master plan §5 stack table.
