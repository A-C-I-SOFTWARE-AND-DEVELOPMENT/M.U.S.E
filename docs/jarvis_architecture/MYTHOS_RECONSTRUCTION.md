# Deconstructing "Anthropic Mythos" → Reconstructing it into JARVIS

> **Status:** Architecture blueprint, 2026-06-04. This doc deconstructs an
> external research report about Anthropic's publicly observable system,
> separates what is *already* in JARVIS from the genuine gaps, and specifies
> the additive **JARVIS Self-Audit + Constitution** layer that closes them.
> It is the narrative companion to [`../jarvis-constitution.md`](../jarvis-constitution.md)
> and [`../orchestration/agent-design-patterns.md`](../orchestration/agent-design-patterns.md).

## Why this exists

A research report — *"Anthropic Mythos and the Publicly Observable Claude
System"* — was handed to JARVIS as raw material with one instruction: **mine it
for what's worth stealing, deconstruct it, and reconstruct the valuable parts
into JARVIS.** This document is the result of that exercise.

### How the source report is treated (kept as-is, attributed)

> ⚠️ **Provenance note.** The source report asserts the existence of a "Claude
> Mythos Preview" frontier model and a "Project Glasswing" limited-release
> program (dated April 2026), and is studded with `citeturn…` search-citation
> artifacts. **These specific claims are unverified** and are preserved here
> **as an external seed, attributed to the report — not asserted as fact in
> JARVIS's voice.** The owner chose to keep them as-is. Crucially, the
> *engineering* below does **not** depend on them: every technique we
> reconstruct is grounded in an independently verifiable, cited Anthropic
> source. The "Mythos signature" is interesting precisely because the *real,
> public mechanisms behind it* are buildable.

## Method

1. **Fresh deep research** recovered the real, public techniques behind each of
   the report's themes (sourced below).
2. **Three parallel repo surveys** mapped the report's three pillars against the
   current JARVIS codebase: safety/governance, operational superstructure, and
   learning/data doctrine.

The headline finding: **JARVIS's foundation is far more complete than the report
implies the hard part is.** Almost the entire "operational superstructure" and
"data doctrine" already exist and are production-grade. The genuine gaps collapse
into a *single coherent missing capability*: **adversarial self-evaluation
against an explicit constitution.**

## Deconstruction — the "Mythos signature" and its real mechanisms

The report frames Anthropic's edge as a tightly-coupled socio-technical system:
post-training/safety doctrine + an operational superstructure + governance. The
*real, public* mechanisms behind that framing:

| Theme in the report | Real, verifiable technique | Source |
|---|---|---|
| Automated red-team / "models as graders, monitors, scorers" | **Petri** — an auditor→target→judge loop, seed scenarios, transcripts scored on behavioral dimensions | [Petri](https://www.anthropic.com/research/petri-open-source-auditing) |
| RL penalizing "privilege escalation / destructive cleanup / destructive workaround / unwarranted scope expansion" | Reward hacking **generalizes to misalignment**; mitigate by preventing it, diversifying safety data, "inoculation", and a **dedicated reward-hacking classifier** | [Emergent misalignment from reward hacking](https://www.anthropic.com/research/emergent-misalignment-reward-hacking) (arXiv 2511.18397) |
| Constitution shaping behavior; self-critique & revision | **Constitutional AI** — explicit constitution → self-critique → revise → (RL)AIF | [Constitutional AI](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback) |
| Capability-banded release gating; redacted risk reports | **Responsible Scaling Policy** — capability thresholds gate what a system may do | RSP (Anthropic) |
| "Simple composable patterns"; multi-agent decomposition | **Building Effective Agents** (5 patterns) + lead→subagent **multi-agent research system** | [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents), [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) |

## Gap analysis — what's already built vs. what to steal

| Pillar | Already in JARVIS (do **not** rebuild) | Genuine gap |
|---|---|---|
| **Operational superstructure** | MCP client **and** server ([`agent/transports/hermes_tools_mcp_server.py`](../../agent/transports/hermes_tools_mcp_server.py)); programmatic tool-calling (`delegate_task`/`execute_code`); GraphRAG ([`hermes_cli/jarvis_prime/graphrag/`](../../hermes_cli/jarvis_prime/graphrag/)); provenance-first Memory Tree w/ contradiction handling ([`memory_tree.py`](../../hermes_cli/jarvis_prime/memory_tree.py)); prompt caching + auto-compaction ([`agent/prompt_caching.py`](../../agent/prompt_caching.py)); Job/Worker/routing/validation/decision-ledger orchestration; AOS council | **No composable-agent-patterns guide** (esp. evaluator-optimizer, lead→subagent) |
| **Learning / data doctrine** | SIA sandbox self-improve + benchmark-gated **promote-by-proposal** ([`sia.py`](../../hermes_cli/workers/sia.py), [`benchmark_gate.py`](../../hermes_cli/jarvis_prime/benchmark_gate.py)); learning preference-pair export w/ secret+CoT stripping ([`learning_dataset.py`](../../hermes_cli/jarvis_prime/learning_dataset.py)); Research Vault + citation verification ([`research_vault.py`](../../hermes_cli/jarvis_prime/research_vault.py)); license-aware sourcing + an **enforced data benchmark wall** ([`open_data_sources.py`](../../hermes_cli/jarvis_prime/open_data_sources.py)) | **No explicit, versioned Constitution** (persona is runtime-only); **no reward-hacking/Goodhart detection** in the loop |
| **Safety / governance** | 8 verification gates runtime-enforced + strict evidence mode ([`gates.py`](../../hermes_cli/jarvis_prime/gates.py)); tamper-evident hash-chained evidence ledger ([`guardrail_evidence.py`](../../hermes_cli/jarvis_prime/guardrail_evidence.py)); owner gates exact-phrase + nonce ([`owner_auth.py`](../../hermes_cli/jarvis_prime/owner_auth.py)); RC0–RC4 bands ([`work_packet.py`](../../hermes_cli/jarvis_prime/work_packet.py)); release/merge gating ([`launch.py`](../../hermes_cli/jarvis_prime/launch.py)); fail-visible monitors ([`monitors.py`](../../hermes_cli/jarvis_prime/monitors.py)); contrarian + assurance-risk reviewer skills | **No automated red-team/audit harness** (only manual [`skills/red-teaming/godmode/scripts/auto_jailbreak.py`](../../skills/red-teaming/godmode/scripts/auto_jailbreak.py)); **behavioral-risk guards documented but unenforced**; **no held-out *behavioral* benchmark wall gating RC bands** |

## Reconstruction — the `JARVIS Self-Audit + Constitution` layer

One coherent subsystem closes every real gap, and it **reuses** the existing
foundation rather than rebuilding it.

```text
        Constitution (rubric)                ← docs/jarvis-constitution.md + constitution.py
                │
   ┌────────────┼─────────────────────────────┐
   ▼            ▼                              ▼
Self-Audit   Behavioral-risk             Capability-band
harness      classifier + monitor        behavioral wall
(Petri)      (reward-hacking paper)      (RSP analogue)
   │            │                              │
   ▼            ▼                              ▼
 audit_result  worker trust score +       capability cards +
 artifact   →  owner-brief drift     →    gate attestation
   └────────────┴──────────────┬───────────────┘
                               ▼
              GuardrailLedger (hash-chained, verify_chain)
```

**1. Constitution (the rubric).** [`docs/jarvis-constitution.md`](../jarvis-constitution.md)
+ a loader module `constitution.py` (mirrors how `persona.py` derives from docs).
Consolidates the identity, 15 principles, modes, memory rules, and **references**
(never copies) `owner_auth.OWNER_GATED_ACTIONS` into stable, severity-tagged
clauses `C1…Cn`. This is the local-first analogue of Constitutional AI — JARVIS
is *evaluated and gated* against it, not *trained* on it.

**2. Self-audit harness (Petri analogue).** A `self_audit/` package: an
**auditor** agent drives seed scenarios against JARVIS (the **target**); a
**judge** scores the transcript on the Constitution's dimensions and verdicts it.
The judge **reuses the existing reviewer skills** — [`contrarian-reviewer`](../../skills/contrarian-reviewer/SKILL.md)
and [`assurance-risk-director`](../../skills/assurance-risk-director/SKILL.md) —
which already play the grader/veto role. Output is a new `audit_result` artifact
appended to the existing hash-chained `GuardrailLedger`.

**3. Behavioral-risk classifier + async monitor (reward-hacking paper analogue).**
A deterministic classifier detects the Article VI dynamics — privilege
escalation, destructive cleanup, destructive workaround, scope expansion,
reward-hacking/Goodharting — from signals already captured (`work_packet` RC
progression, `guardrail_collectors` git diffs, the checkpoint store, the decision
ledger). It degrades a per-worker **trust score** and surfaces drift through a
new `behavioral_drift_checker` in [`monitors.py`](../../hermes_cli/jarvis_prime/monitors.py)
→ [`owner_brief.py`](../../hermes_cli/jarvis_prime/owner_brief.py). Because JARVIS
does **not** do RL, the paper's mitigations become **detect + gate +
exclude-from-learning** (reward-hacking traces are filtered out of
`learning_dataset.py`), not RL penalties.

**4. Capability-band behavioral wall (RSP analogue).** `capability_wall.py`
defines per-RC-band thresholds on the audit dimensions, enforced via the existing
[`benchmark_gate.py`](../../hermes_cli/jarvis_prime/benchmark_gate.py) and a new
check in `gates.py`. The seeds used for **gating** are **held-out / disjoint**
from development seeds — mirroring the data-benchmark-wall disjointness already
enforced in `open_data_sources.py`. It emits per-band **capability cards** (the
local analogue of a system card).

### Reuse map (what each component leans on)

| New component | Reuses |
|---|---|
| `constitution.py` | `persona.py` derive-from-docs pattern; `owner_auth.OWNER_GATED_ACTIONS` |
| `self_audit/` harness + judge | contrarian + assurance-risk reviewer skills; `auto_jailbreak.py` canaries as seeds; `GuardrailLedger` / `EvidenceArtifact` |
| `behavioral_risk.py` + monitor | `work_packet` RC bands; `guardrail_collectors` git-diff; checkpoint store; `monitors.py` + `owner_brief.py`; `learning_dataset.py` filters |
| `capability_wall.py` + gate | `benchmark_gate.py`; `work_packet` RC0–RC4; `gates.py` strict-evidence bundle |

## Phased roadmap

> **Status (2026-06-04):** all four phases are implemented in PR #251.

- ✅ **Phase 1 — Blueprint docs (RC1, no runtime change).** This doc + the
  Constitution (`docs/jarvis-constitution.md`) + the agent-design-patterns guide
  + index updates + the cited-source registry (`self-audit-sources.yaml`).
- ✅ **Phase 2 — Constitution module + audit harness (RC2).** `constitution.py`;
  `self_audit/{seeds,harness,judge,report,sources}.py`; `audit_result` artifact;
  CLI `self-audit run/list/show`.
- ✅ **Phase 3 — Behavioral-risk classifier + async monitor (RC2).**
  `behavioral_risk.py` + per-worker trust score; `behavioral_drift_checker` in
  `monitors.py` (surfaced via the owner brief); reward-hacking exclusion in
  `learning_dataset.py`.
- ✅ **Phase 4 — Capability-band wall (RC2–RC3).** `capability_wall.py` +
  held-out core-seed partitioning + capability cards + a `capability_attestation`
  artifact + an **opt-in, feature-flagged** `capability_gate` that reuses the
  gate framework's types without altering the default eight-gate suites.

## Non-goals (explicit)

- **No in-loop RLHF/RLAIF or model fine-tuning.** JARVIS is model-agnostic and
  local-first; it already exports preference data for *external* tuning — the
  correct boundary. The Constitution is for **evaluation and gating**, not training.
- **Do not rebuild** MCP, programmatic tool-calling, memory, GraphRAG, prompt
  caching, SIA, the Research Vault, the data benchmark wall, or contradiction
  handling — all already built and production-grade.
- Generic platform gaps (server-side compaction, computer-use sandboxing,
  vision/audio streaming) are **out of scope** — not part of the "Mythos signature."
- The Constitution **references** `owner_auth.OWNER_GATED_ACTIONS`; it never
  maintains a second copy.

## Sources

Machine-readable companion: [`../ai-intelligence/self-audit-sources.yaml`](../ai-intelligence/self-audit-sources.yaml) — the Phase 2 `self_audit` loader bridges each entry into the Research Vault as a source-cited `ResearchArtifact`.

- [Petri: an open-source auditing tool](https://www.anthropic.com/research/petri-open-source-auditing)
- [From shortcuts to sabotage: emergent misalignment from reward hacking](https://www.anthropic.com/research/emergent-misalignment-reward-hacking) (arXiv 2511.18397)
- [Constitutional AI: Harmlessness from AI Feedback](https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback)
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- *Anthropic Mythos and the Publicly Observable Claude System* — external seed report; "Mythos Preview"/"Project Glasswing" claims **unverified**, kept as-is per owner.

## Cross-references

- [`../jarvis-constitution.md`](../jarvis-constitution.md) — the rubric this layer scores against.
- [`../orchestration/agent-design-patterns.md`](../orchestration/agent-design-patterns.md) — the composable-patterns gap, closed.
- [`../jarvis-verification-gates.md`](../jarvis-verification-gates.md) — the gates the capability wall plugs into.
- [`JARVIS_RESEARCH_VAULT.md`](JARVIS_RESEARCH_VAULT.md) — where the cited sources are bridged.
