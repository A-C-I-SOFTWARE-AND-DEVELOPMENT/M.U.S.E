# Hermes — Known Limitations

**Phase:** 27 (final 10/10 readiness gate)

This document is the honesty contract for Phase 27. Every component
that is mocked, stubbed, gated, or otherwise not yet production-grade
is listed here with its location and the reason it landed in this
state. If you ship a fix, **remove the corresponding bullet from this
file in the same PR**.

This file supersedes the orchestration-only
[`docs/orchestration/known-limitations.md`](../orchestration/known-limitations.md)
for product-level reviews; that file is preserved for its substrate
context.

---

## 1. GitHub publisher's "live" path is a seam, not a turnkey integration

**Where:** `hermes_cli/github_publisher.py:publish`.

**What:** Live mode requires both `HERMES_PUBLISH_LIVE=1` *and* a
caller-supplied `transport` callable. The default build ships no
transport, so the worst case for an accidental flag flip is a
`NameError` at the call site — never an unintended post.

**Why:** Embedding a GitHub HTTP client (or the MCP wrapper) is a
separate phase. The operator owns the token-scope and
network-policy decisions, not the orchestrator.

**Mitigation:** Dry-run is the default and writes a complete JSON
descriptor under `.hermes/publish/` so an operator can hand-post or
script the transport.

**Roadmap link:**
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §1.

---

## 2. End-to-end gateway smoke is not in CI

**Where:** `gateway/platforms/*` adapters; CI workflows under
`.github/workflows/`.

**What:** Every gateway adapter (Telegram, Discord, Slack, WhatsApp,
Signal, Email, Home Assistant, Matrix, Mattermost, DingTalk, WeCom,
WeiXin, Feishu, QQBot, BlueBubbles, Yuanbao, generic webhook) has
unit tests, and Telegram has webhook-secret enforcement
(`tests/gateway/test_telegram_webhook_secret.py`). What does **not**
run in CI is a full round-trip "user sends message → Hermes replies"
smoke against any live platform.

**Why:** Live smokes need credentials and a registered bot per
platform. Embedding those secrets in CI is itself a security issue;
running them on a side channel is the right answer and is not yet
wired.

**Mitigation:** The gateway's local test suite covers parsing,
session bookkeeping, and webhook secret validation. Operators run
the end-to-end smoke manually with `hermes gateway --platform X
--dry-run` before flipping a platform live.

**Roadmap link:**
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §2.

---

## 3. Worker proposals are descriptive, not always executable

**Where:** `hermes_cli/workers/*.py`.

**What:** Some workers (the original substrate set used by the
orchestrator) return a Markdown proposal that *describes* what they
would do rather than producing a patch. The newer adapter set
(`aider.py`, `claude_code.py`, `codex.py`, `goose.py`,
`hermes_local.py`, `chatgpt_handoff.py`) defines the contract for
real execution — see `tests/test_worker_*.py` — but turning every
worker into a patch-producing actuator end-to-end is staged.

**Why:** Closing the mutate-and-merge loop introduces an external-API
dependency that has to be opt-in per operator.

**Mitigation:** The merge engine, scoring, gates, and publisher are
all shaped to handle real patches the day every worker writes them.

**Roadmap link:**
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §3.

---

## 4. Scoring is a fixed-weight linear combination

**Where:** `hermes_cli/scoring.py:WEIGHTS`.

**What:** Weights are set in source, not learned from outcomes. There
is no per-task adaptation.

**Why:** Deterministic and auditable beats clever-but-opaque for the
release-hardening line of phases. Adaptive scoring is on the roadmap.

**Mitigation:** Weights are documented, asserted to sum to 1.0
(`tests/test_scoring.py:test_weights_sum_to_one`), and small enough
to reason about by hand.

**Roadmap link:**
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §4.

---

## 5. Worktree cleanup is best-effort

**Where:** `hermes_cli/orchestrator.py:WorktreeManager.remove`.

**What:** If `git worktree remove --force` fails, the cleanup falls
back to `shutil.rmtree(ignore_errors=True)`. A genuinely hostile
filesystem state (read-only mounts, stale NFS handles) could leave
directories behind.

**Why:** A hard failure on cleanup is worse than an orphaned
directory — the orphan is easy to spot under
`.hermes/worktrees/<name>/` and easy to remove manually.

**Mitigation:** The orchestrator logs every worktree it creates and
exposes `WorktreeManager.cleanup_all` for explicit teardown in test
fixtures.

---

## 6. No per-task budget or hard-cancel timeout

**Where:** `hermes_cli/orchestrator.py:Orchestrator.run`.

**What:** The orchestrator imposes a `timeout_seconds` default per
worker via `Future.result(timeout=...)`, but a misbehaving worker
that ignores cooperative cancellation can still consume its thread
for the lifetime of the process.

**Why:** Current workers complete in milliseconds. Hard cancellation
matters only once workers start calling external tools at scale.

**Mitigation:** Each worker runs in a sandboxed worktree, so the
blast radius of a stuck worker is bounded.

---

## 7. Validation gates are intentionally narrow

**Where:** `hermes_cli/validation_gates.py:GATES`.

**What:** Five gates — `structure`, `size`, `secrets`, `unicode`,
`policy`. They catch the documented failure modes. They do **not**
run linters, type-checkers, or domain-specific schema validation.

**Why:** A small, deterministic gate set is auditable. Bolting on
heavy checks (mypy, ruff, integration tests) belongs in CI, not at
the orchestrator gate.

**Mitigation:** The gate registry is a tuple — adding a gate is one
function and one entry. New gates do not need to know about the
rest.

**Roadmap link:**
[`hermes-next-roadmap.md`](hermes-next-roadmap.md) §5.

---

## 8. The orchestrator is single-host

**Where:** `hermes_cli/orchestrator.py:ThreadPoolExecutor` fan-out.

**What:** All workers run inside the same Python process. There is
no support for distributing workers across machines.

**Why:** Out of scope for Phase 24 and Phase 27.

**Mitigation:** Multi-host orchestration is roadmap item #6 in
[`hermes-next-roadmap.md`](hermes-next-roadmap.md).

---

## 9. Adaptive self-improvement loop is open, not closed

**Where:** `skills/self-improvement-loop/`,
`skills/ai-improvement-radar/`, `docs/orchestration/decision-ledger.md`.

**What:** Hermes can observe its own outcomes (the decision ledger
records every arbitration), produce retrospectives, and surface
suggestions via the AI radar. What it cannot yet do is feed those
retrospectives back into scoring weights, worker selection, or
prompt templates without an operator clicking "apply".

**Why:** Closing the loop without human-in-the-middle is a policy
decision that belongs to each operator.

**Mitigation:** The ledger + radar + retrospective trio is a
working *open* loop; a fully *closed* loop is roadmap item #4.

---

## 10. No telemetry, no remote audit log by default

**Where:** *missing by design*.

**What:** The orchestrator records per-run JSON under
`.hermes/runs/run-*.json` and per-publish JSON under
`.hermes/publish/`, but there is no metrics export, no log
aggregator, no remote audit sink.

**Why:** Telemetry is a privacy and policy decision, not a default.

**Mitigation:** Per-run JSON is sufficient for hand audit. Telemetry
is opt-in via roadmap item #7 (Prometheus textfile when
`HERMES_TELEMETRY_DIR` is set).

---

## 11. Documented test names in past prompts may drift from filenames

**Where:** prior-phase prompts that reference, e.g.,
`tests/test_validation.py`, `tests/test_decision_ledger.py`,
`tests/test_model_router.py`, `tests/test_secrets_policy.py`,
`tests/test_phase_gated_workflows.py`.

**What:** Those filenames do not exist. The equivalent coverage
lives under the names actually checked in (e.g.
`tests/test_validation_gates.py`, `tests/test_orchestrator_job_controller.py`,
`tests/test_orchestrator_commands.py`,
`tests/test_orchestrator_api.py`).

**Why:** Phase prompts were written against intent; filenames
settled differently when the code landed. The intent is preserved.

**Mitigation:** The Phase 27 readiness report
([`hermes-final-10-10-readiness-report.md`](hermes-final-10-10-readiness-report.md)
§3) lists the actual filenames the gate runs against. When you
re-read an old phase prompt, treat its test list as a *contract on
coverage*, not a *contract on filenames*.

---

## 12. `hermes_cli/integrations/` does not exist as a package

**Where:** referenced in Phase 27's compile command; not in the
filesystem.

**What:** The CLI's integration surface lives directly under
`hermes_cli/` (`gateway.py`, `webhook.py`, `slack_cli.py`,
`vercel_auth.py`, `copilot_auth.py`, `dingtalk_auth.py`,
`browser_connect.py`, `pairing.py`, `pty_bridge.py`, …) and inside
`plugins/`. No `integrations/` subpackage was ever introduced.

**Why:** Integrations grew organically alongside the CLI rather than
into a dedicated namespace. Refactoring them into one is a
documentation tax with no functional payoff.

**Mitigation:** Any reviewer following an old prompt that mentions
`hermes_cli/integrations/*.py` should read the list above instead.
The Phase 27 readiness report (§2) calls this out explicitly.

---

## 13. Website (Docusaurus) build-time npm advisories have no clean fix

**Where:** `website/` (the Docusaurus documentation site).
`npm audit` reports 24 advisories there (23 moderate, 1 high).

**What:** The high (`serialize-javascript`) and the bulk of the
moderates resolve to **build-time-only** dev dependencies pulled in
transitively under `@docusaurus/bundler` → `copy-webpack-plugin` /
the webpack dev stack: `serialize-javascript`, `copy-webpack-plugin`,
`css-minimizer-webpack-plugin`, `sockjs`, `uuid`, `webpack-dev-server`.
They run during `docusaurus build` / `docusaurus start`; they are **not
shipped in the static HTML output** and never process untrusted input.

**Why no fix is applied:**
- Upgrading Docusaurus to the latest 3.x (3.10.1 at time of writing)
  clears **zero** of these — the latest release still ships the same
  bundler transitives. `serialize-javascript` is already at its latest
  published version (6.0.2).
- `npm audit fix --force`'s only offered path is to **downgrade**
  `@easyops-cn/docusaurus-search-local` to `0.26.1` — a Docusaurus-2-era
  major that would break this 3.x site, and which does not even sit on
  the vulnerable dependency path (the leaves live under `core`/`bundler`,
  not the search plugin). So the "fix" is both breaking and ineffective.
- The non-website JS trees (`web/`, `ui-tui/`, `scripts/whatsapp-bridge/`)
  and the Python deps were fully remediated (PRs #338, #339); the
  non-breaking subset of the website advisories + a Docusaurus version-skew
  fix landed in #340. Only this irreducible build-time tail remains.

**Mitigation:** Treat these as **accepted, build-time-only** risk for a
static docs site. Disposition options, none of which forces a breaking
build: (1) dismiss the corresponding Dependabot alerts with
"build-time only / no fix available"; (2) revisit when upstream Docusaurus
ships a release that bumps `copy-webpack-plugin` / `serialize-javascript`.
Re-checking is a one-liner: `cd website && npm audit`. See the 2026-06-05
re-audit ([`JARVIS_MOBILE_NATIVE_REAUDIT_2026-06-05.md`](JARVIS_MOBILE_NATIVE_REAUDIT_2026-06-05.md))
for the surrounding dependency-hardening campaign.
