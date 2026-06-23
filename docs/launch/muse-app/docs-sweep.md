# Docs sweep — `hermes`→`muse` / "Hermes Agent"→"muse" (user-facing docs)

**Task:** Finish the rebrand in user-facing documentation only. No code, no
PR, no merge.

- **Branch:** `claude/muse-docs-sweep` (built on local worktree branch
  `worktree-agent-ae66476d36204e19c`, pushed to remote
  `claude/muse-docs-sweep`).
- **Base commit:** `9f4f932bc74b4aecd3800aaeeba73a7853ffee5b` (origin/main).
- **Files changed:** 457 (327 under `website/docs/`, 128 under `docs/`
  excluding `docs/launch/`, plus `README.md` and `README.zh-CN.md`).
  5369 insertions / 5369 deletions — pure 1:1 line edits, no structural
  changes.
- **Build:** `cd website && npm ci && npm run build` → **exit 0
  (SUCCESS)**. Generated `build/`, `build/ko/`, `build/zh-Hans/`.

## What was changed

1. **Command invocations users type** — `hermes <subcommand|flag>` →
   `muse <subcommand|flag>`, applied via an allowlist-anchored sed across
   all owned files (~298 files touched by this pass). Covers every real and
   proposed CLI subcommand (`muse doctor`, `muse jarvis launch`,
   `muse cockpit serve`, `muse orchestrate`, `muse gateway`, `muse send`,
   `muse watch`, `muse plan branch`, …), the global flags (`muse --tui`,
   `muse -z`, `muse -p`, …), the entrypoint usage syntax
   (`muse [global-options] <command>`), and the bare `hermes` REPL prompt
   (converted per-file with judgment, ~30 hand-checked occurrences in
   getting-started / guides / user-guide / orchestration / README.zh-CN).

2. **Product name** — `"Hermes Agent"` → `"muse"` across the safe
   user-facing set (174 files), and standalone product `"Hermes"` →
   `"muse"` in clearly-product prose/headings via a **line-aware**
   replacer (412 files) that only fires on a prose boundary (never before
   `-` or `/`, so every `Hermes-foo` / `Hermes/foo` compound is left
   intact) and skips any line carrying a substrate/heritage/identifier
   signal.

## Preserve-decisions (left as `hermes`/"Hermes" on purpose)

Verified by count-equality against base (every count below is identical
pre/post):

- **Substrate / heritage (model + lab):** `Nous Hermes`, `Hermes-4`/`Hermes 4`
  (incl. `Hermes-4-70B` etc.), `Hermes-3`, `Hermes models`, `Hermes base`,
  `Hermes agent base`, `Hermes baseline`, "the lab behind Hermes, Nomos, and
  Psyche", `Hermes/Grok` (uncensored-model note), `Nous Research`. muse is
  *built on* the Hermes base — that honesty framing stays.
- **Filesystem / infra / env:** `~/.hermes`, `$HERMES_HOME`, `HERMES_*`
  (incl. `HERMES_TUI`, `HERMES_KANBAN_BOARD`), the `hermes` data dir
  (`%LOCALAPPDATA%\hermes\git`).
- **Packaging / identifiers:** dist name `hermes-agent`, modules
  `hermes_cli` / `hermes_bootstrap` / `run_agent`, the `hermes-acp`
  toolset/binary, `hermes-setup` auth id, `hermes-gateway.service` /
  `hermes.service`, the `hermes.exe` Windows artifact name, repo/clone paths
  `hermes-agent`, doc filenames/slugs containing `hermes-` (e.g.
  `use-mcp-with-hermes`, `build-a-hermes-plugin`), the
  `~/.hermes/hermes-agent/hermes` bootstrap-file path.
- **HTTP headers / config values (API contract):** `X-Hermes-Session-Id`,
  `X-Hermes-Session-Key`, `X-Hermes-Session-Token`; the
  `Hermes-Meeting-Pipeline-Policy` Azure policy name; the `Hermes-Monitor/1.0`
  User-Agent string; the `hermes:cockpit` Android wakelock tag; the `#hermes`
  example Slack channel name.
- **Literal default strings that mirror code** (reverted after the blanket
  pass): the built-in default identity `"You are Hermes Agent, an
  intelligent AI assistant created by Nous Research..."`
  (`website/docs/user-guide/features/personality.md`,
  `developer-guide/prompt-assembly.md`), and the `retain_context` default
  `conversation between Hermes Agent and the User`
  (`features/memory-providers.md`).
- **OS account / group named "hermes":** the `hermes` systemd service
  user and `hermes` group in the Nix/install docs
  (`getting-started/nix-setup.md`, `installation.md`, `oauth-over-ssh.md`),
  and the `hermes` UID/process in `docs/plans/...s6-overlay...`.
- **Worker-profile / source-repo proper noun "hermes":** the `hermes`
  worker-profile id listed alongside `codex`/`claude`/`opencode`/`kanban`/
  `council` (`docs/orchestration/PHASES.md`, `next-roadmap.md`), and the
  `hermes` source-repo name in the AOS hazmat↔hermes comparison docs.

## Excluded files / scope decisions

- **`docs/launch/**`** — left entirely (operational ledgers, release notes,
  per-grain snapshots; single-writer artifacts of other grains). Only this
  snapshot was added there.
- **`RELEASE_*.md`, `CHANGELOG`** — left entirely (historical).
- **Audit / prompt-fidelity / skill-identifier files excluded from the
  "Hermes Agent"→"muse" prose pass** (they quote the *current* "Hermes
  Agent" label as a finding, or are literal prompt strings, or are skill
  ids): `docs/jarvis-prime-app-*audit*`/`*gap*`/`*roadmap*`,
  `docs/audits/**`, `docs/audit/**`, `docs/aos-recovery/AOS_AGENT_*`,
  `docs/competitive/**`, `docs/context/**`,
  `website/docs/developer-guide/prompt-assembly.md`, and the two
  `*-hermes-agent*` skill `sidebar_label` pages. (These still received the
  safe `hermes <cmd>`→`muse <cmd>` command-invocation pass, which is always
  unambiguous.)
- **Standalone-`"Hermes"` prose pass scoped to** `website/docs/**`,
  `docs/orchestration/**`, the user-facing `docs/` guide dirs (mobile, voice,
  security, remote, profile, troubleshooting, integrations, android, termux,
  api), and the READMEs — i.e. the clearly product-framed surfaces. Internal
  architecture / research / AOS / jarvis-architecture / plans / product docs
  were left for standalone-`Hermes` (heavier codebase/substrate usage there;
  the `"Hermes Agent"` pass already caught their clear product names safely).
- **i18n (`website/i18n/ko`, `zh-Hans`)** — not touched (out of owned scope;
  stale auto-translations).

## Ambiguous "Hermes" left in place (noted, under-changed on purpose)

- `website/docs/integrations/providers.md:167` — "Hermes stores a long-lived
  refresh token …" sits on the same line as the `Hermes-4 models` substrate
  list, so the line-aware guard skipped the whole line. The product "Hermes"
  there stays (safe under-change; the line is dominated by substrate).
- `docs/jarvis-free-first-launch.md` — "Start Hermes" prose left as-is (file
  outside the standalone-prose scope); only the `` `hermes` `` command on
  that row was switched to `muse`.
- `docs/competitive/developer-agent-feature-harvest.md`,
  `docs/audits/**` — "Hermes"/"Hermes has …" product prose intentionally
  left (excluded files); only typed commands converted.
- `docs/android/termux-intent-bridge.md:49` — `command -v hermes` binary-on-
  PATH detection left (internal bridge spec; would be `muse` post-binary-
  rename, but that's owned by the code-rename grain).

## Anchor fixes (heading rebrand → internal link repair)

Changing headings that contained `hermes <cmd>` or "Hermes" renamed their
auto-generated anchors; the inbound English links were repaired so the build
stays clean:

- `#running-hermes-as-an-mcp-server` → `#running-muse-as-an-mcp-server`
- `#how-hermes-runs-shell-commands-on-windows` → `#how-muse-runs-shell-commands-on-windows`
- `#wsl2-bridge-hermes-in-wsl-to-windows-chrome` → `#wsl2-bridge-muse-in-wsl-to-windows-chrome`
- `#hermes-profile-export` → `#muse-profile-export`
- `#hermes-insights` → `#muse-insights`
- `#wsl-gateway-keeps-disconnecting-or-hermes-gateway-start-fails` → `…-muse-gateway-start-fails`
- `#surfacing-env-vars-in-hermes-config` → `#surfacing-env-vars-in-muse-config`

## Residual risks

- **Stale i18n anchors:** the Korean (`ko`) and `zh-Hans` translation files
  under `website/i18n/` still link to the *old* English `#…hermes…` anchors,
  so the build prints broken-anchor **warnings** for `/docs/ko/` and
  `/docs/zh-Hans/`. `onBrokenLinks: 'warn'` ⇒ build still passes (exit 0).
  Out of owned scope; flagged for the translations owner.
- **Pre-existing broken links (NOT caused by this sweep, present on base):**
  `#step-by-step-checklist` (heading has a `(Built-in Path)` suffix),
  `/docs/integrations/providers#fallback-model`,
  `#large-files-20mb--via-local-bot-api-server` (heading has `(>20MB)`),
  and `/docs/user-guide/features/rl-training` (the page does not exist on
  `main`). Left as-is.
- **Conservative under-change** on a handful of ambiguous standalone
  "Hermes" prose lines (see above) — preferred over risking the substrate
  honesty, per the task guidance.

## Validation performed

- `npm ci && npm run build` → exit 0 (catches broken internal links/anchors).
- Count-equality invariants vs base for every preserved identifier
  (`~/.hermes`, `HERMES_*`, `hermes-agent`, `hermes_cli`, `hermes_bootstrap`,
  `run_agent`, `hermes-acp`, `hermes-setup`, `X-Hermes-Session`, `Hermes-4`,
  `Hermes-3`, `Nous Research`, `Nous Hermes`, `hermes:cockpit`,
  `hermes-gateway.service`) — all unchanged.
- Zero leftover user-typed `hermes <subcommand>` invocations in the owned
  tree.
- No file outside owned paths changed; no `docs/launch/**` (other than this
  snapshot), `RELEASE_*`, `CHANGELOG`, or code (`*.py/.ts/.kt/.nix/.rb`,
  `scripts/`, `pyproject.toml`) touched.
