# PROJECT SYNAPSE — GPL / License Re-Audit (Master Plan §8.5)

**Project:** SYNAPSE — Legal gate (§8.5) · **Status:** RE-AUDIT v1.0 · **Date:** 2026-06-10

> **THIS IS NOT LEGAL ADVICE.** This document is an engineering-side license
> inventory and risk triage prepared as input for the ~$300 one-hour IP
> consult budgeted in the master plan
> (`docs/plans/2026-06-10-project-synapse-master-plan.md`, §8.5). Every
> "verdict" below is a triage label for counsel, not a legal conclusion.
> Nothing here was verified against signed license agreements; "verified"
> means *verified against locally installed package metadata*, nothing more.

---

## Executive verdict: **CLEAR-WITH-ACTIONS**

No GPL/AGPL/SSPL code was found **copied into** this repository, and nothing
in the SYNAPSE (P2) design links repo code at all (HTTP-client-only coupling
rule). Two clusters of work remain before the gate can be closed as CLEAR;
neither blocks Phase 0 engineering from proceeding in parallel.

### Action list (owner: Jeremiah; close before first commercial sale)

| # | Action | Priority | Blocking what |
|---|---|---|---|
| A1 | **Verify the UNVERIFIED optional-extra licenses** (table 1c below) against PyPI/upstream LICENSE files. Highest priority: `edge-tts` (training-knowledge prior: upstream has historically published under **GPL-3.0** — treat as GPL until disproven; it is the *default* TTS provider, lazy-installed) and `python-telegram-bot` (prior: **LGPL-3.0**; it IS redistributed in the Docker image, see A2). | HIGH | Closing this gate as CLEAR |
| A2 | **Docker image posture:** `Dockerfile:81` bakes `--extra all --extra messaging` into the published image, so the image *redistributes* the messaging deps (incl. `python-telegram-bot`, LGPL-3.0 prior). LGPL redistribution is normally workable (provide license text + source offer) but requires a NOTICE step we don't currently do. Put on counsel agenda; add license texts to the image or document the posture. | HIGH | Docker distribution channel |
| A3 | **TokenJuice / OpenHuman clean-room question → counsel.** Ships **default-on** in P1 (see §2). Bring the evidence pack (paths in §2.4) and the specific question in §5 item 2. Obtain a written one-paragraph sign-off or a remediation instruction. | HIGH | Closing this gate as CLEAR; commercial sale of P1 |
| A4 | **Record an author provenance statement** for `tools/tokenjuice/` (who wrote the Python reducer, what sources were open while writing, confirmation no OpenHuman Rust was translated line-by-line). Cheap now, expensive to reconstruct later. Optional but recommended: a structural-similarity diff review of `tools/tokenjuice/*.py` vs the OpenHuman Rust as evidence. | MED | Strength of A3 |
| A5 | **Add a CI license gate** (e.g. `pip-licenses` / `uv` + an allowlist failing on GPL/AGPL/SSPL/unknown for core + `[all]` + `[messaging]`) so this audit doesn't rot. The exact-pin policy in `pyproject.toml` makes this cheap. | MED | Audit freshness |
| A6 | **P2 model selection:** before bundling any GGUF in the SYNAPSE pak, verify the model's license permits *redistribution of weights in a commercial product* (candidates in §3.3) and archive the license text + download hash in the SYNAPSE repo. | MED (by S1/S2) | SYNAPSE Sprint 1 plugin work |
| A7 | **P2 at-signing verifications:** UE5 EULA royalty terms, Fab Standard License scope, Megascans-in-UE entitlement — re-read the *current* published terms when the SYNAPSE project is created, not from memory (§3.1–3.2). | MED (by S1) | SYNAPSE repo creation |
| A8 | Fix two cosmetic metadata gaps on our side: installed `requests` is 2.33.1 vs pin 2.33.0 in this environment (env drift, not a license issue, but it means this audit's metadata read is of the *installed* env — re-run after `uv sync --frozen`); `tzdata` (win32-only) was not resolvable locally → UNVERIFIED. | LOW | Hygiene |

**Why not BLOCKING:** nothing GPL is copied into the repo; the one
GPL-adjacent question (TokenJuice) has a documented MIT upstream for the same
behavior and written attribution/clean-room claims already in the tree.
**Why not CLEAR:** ~30 optional-extra packages could not be license-verified
locally, the default TTS provider has a credible unverified GPL prior, the
Docker image redistributes an LGPL-prior package without a notice step, and
the clean-room claim has not been reviewed by counsel.

---

## 1. Surface P1 — the MUSE platform as distributed

### 1.0 Distribution posture

- **Repo license:** MIT, © 2025 Nous Research (`/home/user/M.U.S.E/LICENSE`;
  `pyproject.toml` `license = { text = "MIT" }`). Third-party attributions
  live in `THIRD_PARTY_NOTICES.md`.
- **How P1 ships:** as **source** (pip/uv install from this repo / PyPI
  sdist+wheel). The wheel does **not** bundle dependencies — users' package
  managers fetch them from PyPI at install time. Under that posture, a
  copyleft *dependency declaration* does not by itself impose copyleft terms
  on the MIT code; the user combines the works on their own machine.
- **Exception — the Docker image** (`Dockerfile:81`:
  `uv sync --frozen --no-install-project --extra all --extra messaging`)
  **does** redistribute the resolved dependency closure for `[all]` +
  `[messaging]`. Any copyleft package in that closure is redistributed by us
  and its notice/source-offer obligations attach to the image. See action A2.
- **Lazy-install channel** (`tools/lazy_deps.py`): provider/TTS/messaging
  backends install at first use on the *user's* machine. We never
  redistribute these; we only trigger a `pip install` the user implicitly
  authorizes. Lower-risk posture, but the default-provider choice still
  matters reputationally and for counsel review (see `edge-tts`).

### 1.1 Core runtime dependencies (every install) — all license-verified locally

Verified by reading installed dist-info METADATA via
`importlib.metadata` under the system Python (and LICENSE files where
metadata said UNKNOWN).

| Dependency (pin) | License (verified) | Risk | Note |
|---|---|---|---|
| openai==2.24.0 | Apache-2.0 | None | |
| python-dotenv==1.2.2 | BSD-3-Clause | None | |
| fire==0.7.1 | Apache-2.0 | None | |
| httpx[socks]==0.28.1 | BSD-3-Clause | None | socks extra → `socksio` (MIT, verified via dist-info LICENSE file) |
| rich==14.3.3 | MIT | None | |
| tenacity==9.1.4 | Apache-2.0 | None | |
| pyyaml==6.0.3 | MIT | None | |
| ruamel.yaml==0.18.17 | MIT | None | |
| requests==2.33.0 | Apache-2.0 | None | installed env had 2.33.1 (see A8) |
| jinja2==3.1.6 | BSD-3-Clause | None | |
| pydantic==2.12.5 | MIT | None | |
| prompt_toolkit==3.0.52 | BSD-3-Clause | None | |
| croniter==6.0.0 | MIT | None | |
| PyJWT[crypto]==2.13.0 | MIT | None | crypto extra → `cryptography` (Apache-2.0 OR BSD-3-Clause; widely dual-licensed — confirm in CI gate, A5) |
| tzdata==2025.3 (win32 only) | **UNVERIFIED** | Low | Not resolvable locally (Linux host). IANA tzdata is public-domain-style; verify per A1/A8 |

**Core verdict: no GPL/AGPL/SSPL in the always-installed set.** All
permissive (MIT/BSD/Apache/ISC-class).

### 1.2 Optional extras — license-verified locally

| Dependency (pin) | Extra | License (verified) | Risk | Note |
|---|---|---|---|---|
| aiohttp==3.14.0 | messaging/slack/homeassistant/sms | Apache-2.0 AND MIT | None | dual notice, both permissive |
| mcp==1.26.0 | mcp/dev/computer-use | MIT | None | |
| agent-client-protocol==0.9.0 | acp | Apache-2.0 (verified via dist-info LICENSE file; no metadata field) | None | |
| simple-term-menu==1.6.6 | cli | MIT | None | |
| ptyprocess==0.7.0 | pty (non-win32) | ISC (classifier + LICENSE file; `License:` field says UNKNOWN) | None | |
| google-api-python-client==2.194.0 | google | Apache-2.0 | None | |
| google-auth-oauthlib==1.3.1 | google | Apache-2.0 | None | |
| google-auth-httplib2==0.3.1 | google | Apache-2.0 | None | |
| youtube-transcript-api==1.2.4 | youtube | MIT | None | ToS/scraping question is separate from license; out of scope here |
| fastapi==0.133.1 | web | MIT | None | |
| starlette==1.0.1 | web | BSD-3-Clause | None | |
| uvicorn[standard]==0.41.0 | web | BSD-3-Clause | None | `[standard]` transitives not enumerated — covered by CI gate A5 |
| psutil==7.2.2 | dev | BSD-3-Clause | None | dev-only, not shipped |
| pytest==9.0.3 / ruff==0.15.10 / ty==0.0.21 / debugpy==1.8.20 | dev | MIT (all) | None | dev-only, not shipped (removed from `[all]` 2026-06-09) |

### 1.3 Optional extras — NOT resolvable locally → **UNVERIFIED** (action A1)

These packages are not installed in this environment (neither system Python
nor the project `.venv`), so their licenses could not be read from dist-info.
Per the audit protocol they are marked **UNVERIFIED — do not rely on the
prior column**. "Prior" = training-knowledge expectation recorded only to
*prioritize* verification; it is explicitly not a finding.

| Dependency (pin) | Extra / lazy key | License | Risk triage | Prior (unverified — for prioritization only) |
|---|---|---|---|---|
| **edge-tts==7.2.7** | edge-tts / `tts.edge` (**default TTS provider**, lazy) | **UNVERIFIED** | **HIGH** | Upstream `rany2/edge-tts` has historically published under **GPL-3.0**. Lazy-install means we don't redistribute it, but a GPL default provider deserves explicit counsel review. Verify first. |
| **python-telegram-bot[webhooks]==22.6** | messaging/termux (**redistributed in Docker image**) | **UNVERIFIED** | **HIGH** | Prior: **LGPL-3.0**. Because `Dockerfile` installs `[messaging]`, the image redistributes it → notice/source-offer step (A2). |
| mautrix[encryption]==0.21.0 | matrix (lazy) | **UNVERIFIED** | MED | Prior: **MPL-2.0** (weak copyleft, file-level); `[encryption]` pulls `python-olm` (prior: Apache-2.0 bindings over libolm). Lazy-only; verify. |
| discord.py[voice]==2.7.1 | messaging (Docker image via `[messaging]`) | **UNVERIFIED** | LOW | Prior: MIT. `[voice]` pulls PyNaCl (prior: Apache-2.0; uv override pins >=1.6.2) |
| anthropic==0.87.0 | anthropic (lazy) | **UNVERIFIED** | LOW | Prior: MIT |
| exa-py==2.10.2 | exa (lazy) | **UNVERIFIED** | LOW | |
| firecrawl-py==4.17.0 | firecrawl (lazy) | **UNVERIFIED** | LOW | |
| parallel-web==0.4.2 | parallel-web (lazy) | **UNVERIFIED** | LOW | |
| fal-client==0.13.1 | fal (lazy) | **UNVERIFIED** | LOW | |
| modal==1.3.4 | modal (lazy) | **UNVERIFIED** | LOW | |
| daytona==0.155.0 | daytona (lazy) | **UNVERIFIED** | LOW | |
| vercel==0.5.7 | vercel (lazy) | **UNVERIFIED** | LOW | |
| hindsight-client==0.6.1 | hindsight (lazy) | **UNVERIFIED** | LOW | |
| sentence-transformers==5.5.1 | embeddings (lazy) | **UNVERIFIED** | LOW | Prior: Apache-2.0. NB: *model weights* it downloads carry their own licenses — separate check if ever bundled |
| numpy==2.4.3 | embeddings/voice | **UNVERIFIED** | LOW | Prior: BSD-3-Clause |
| duckdb==1.4.3 | analytics (lazy) | **UNVERIFIED** | LOW | Prior: MIT |
| brotlicffi==1.2.0.1 | messaging (Docker image) | **UNVERIFIED** | LOW | Prior: MIT |
| slack-bolt==1.27.0 / slack-sdk==3.40.1 | slack/messaging (Docker image) | **UNVERIFIED** | LOW | Prior: MIT |
| qrcode==7.4.2 | messaging/dingtalk/feishu (Docker image via messaging) | **UNVERIFIED** | LOW | Prior: BSD |
| Markdown==3.10.2 | matrix (lazy) | **UNVERIFIED** | LOW | Prior: BSD-3-Clause |
| aiosqlite==0.22.1 | matrix (lazy) | **UNVERIFIED** | LOW | Prior: MIT |
| asyncpg==0.31.0 | matrix (lazy) | **UNVERIFIED** | LOW | Prior: Apache-2.0 |
| aiohttp-socks==0.11.0 | matrix (lazy) | **UNVERIFIED** | LOW | Prior: Apache-2.0 |
| elevenlabs==1.59.0 | tts-premium (lazy) | **UNVERIFIED** | LOW | Prior: MIT |
| faster-whisper==1.2.1 | voice (lazy) | **UNVERIFIED** | LOW | Prior: MIT; transitives ctranslate2/onnxruntime prior MIT — verify with it |
| sounddevice==0.5.5 | voice (lazy) | **UNVERIFIED** | LOW | Prior: MIT; wraps PortAudio (prior: MIT-style) |
| pywinpty==2.0.15 | pty (win32) | **UNVERIFIED** | LOW | Prior: MIT |
| honcho-ai==2.0.1 | honcho (lazy) | **UNVERIFIED** | LOW | |
| boto3==1.42.89 | bedrock (lazy) | **UNVERIFIED** | LOW | Prior: Apache-2.0 |
| azure-identity==1.25.3 | azure-identity (lazy) | **UNVERIFIED** | LOW | Prior: MIT |
| dingtalk-stream==0.24.3 / alibabacloud-dingtalk==2.2.42 | dingtalk (lazy) | **UNVERIFIED** | LOW | Prior: Apache-2.0 |
| lark-oapi==1.5.3 | feishu (lazy) | **UNVERIFIED** | LOW | Prior: MIT |

(`mistralai` extra was removed 2026-05-12 — PyPI quarantine; not part of any
shipping surface today. SIA is intentionally **not** a dependency — external
CLI on PATH, MIT per `THIRD_PARTY_NOTICES.md`.)

### 1.4 Vendored / in-repo third-party material

| Material | License | Risk | Note |
|---|---|---|---|
| `tools/tokenjuice/rules/*.json` (96 rule files) | MIT (© 2026 Vincent Koc, `vincentkoc/tokenjuice`) — attribution in `THIRD_PARTY_NOTICES.md` + `tools/tokenjuice/rules/NOTICE.md` | Low | Vendored verbatim from the MIT upstream; data, not code |
| `tools/tokenjuice/*.py` (the reducer) | Claimed MIT (this repo), claimed clean-room | **See §2** | The §8.5 question |
| SIA task-directory format adaptation (`hermes_cli/workers/sia_assets.py`) | MIT (Hexo Labs), attributed | Low | Layout/role-design adaptation only; no source copied per `THIRD_PARTY_NOTICES.md:32` |

---

## 2. The OpenHuman question (the prior audit's flag)

### 2.1 What was flagged, where

- **Prior audit doc:** `docs/audits/hermes-openhuman-audit.md`
  (2026-06-03), **§6 "License audit (gating)"**. It flagged that OpenHuman —
  the project whose **TokenJuice** terminal-output compaction was being
  ported into Hermes — is **GPL-3.0** (`openhuman/LICENSE`), including its
  Rust TokenJuice implementation (`openhuman/.../tokenjuice/*.rs`), against
  Hermes' MIT license. Verdict in that audit: **"❌ never copy code"** /
  **"reference only"** for the Rust; **"✅ reuse w/ attribution"** for the
  96 vendored JSON rule files, which are verbatim from the *separate MIT
  upstream* `vincentkoc/tokenjuice`.
- **Master plan reference:**
  `docs/plans/2026-06-10-project-synapse-master-plan.md:191-193` (§8.5)
  names this exact flag as the reason for this re-audit.
- **Related docs:** `docs/audits/tokenjuice-integration-plan.md`,
  `docs/audits/one-sprint-build-plan.md`, `THIRD_PARTY_NOTICES.md:66-105`,
  `tools/tokenjuice/rules/NOTICE.md`.

### 2.2 What code it concerns

The compaction stack at `tools/tokenjuice/` (`classify.py`, `config.py`,
`integration.py`, `loader.py`, `raw_log.py`, `reduce.py`, `scrub.py`,
`text.py`, `types.py` + `rules/*.json`), wired into the agent loop at
`agent/tool_executor.py:53-203` (`_tokenjuice_compact`, both sequential and
concurrent tool paths).

### 2.3 Does it ship in P1 default installs? **Yes, default-on.**

- `tools/` is included in the wheel
  (`pyproject.toml` `[tool.setuptools.packages.find]` includes `"tools",
  "tools.*"`), and `agent/tool_executor.py` imports it unconditionally.
- `tools/tokenjuice/config.py:35` — `enabled: bool = True` (opt-out via
  config / `HERMES_TOKENJUICE=off`, per `agent/tool_executor.py:74`).

So whatever the legal status of the reducer is, it attaches to **every** P1
distribution, including the Docker image. This is why it stays on the
counsel agenda rather than being closed by engineering.

### 2.4 Clean-room status — the evidence on file

What the repo asserts, with paths:

1. `THIRD_PARTY_NOTICES.md:75-79` — "The Python reducer in
   `tools/tokenjuice/` is a **clean-room reimplementation** of TokenJuice
   behavior written from the public upstream specification — **no** source
   code from any TokenJuice port (including GPL-licensed ports) is copied."
2. `tools/tokenjuice/rules/NOTICE.md:12-14` — same claim, "does not copy
   code from any GPL-licensed port."
3. `docs/audits/hermes-openhuman-audit.md:99-104` — "The reducer itself is
   clean-room reimplemented in Python from the public upstream behavior — no
   GPL Rust is copied."

What weakens the claim (the part counsel must see):

- The same audit (§1, line 16) says the port was done "using OpenHuman only
  as a **behavioral reference** (its Rust code is GPL-3.0)" and the audit
  itself was "performed against the live local checkouts … and
  `/home/user/openhuman` (reference only)". I.e., the author(s) plausibly
  **had the GPL-3.0 Rust source available and consulted its behavior** while
  writing the Python. That is *reimplementation with access*, not a
  two-team/Chinese-wall clean room. Copyright protects expression rather
  than behavior, and the same behavior is independently documented by the
  MIT upstream (`vincentkoc/tokenjuice`) — both points cut in our favor —
  but "clean-room" is being used loosely in the repo's own docs, and no
  author provenance statement, process record, or similarity review exists
  in the tree (I found none searching for any such record).

### 2.5 Verdict: **NEEDS COUNSEL** (not BLOCKING, not RESOLVED)

- Not **RESOLVED**: the clean-room claim is self-asserted, the process
  evidence is thin (access to the GPL source during the port is implied by
  the audit's own framing), and the code ships default-on in the commercial
  P1 surface.
- Not **BLOCKING**: there is no evidence of copied GPL code; the rule data
  is verifiably from an MIT upstream; the behavior being replicated has a
  permissively-licensed canonical source; attribution is already in place;
  and an easy remediation path exists if counsel wants one (re-derive the
  reducer strictly from the MIT upstream's spec/tests, or relicense-isolate
  the module).
- **Inputs for counsel:** the four file paths in §2.4, plus
  `agent/tool_executor.py` and `tools/tokenjuice/`. Pre-work: action A4
  (provenance statement + optional similarity diff vs the OpenHuman Rust).

---

## 3. Surface P2 — SYNAPSE (future UE5 app): design-time license posture

SYNAPSE links **nothing** from this repo. The coupling rule (master plan /
`docs/synapse/design/11-technical-design.md`) is **HTTP client only**: the
UE5 app talks to the MUSE gateway over HTTP/SSE with bearer auth. The MIT
gateway code never enters the shipped binary, and no repo Python ships in
the pak. The rules below are the posture SYNAPSE adopts at repo creation
(Sprint S1) — each carries a "verify at signing" step because P2 has no
lockfile to audit yet.

### 3.1 Engine — Unreal Engine 5 EULA

- Royalty: **5% of gross revenue above $1M lifetime gross per product** —
  *per Epic's published EULA; verify the current EULA text at signing*
  (terms and the threshold have changed before). Steam's 30% does not reduce
  "gross" for royalty purposes under the published terms — confirm with
  counsel.
- Obligations to plan for: royalty reporting/registration of the product
  with Epic once revenue starts; UE trademark/branding rules for store
  pages; you may not ship UE source/tools themselves.

### 3.2 Content — Fab / Quixel Megascans

- Plan (master plan §5, production plan S2/S6/S10) leans on **Fab asset
  packs (~$1,000)** and **Megascans** for environment dress.
- Posture rule: assets may be shipped **only as incorporated, cooked
  content inside the game** (the standard Fab license scope) — never
  redistributed as source assets, never in a form users can extract and
  reuse as assets. **Verify the Fab Standard License text per asset at
  purchase**, and specifically verify the current **Megascans entitlement**
  (historically free-for-UE-rendered products via the Unreal/Fab
  integration; the terms changed when Quixel moved to Fab — do not rely on
  the pre-Fab "free with UE" memory).
- The **Fab runtime-LLM plugin** ("Runtime Local LLM" / "GenAI Llama"
  class, master plan §134, tech design §135-136) is *code*, not content:
  read its individual Fab license **and** its embedded third-party notices
  (it wraps llama.cpp — MIT-class prior, verify) before integrating.
  Confirm the plugin's license permits shipping in a commercial binary and
  does not impose copyleft.

### 3.3 Bundled GGUF model — must be redistribution-licensed

The hybrid AI ladder bundles one ~3–4B instruct GGUF (Q4, ≈2.5 GB) in its
own pak chunk (tech design §154). **Rule: the bundled model's license must
permit commercial redistribution of the weights** — Apache-2.0/MIT-class,
not research-only, not "contact us" licensing.

Candidate model families whose published licenses are known to permit
redistribution (verify the exact checkpoint's license file at selection —
families sometimes mix licenses across sizes/variants):

1. **Qwen 2.5 / Qwen 3 instruct (3–4B class)** — Apache-2.0 on the small
   sizes (some larger Qwen variants have used a different license — check
   the specific repo).
2. **Microsoft Phi-3 / Phi-4-mini class** — MIT.
3. **IBM Granite / HF SmolLM2 class** — Apache-2.0.

Flagged, *not* recommended without counsel: **Meta Llama 3.x** (the Fab
plugin is "GenAI Llama class") — the Llama Community License permits
redistribution but adds conditions (attribution/"Built with Llama", naming
rules, acceptable-use policy, scale clause). Usable, but it is not
Apache/MIT-class; if the bundled model is Llama-family, that's a consult
agenda item. **Google Gemma** similarly ships under a custom license with a
use policy — treat like Llama, not like Apache.

**Verification step (A6):** at model selection, download the checkpoint's
LICENSE/`README` from the canonical repo, confirm (a) redistribution of
weights allowed, (b) commercial use allowed, (c) no research-only clause,
(d) any attribution/notice requirement is implementable in the credits
screen; archive the license text + model file hash in the SYNAPSE repo and
record it in the SYNAPSE third-party notices.

### 3.4 No-GPL-link rule for the shipped binary

**No GPL/AGPL-licensed code may be statically or dynamically linked into the
shipped SYNAPSE binary or its plugins.** GPL linking obligations are
incompatible with shipping a closed commercial UE title (and with parts of
the UE EULA posture). LGPL is allowed only with counsel sign-off and only
dynamically linked with relink ability — in practice, on a packaged UE/Steam
title, treat LGPL as "avoid". Enforce mechanically: SYNAPSE CI runs a
license scan over `Plugins/`, `ThirdParty/`, and the vcpkg/conan/whatever
manifest, failing on GPL/AGPL/SSPL/unknown (mirror of action A5). The
HTTP-only coupling rule already keeps every license question in this repo
(including TokenJuice, §2) **out** of the SYNAPSE binary entirely.

---

## 4. Android Kotlin app (`apps/android/`) — best-effort

Manifest read from `apps/android/gradle/libs.versions.toml` +
`apps/android/app/build.gradle.kts:134-177`. Gradle does not embed license
metadata locally the way dist-info does, so classification is from the
artifacts' well-known published licenses — treat the whole table as
**high-confidence prior, to be confirmed by a Gradle license-report plugin**
(one-line addition; fold into A5).

| Dependency | License (published; confirm via license-report) | Risk | Note |
|---|---|---|---|
| androidx.* (core-ktx, lifecycle*, activity-compose, compose BOM + ui/material3/icons, navigation-compose, datastore, security-crypto, camera*) | Apache-2.0 (AOSP/Jetpack standard) | None | |
| org.jetbrains.kotlinx (serialization-json, coroutines) | Apache-2.0 | None | |
| app.rive:rive-android 9.6.5 | MIT (Rive runtimes are published MIT) | Low | Confirm; runtime is MIT, Rive *editor assets* are governed by Rive's terms — only ship .riv files you have rights to |
| com.google.mlkit:face-detection 16.1.7 | **Proprietary (Google Play services / ML Kit ToS), not OSS** | **Note** | Not a copyleft risk, but it is closed-source SDK under Google's ML Kit terms — confirm the app's privacy disclosure matches (camera/face data; repo comment says on-device only, no frames stored/sent) |
| junit, robolectric, espresso, androidx.test.* | EPL-1.0 (junit) / MIT (robolectric) / Apache-2.0 | None | test-only, not shipped |

No GPL/LGPL candidates found in the Android dependency set. Action: add
`com.jaredsburrows.license` or Gradle's license-report plugin and a Play
Store OSS-notices screen before any Play release (standard practice; the
attribution requirement of Apache-2.0/MIT applies to the shipped APK).

---

## 5. Open questions — agenda for the $300 / one-hour IP consult

Bring: this document, `THIRD_PARTY_NOTICES.md`,
`docs/audits/hermes-openhuman-audit.md`, the A4 provenance statement, and
the verified version of table 1c.

1. **(10 min) Distribution posture sanity check.** MIT project, source
   distribution, deps pulled by the user from PyPI — confirm that declaring
   copyleft *optional* dependencies (extras / lazy-install) does not affect
   the MIT licensing of our code, and what, if anything, we must say in
   docs.
2. **(15 min) TokenJuice / OpenHuman.** Facts: GPL-3.0 Rust port existed;
   the same behavior's canonical upstream is MIT; our Python reducer was
   written with the GPL port available "as a behavioral reference"; no
   copied code is claimed or found; rule JSON is verbatim-MIT with
   attribution. Question: is the reducer safely original work as-is, or do
   you want (a) a provenance affidavit, (b) a similarity review, or (c) a
   re-derivation from the MIT upstream only? It ships default-on in the
   commercial product.
3. **(10 min) Docker image.** The image redistributes `[all]+[messaging]`
   including (prior) LGPL-3.0 `python-telegram-bot`. What notice/source-
   offer mechanics do you want in the image (license texts dir? link to
   PyPI sdists?) — or should the published image drop `[messaging]`?
4. **(5 min) Default GPL tool via lazy-install.** If `edge-tts` verifies as
   GPL-3.0: we never redistribute it, the user's machine pip-installs it on
   first use of the default TTS path. Acceptable, or should the default
   flip to a permissive provider?
5. **(10 min) SYNAPSE posture ratification.** The four rules in §3 (UE5
   royalty + reporting, Fab/Megascans shipped-content-only, redistribution-
   licensed GGUF with archived license, no-GPL-link CI gate) — anything
   missing for a paid Steam title with a bundled LLM? Specifically: if the
   bundled model ends up Llama-family, what attribution/AUP exposure does
   the Llama Community License create for a game?
6. **(5 min) Trademark adjacency.** "SYNAPSE" name search is a separate
   §8.5 work item (USPTO + Steam) — confirm scope of the search counsel
   would consider sufficient pre-launch.
7. **(5 min) CREDITS/notices hygiene.** Are `THIRD_PARTY_NOTICES.md` +
   per-package license texts in the Docker image + an Android OSS-notices
   screen sufficient attribution mechanics across all three surfaces?

---

## Method note (reproducibility)

- Python licenses read from installed dist-info METADATA
  (`License-Expression` → `License` → classifiers → bundled LICENSE file)
  via `importlib.metadata` under `/usr/local/bin/python3`; project `.venv`
  checked for the extras (none installed there). Packages absent from both
  → **UNVERIFIED**, never guessed.
- Repo evidence: `pyproject.toml`, `LICENSE`, `THIRD_PARTY_NOTICES.md`,
  `tools/lazy_deps.py`, `tools/tokenjuice/`, `agent/tool_executor.py`,
  `Dockerfile`, `docs/audits/hermes-openhuman-audit.md`,
  `docs/plans/2026-06-10-project-synapse-master-plan.md`,
  `docs/synapse/design/11-technical-design.md`,
  `apps/android/gradle/libs.versions.toml`,
  `apps/android/app/build.gradle.kts`.
- This re-audit is **point-in-time** against pins as of 2026-06-10
  (`hermes-agent 0.14.1+aci.1`). Action A5 makes it continuous.

*Prepared as preparation for counsel. Not legal advice.*
