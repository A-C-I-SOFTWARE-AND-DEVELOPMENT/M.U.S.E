# AOS Sub-Agent Registry — Complete

> **Generated:** 2026-05-24 from hazmat division-doc extraction + Hermes worker profiles + R-code personas + HazMat product roles.
> See `AOS_AGENT_REGISTRY_COMPLETE.md` for top-level agents and `AOS_FULL_SOURCE_INVENTORY.md` for the file index.
>
> Source extraction methods used:
> - **Division sub-agents** — extracted from `### Name` headings and `**Name**` bold leads inside the 11 hazmat division docs at `recovered-agent-sources/from-hazmat-command/docs/agents/0[0-9]-*.md`.
> - **Hermes orchestration workers** — the 4 worker-profile templates in `docs/orchestration/workers/`.
> - **Hermes Python runtime workers** — runtime agent profiles in `enterprise/` and `agent/`.
> - **R-code personas** — judgement lenses named in hazmat `AGENTS.md` § "Taxonomy".
> - **HazMat product roles** — the 5 role tokens carrier_admin / safety_manager / dispatcher / driver / solo_driver.
>
> Confidence labels:
> - `DIRECTLY RECOVERED` — name appears verbatim in a markdown spec heading.
> - `RECONSTRUCTED FROM CONTEXT` — name extracted from frontmatter or Python module structure.
> - `PERSONA` — judgement-lens label, not a runtime agent.
> - `PRODUCT-ROLE` — a role in the HazMat Command application (not an autonomous agent).

**Total sub-agent entries:** 108 (division: 79 · worker templates: 4 · Python runtime: 13 · R-personas: 7 · product roles: 5)

## A. Executive / Operator Layer

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`CEO / GM Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `ceo-gm-agent`.
- **`Chief of Staff Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `chief-of-staff-agent`.
- **`General Counsel Orchestrator`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `general-counsel-orchestrator`.
- **`HMC Chief Orchestrator`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `hmc-chief-orchestrator`.

## B. Product Strategy Layer

## C. Software Architecture Layer

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Backend / API Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `backend-api-engineer`.
- **`Data / SoR Migration Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `data-sor-migration-engineer`.
- **`Frontend Product Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `frontend-product-engineer`.
- **`Integration Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `integration-engineer`.
- **`Mobile / Capacitor Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `mobile-capacitor-engineer`.
- **`OCR / Document Intelligence Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `ocr-document-intelligence-engineer`.
- **`Pilot Demo Architect`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `pilot-demo-architect`.
- **`Principal HazMat Software Architect`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `principal-hazmat-software-architect`.

## D. Security / Compliance Layer (Security)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Principal Security Architect`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `principal-security-architect`.
- **`Security / Authz Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `security-authz-engineer`.
- **`Security Standards Research Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `security-standards-research-agent`.
- **`Supply Chain Security Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `supply-chain-security-agent`.
- **`Threat Modeling Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `threat-modeling-agent`.

## D2. Security / Compliance Layer (Compliance)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`49 CFR Regulatory Research Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `49-cfr-regulatory-research-agent`.
- **`Canadian TDG Research Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `canadian-tdg-research-agent`.
- **`Chief Safety & Compliance Officer (CSCO)`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `chief-safety-compliance-officer-csco`.
- **`Compliance Engine Engineer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `compliance-engine-engineer`.
- **`Compliance Evidence Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `compliance-evidence-agent`.
- **`Enterprise Procurement Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `enterprise-procurement-agent`.
- **`PHMSA / ERG Source Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `phmsa-erg-source-agent`.
- **`Procurement / Vendor Terms Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `procurement-vendor-terms-agent`.

## E. Psychology / UX / Behavior Layer (Psychology)

## E2. Psychology / UX / Behavior Layer (UX)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Accessibility / Human Factors Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `accessibility-human-factors-agent`.
- **`Practitioner Friction Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `practitioner-friction-agent`.
- **`UX/UI Trust Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `ux-ui-trust-agent`.

## F. QA / Release / Testing Layer (QA)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Citation Integrity Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `citation-integrity-agent`.
- **`Dissent / Challenge Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `dissent-challenge-agent`.
- **`Doc Freshness Auditor`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `doc-freshness-auditor`.
- **`Independent QA / V&V Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `independent-qa-v-v-agent`.
- **`Legal Consistency Auditor`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `legal-consistency-auditor`.
- **`Negative / Fuzz Test Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `negative-fuzz-test-agent`.
- **`Postmortem / Lessons Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `postmortem-lessons-agent`.

## F2. QA / Release / Testing Layer (Release)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Incident Readiness Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `incident-readiness-agent`.
- **`Launch Campaign Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `launch-campaign-agent`.
- **`Pilot Program Manager`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `pilot-program-manager`.
- **`Pilot Readiness Judge`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `pilot-readiness-judge`.
- **`Release Engineering Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `release-engineering-agent`.

## G. Data / Memory / Knowledge Layer (Memory)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Agent OS Librarian`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `agent-os-librarian`.
- **`Artifact Registry Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `artifact-registry-agent`.
- **`Prompt Evolution Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `prompt-evolution-agent`.
- **`Skill Library Manager`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `skill-library-manager`.
- **`Support Knowledge Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `support-knowledge-agent`.

## G2. Data / Memory / Knowledge Layer (Research)

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Chief Research Analyst`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `chief-research-analyst`.
- **`Competitor Intelligence Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `competitor-intelligence-agent`.
- **`Contradiction Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `contradiction-agent`.

## H. Claude Code / Codex / Developer Workflow Layer (Claude Code)

## H2. Claude Code / Codex / Developer Workflow Layer (Codex)

## I. HazMat Command-Specific Layer

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Dispatcher Workflow Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `dispatcher-workflow-agent`.
- **`Driver Workflow Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `driver-workflow-agent`.
- **`HazMat Market Positioning Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `hazmat-market-positioning-agent`.
- **`Safety Manager Workflow Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `safety-manager-workflow-agent`.

## J. Nourish-Specific Layer

## K. Hermes-Specific Skills Layer

## K2. Business / Commercial / Legal Layer

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`ASO / SEO & Store Conversion Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `aso-seo-store-conversion-agent`.
- **`App Store & Platform Policy Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `app-store-platform-policy-agent`.
- **`B2B Sales Enablement Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `b2b-sales-enablement-agent`.
- **`Buyer Objection Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `buyer-objection-agent`.
- **`Case Study Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `case-study-agent`.
- **`Chief Commercial Officer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `chief-commercial-officer`.
- **`Commercial Market Research Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `commercial-market-research-agent`.
- **`Contract Drafting Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `contract-drafting-agent`.
- **`Customer Success Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `customer-success-agent`.
- **`DPA / Subprocessor Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `dpa-subprocessor-agent`.
- **`Enterprise Buyer Persona Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `enterprise-buyer-persona-agent`.
- **`Field Feedback Analyst`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `field-feedback-analyst`.
- **`IP & Open Source Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `ip-open-source-agent`.
- **`Packaging & Entitlements Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `packaging-entitlements-agent`.
- **`Partnership Strategy Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `partnership-strategy-agent`.
- **`Pricing Science Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `pricing-science-agent`.
- **`Privacy Counsel Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `privacy-counsel-agent`.
- **`Product Counsel Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `product-counsel-agent`.

## L. Experimental / Unknown / Needs Review

### Division sub-agents (hazmat-command `docs/agents/0[0-9]-*.md`)

- **`Agent Performance Evaluator`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `agent-performance-evaluator`.
- **`Chief Product Officer`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `chief-product-officer`.
- **`Claims Substantiation Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `claims-substantiation-agent`.
- **`Evaluator-optimizer loop`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `evaluator-optimizer-loop`.
- **`Instrumentation Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `instrumentation-agent`.
- **`Integration Captain Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `integration-captain-agent`.
- **`Orchestrator-worker swarm`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `orchestrator-worker-swarm`.
- **`Risk Controller Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `risk-controller-agent`.
- **`SRE / Reliability Agent`** — sub-agent named inside the corresponding hazmat division doc. Confidence: `DIRECTLY RECOVERED`. Slug: `sre-reliability-agent`.

## H+. Hermes Orchestration Worker-Profile Templates (cross-category)

| Worker | Source file | Description |
| --- | --- | --- |
| **`claude-code-worker`** | `docs/orchestration/workers/claude-code-worker.md` | Claude Code worker profile — the Hermes orchestration adapter that delegates implementation work to Claude Code sub-sessions. |
| **`codex-worker`** | `docs/orchestration/workers/codex-worker.md` | Codex worker profile — bounded-implementation adapter that runs Codex Task Packets. |
| **`aider-worker`** | `docs/orchestration/workers/aider-worker.md` | Aider worker profile — adapter for the Aider CLI implementation tool. |
| **`goose-worker`** | `docs/orchestration/workers/goose-worker.md` | Goose worker profile — adapter for the Goose CLI implementation tool. |

## H++. Hermes Python Runtime Worker Profiles (RECONSTRUCTED FROM CONTEXT)

| Module | Source file | Description |
| --- | --- | --- |
| **`enterprise.adapters.cs`** | `enterprise/adapters/cs.py` | Customer-service runtime adapter inside the enterprise-council Hermes skill. |
| **`enterprise.adapters.finance`** | `enterprise/adapters/finance.py` | Finance runtime adapter. |
| **`enterprise.adapters.hr`** | `enterprise/adapters/hr.py` | HR runtime adapter. |
| **`enterprise.adapters.ops`** | `enterprise/adapters/ops.py` | Operations runtime adapter. |
| **`enterprise.adapters.sales`** | `enterprise/adapters/sales.py` | Sales runtime adapter. |
| **`enterprise.council`** | `enterprise/council.py` | Enterprise-council orchestration runtime — dispatches the 5 leaves above plus judge.py and monitor.py. |
| **`enterprise.judge`** | `enterprise/judge.py` | Judge runtime — validates every leaf result against the schema and policy taxonomy before the orchestrator integrates it. |
| **`enterprise.monitor`** | `enterprise/monitor.py` | Monitor runtime — reads the post-run audit trail and emits improvement proposals into the Hermes drafts lane. |
| **`enterprise.audit`** | `enterprise/audit.py` | Audit-trail runtime for the enterprise council. |
| **`enterprise.policy`** | `enterprise/policy.py` | Policy taxonomy enforcement runtime. |
| **`enterprise.secrets`** | `enterprise/secrets.py` | Secure-by-construction credential retrieval runtime (the fetch_secret(...) contract). |
| **`agent.codex_runtime`** | `agent/codex_runtime.py` | Top-level Hermes Codex runtime worker profile. |
| **`agent.codex_responses_adapter`** | `agent/codex_responses_adapter.py` | Codex response handling adapter. |

## M. R-Code Personas (hazmat AGENTS.md § Taxonomy)

These are judgement-lens labels from the hazmat-command `AGENTS.md` Taxonomy section. They are not runtime agents — they are codes the owner uses to mark which lens authored a sprint planning document.

- **`R1-D`** — Discovery persona (round 1) — judgment lens from the AGENTS.md round-code taxonomy. Confidence: `PERSONA`.
- **`R2-I`** — Inspection persona (round 2). Confidence: `PERSONA`.
- **`R3-O`** — Outline persona (round 3). Confidence: `PERSONA`.
- **`R4-X`** — Cross-check persona (round 4). Confidence: `PERSONA`.
- **`R5-T`** — Tightening persona (round 5). Confidence: `PERSONA`.
- **`R5-U`** — Underwrite persona (round 5). Confidence: `PERSONA`.
- **`R5-V`** — Verify persona (round 5). Confidence: `PERSONA`.

## N. HazMat Command Product Roles (RBAC roles, not autonomous agents)

Included for completeness; these are the human end-user roles enforced by the HazMat Command RBAC layer, not autonomous council members.

- **`carrier_admin`** — HazMat Command product role — carrier administrator with full fleet authority. Confidence: `PRODUCT-ROLE`.
- **`safety_manager`** — Product role — safety manager with rule-engine override authority and audit access. Confidence: `PRODUCT-ROLE`.
- **`dispatcher`** — Product role — operational dispatcher for loads and pre-trip workflows. Confidence: `PRODUCT-ROLE`.
- **`driver`** — Product role — driver running loads, shipping papers, pre-trip checklists. Confidence: `PRODUCT-ROLE`.
- **`solo_driver`** — Product role — independent driver who is also their own admin. Confidence: `PRODUCT-ROLE`.
