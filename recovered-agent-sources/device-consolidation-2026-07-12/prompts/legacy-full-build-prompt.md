# MASTER CLAUDE CODE PROMPT — HERMES / JARVIS PRIME 100% PERSONAL BUILD

You are Claude Code working inside the repo:

`A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent`

Primary branch/PR context:

- Current draft PR: `#175`
- Branch: `jarvis/audit-memory-companion-2026-05-28`
- Base branch: `main`
- Canonical backend: Hermes
- Canonical feature identity: JARVIS Prime

## 0. Mission

Build Hermes/JARVIS Prime to the strongest practical personal-use completion state possible from the current repo, without hallucinating, without bypassing owner gates, and without pretending unfinished systems are complete.

The target product is:

> JARVIS Prime: Jeremiah Echerd’s local-first, owner-authorized, memory-backed, model-routed AI operating partner inside Hermes. It can plan, research, code, review, remember, monitor, brief, operate across desktop/Android/mobile surfaces, and prepare bounded action packets for personal device control — while preserving provenance, owner authority, reversibility, and verification.

The build must make JARVIS the obvious main feature in code, docs, CLI, tests, Android companion surfaces, and workflow. It must be usable by Jeremiah personally, not just described in markdown.

## 1. Non-negotiable rules

1. Do not hallucinate. If a feature is missing, mark it missing and build it or create a precise implementation packet.
2. Do not claim “100% complete” unless every acceptance gate in this prompt passes.
3. Do not make Base44 the backend. For this task, ignore Base44 as a runtime target. Hermes is the backend. Existing Base44 sync/cockpit references may remain, but do not build a Base44 replacement for Hermes.
4. Do not remove owner gates.
5. Personal-use owner authorization may reduce repeated permission friction, but irreversible or external actions still require final confirmation.
6. Do not execute real Android accessibility gestures, external posts/messages, purchases, merges, deploys, credential changes, OAuth changes, destructive file operations, or public releases during this task.
7. Do not store secrets, credentials, raw tokens, raw session cookies, private keys, raw voice dumps, raw camera frames, unconsented PII, or chain-of-thought in memory.
8. Do not silently overwrite memory. Use contradiction records and supersession.
9. Memory cites sources; it does not become the source of truth.
10. Builder and reviewer must be separate workers/models for RC2+ changes.
11. Do not copy GPL or incompatible external code. Use clean-room implementation.
12. Do not add heavyweight dependencies unless justified and optional.
13. Do not break existing `hermes`, gateway, model selection, JARVIS CLI, Android, or test behavior.
14. Do not treat vendor benchmark claims as proof. Record them as vendor-reported unless independently verified.
15. Do not leave TODO-only stubs for core JARVIS behavior unless a feature is explicitly moved into a documented future packet.

## 2. First action: audit before editing

Before changing code, run and record:

```bash
git status
git branch --show-current
git rev-parse HEAD
git log --oneline -5
python -m hermes_cli.jarvis_prime --help || true
python -m compileall -q hermes_cli/jarvis_prime
pytest -q tests/test_jarvis_prime_companion_presence.py tests/test_jarvis_prime_memory_tree.py tests/test_jarvis_prime_natural_language_coder.py || true
```

Then inspect the repo end to end. At minimum read:

```text
README.md
pyproject.toml
package.json
docs/README.md
docs/jarvis-prime-operating-system.md
docs/jarvis-*.md
docs/orchestration/README.md
docs/mobile/mobile-app-guide.md
docs/voice/voice-first-user-guide.md
docs/security/private-local-security-guide.md
docs/ai-intelligence/model-routing-policy.md
docs/ai-intelligence/oss-model-catalog.md
docs/ai-intelligence/oss-model-catalog.yaml
config/model-catalog.yaml
hermes_cli/jarvis_prime/runtime.py
hermes_cli/jarvis_prime/__main__.py
hermes_cli/jarvis_prime/memory.py
hermes_cli/jarvis_prime/gates.py
hermes_cli/jarvis_prime/owner_auth.py
hermes_cli/jarvis_prime/research.py
hermes_cli/jarvis_prime/router.py
hermes_cli/jarvis_prime/self_update.py
hermes_cli/jarvis_prime/companion_presence.py
hermes_cli/jarvis_prime/memory_tree.py
hermes_cli/jarvis_prime/natural_language_coder.py
hermes_cli/oss_model_brain.py
hermes_cli/jarvis_prime/model_brain.py
gateway/jarvis_local_http.py
apps/android/README.md
apps/android/app/src/main/AndroidManifest.xml
apps/android/app/src/main/java/com/aci/hermes/service/JarvisAccessibilityService.kt
apps/android/app/src/main/java/com/aci/hermes/service/JarvisOverlayService.kt
apps/android/app/src/main/java/com/aci/hermes/service/VoiceLoopService.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/JarvisChatScreen.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/chat/JarvisChatViewModel.kt
apps/android/app/src/main/java/com/aci/hermes/ui/screens/live/*
apps/android/app/src/main/java/com/aci/hermes/data/automation/*
tests/test_jarvis_prime_*.py
tests/test_oss_model_brain.py
tests/test_model_catalog.py
tests/gateway/test_jarvis_local_http.py
apps/android/app/src/test/java/com/aci/hermes/**/*.kt
```

If a listed file does not exist, record that. Do not invent it.

## 3. Research before implementation

Before implementing, research current official docs and primary sources for anything that may have changed, especially:

- Claude Code memory, subagents, hooks, permissions, and skills.
- Claude/Anthropic model names and model capabilities.
- OpenAI/Codex agent, background, eval, and approval patterns.
- Current OSS/local model serving docs for Qwen, DeepSeek, Kimi, GLM, vLLM, SGLang, Ollama, llama.cpp.
- OWASP LLM Top 10.
- NIST AI RMF and NIST GenAI Profile.

Record the results in:

`docs/jarvis_research/JARVIS_CURRENT_RESEARCH_DOSSIER.md`

Rules for this research file:

- Cite official/primary sources.
- Separate verified facts from recommendations.
- Mark vendor benchmark claims as vendor-reported.
- Do not download copyrighted books or private materials.
- Do not add private API keys, tokens, or credentials.

## 4. Architecture target

Implement toward this three-plane architecture:

### Control plane

Hermes / JARVIS Prime owns:

- owner gates
- emergency stop
- mode classification
- routing
- model selection
- work packet creation
- job graph handoff
- verification gates
- self-update proposals
- approval inbox data
- audit ledger
- daily owner brief

### Cognition plane

JARVIS Memory OS owns:

- working memory
- session memory
- durable memory
- Memory Tree
- Research Vault
- Decision Vault
- Skill Vault
- Code Practice Vault
- contradiction handling
- freshness tracking
- source trust
- retrieval quality
- context packing / TokenJuice

### Execution plane

Workers execute bounded work only:

- Claude Code builder
- Codex reviewer / bounded fix worker
- local tests
- GitHub PR publisher after approval
- research fetchers
- Termux/Android action broker after permission and final confirmation
- local OSS model experiments after benchmark setup

## 5. Required build areas

Complete all sections below as far as the repo architecture permits.

---

# A. JARVIS identity and repo presentation

## Goal

Hermes should clearly present JARVIS Prime as the main personal AI operating feature for Jeremiah’s build.

## Required work

1. README must accurately describe:
   - JARVIS Prime activation.
   - Hermes as backend.
   - AOS Council / routing.
   - builder/reviewer workflow.
   - memory and research vault.
   - Android/Termux/Slack/voice surfaces.
   - owner gates and emergency stop.
   - local OSS model option.
2. Docs must not overclaim “fully autonomous” or “unrestricted.”
3. Any existing Base44 references must be clearly cockpit/sync only, not backend.
4. Add or update:
   - `docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md`
   - `docs/jarvis_architecture/JARVIS_PERSONAL_USE_COMPLETION_STATUS.md`
   - `docs/jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md`

## Acceptance

- A user can read README + the system overview and understand exactly what JARVIS is, what it can do, what it cannot yet do, and how to run it.
- No false “100% autonomous” claims.

---

# B. Memory Tree / JARVIS Memory OS

## Goal

Replace the minimal `memory_tree.py` with a production-quality clean-room Memory Tree that complements, not breaks, existing `memory.py`.

## Required public API

Implement in `hermes_cli/jarvis_prime/memory_tree.py`:

```text
MemoryNamespace
MemoryLayer
SourceTrust
SensitivityClass
ApprovalState
ContradictionStatus
MemorySource
MemoryChunk
MemoryNode
ContradictionReport
MemoryWritePolicy
MemorySearchResult
ContextPack
MemoryTreeStore
estimate_tokens
canonicalize_text
stable_memory_id
```

## Required behavior

1. Three layers:
   - `working`
   - `session`
   - `durable`

2. Durable entries must include:
   - stable id
   - namespace
   - layer
   - title
   - summary
   - text or chunk refs
   - source artifact pointers
   - source URI or repo path
   - source trust tier
   - confidence
   - sensitivity class
   - approval state
   - freshness due date
   - contradiction status
   - supersedes
   - superseded_by
   - created_at
   - updated_at
   - tags

3. Write policy:
   - reject obvious secret-like text
   - reject chain-of-thought storage
   - reject raw credentials/tokens/private keys/session cookies
   - reject durable writes below confidence threshold unless owner-approved
   - require provenance for durable facts
   - allow owner-approved durable decisions
   - downgrade temporary emotional state to session/working
   - support dry-run validation before write

4. Contradictions:
   - new facts do not silently overwrite old facts
   - conflicting high-confidence facts create a `ContradictionReport`
   - both records become contested until resolved
   - `resolve_contradiction(...)` records resolution and supersession
   - unresolved contested memory excluded from default context packs

5. Retrieval:
   - deterministic lexical retrieval
   - rank by namespace, term overlap, trust, confidence, recency/freshness, approval state
   - support `search(...)`
   - support `context_pack(query, token_budget, namespaces=None, include_contested=False)`
   - include source lines/artifacts in context pack output

6. Persistence:
   - default path: `~/.hermes/jarvis_prime/memory_tree.jsonl`
   - caller-supplied path for tests
   - atomic writes
   - owner-only permissions where supported
   - tolerate malformed lines with diagnostics
   - no network calls

7. Exports:
   - `to_dict()` / `from_dict()`
   - `export_markdown(namespace=None)`
   - `export_audit_cards(namespace=None)`

8. Integration:
   - do not break existing `MemoryStore`
   - optionally expose Memory Tree from JARVIS CLI
   - no mandatory external database

## Tests

Expand `tests/test_jarvis_prime_memory_tree.py` to cover:

- working/session/durable writes
- durable provenance requirement
- low-confidence rejection
- owner-approved decisions
- sensitive content rejection
- temporary-emotion downgrade
- contradiction report creation
- contradiction resolution
- supersession
- search ranking
- default exclusion of contested memory
- context pack source inclusion
- token budget behavior
- markdown export
- audit cards export
- JSONL persistence/reload
- malformed-line tolerance
- no silent overwrite

---

# C. Natural-language coder / bounded work packetizer

## Goal

Replace the minimal `natural_language_coder.py` with a complete clean-room packetizer that converts plain-English requests into bounded, reviewable, gate-compatible work packets. It must never execute.

## Required public API

Implement in `hermes_cli/jarvis_prime/natural_language_coder.py`:

```text
CodingIntent
RiskClass
WorkerRole
OwnerGate
ModelLaneHint
RouteDecision
CodingWorkPacket
PacketValidationFinding
PacketValidationResult
classify_intent(prompt, context=None)
route_request(prompt, context=None)
parse_owner_gate_keywords(prompt)
build_work_packet(prompt, repo_root='.', branch_prefix='jarvis', allowed_files=None, forbidden_files=None, context=None)
validate_work_packet(packet)
render_packet_markdown(packet)
```

## Intent classes

Support:

- research
- audit
- implement
- review
- test
- document
- refactor
- model_routing
- memory
- android
- avatar_presence
- device_action
- release
- security
- unknown

## Risk classes

- RC0: read-only/summarize
- RC1: docs/tests/local-only narrow code
- RC2: implementation/refactor with code changes
- RC3: device action, auth/security, external communication, merge/deploy/publish, billing/spend, destructive file ops
- RC4 or blocked: bypass-owner-gate, credential exfiltration, harmful/illegal requests, destructive production actions

## Owner gates

Detect and emit:

- merge_main
- deploy
- publish
- external_message
- purchase_or_spend
- oauth_or_credentials
- security_sensitive_change
- destructive_file_operation
- android_accessibility_gesture
- app_store_or_public_release
- explicit_or_mature_content_confirmation where relevant outside coding

## Work packet fields

`CodingWorkPacket` must include:

- mission
- normalized_intent
- risk_class
- repo_root
- branch
- allowed_files
- forbidden_files
- non_goals
- assumptions
- acceptance_criteria
- verification_plan
- rollback_plan
- owner_gated_actions
- primary_worker
- reviewer_worker
- model_lane_hint
- evidence_required
- generated_at
- `to_dict()`
- `to_gate_packet()` compatible with `run_gate_summary()`

## Routing model

- Builder default: Claude Code / Sonnet lane
- Reviewer default: Codex or different model-family reviewer
- High-risk reviewer: Opus/GPT-level independent review where available
- OSS/local model lanes experimental until measured
- Unknown/high-risk requests become draft/plan/review packets, not execution packets

## Validation

`validate_work_packet(packet)` must fail if:

- branch missing or unsafe
- allowed_files empty for write intent
- owner-gated actions present but risk class below RC3
- builder and reviewer are same worker for RC2+
- rollback plan missing for write intent
- acceptance criteria missing
- verification plan missing
- mission empty
- branch targets main/master directly
- forbidden files overlap allowed files in dangerous ways

Return structured findings, not only boolean.

## Tests

Expand `tests/test_jarvis_prime_natural_language_coder.py` to cover:

- every intent classification
- owner-gated keyword extraction
- RC3 route for Android/accessibility/external actions
- blocked routing for bypass-owner-gate prompts
- branch slug safety
- allowed/forbidden files
- builder/reviewer separation
- `to_dict()`
- `to_gate_packet()` passes planning gate when complete
- validation catches missing rollback/no tests/empty scope/same builder-reviewer
- markdown rendering includes mission/risk/owner gates/verification/rollback
- no execution side effects

---

# D. Research Vault

## Goal

Make Research Vault a first-class JARVIS feature for papers, docs, OSS practices, model notes, courses, and evidence.

## Required files

Add:

- `hermes_cli/jarvis_prime/research_vault.py`
- `tests/test_jarvis_prime_research_vault.py`
- `docs/jarvis_architecture/JARVIS_RESEARCH_VAULT.md`

## Required records

Support clean dataclasses/enums for:

- ResearchArtifact
- SourceType
- EvidenceStrength
- ModelBenchmarkCard
- OSSPracticeCard
- CourseArtifactCard
- SkillProposalCard

## Required behavior

- add artifact from URL/path/manual citation
- summarize only from stored citation text or user-provided excerpt
- mark source type and evidence strength
- record freshness due date
- connect artifacts to Memory Tree source pointers
- export audit cards
- do not download copyrighted/private materials
- no network required for tests

## CLI

Add optional:

```bash
python -m hermes_cli.jarvis_prime research add ...
python -m hermes_cli.jarvis_prime research list --json
python -m hermes_cli.jarvis_prime research export-markdown
```

---

# E. TokenJuice context compiler

## Goal

Create a deterministic context compiler that packs task-relevant repo/memory/research/gate information into a bounded prompt packet.

## Required files

Add:

- `hermes_cli/jarvis_prime/tokenjuice.py`
- `tests/test_jarvis_prime_tokenjuice.py`
- `docs/jarvis_architecture/TOKENJUICE_CONTEXT_COMPILER.md`

## Required behavior

- input: mission, work packet, memory tree, research vault artifacts, repo paths
- output: ordered context sections
- enforce token budget
- include sources/provenance
- deprioritize stale/contested memory
- never include secrets
- deterministic output for tests

---

# F. Model router / scorecards / OSS models

## Goal

Complete model routing as evidence-backed, not preference-backed.

## Inspect first

- `hermes_cli/oss_model_brain.py`
- `hermes_cli/jarvis_prime/model_brain.py`
- `config/model-catalog.yaml`
- `docs/ai-intelligence/oss-model-catalog.yaml`
- tests for model catalog

## Required work

1. Ensure model catalog includes:
   - frontier lane
   - Claude/Anthropic lane
   - OpenAI/Codex lane
   - Google/Gemini lane
   - local OSS lane
   - Qwen coder lane
   - DeepSeek lane
   - Kimi lane
   - GLM lane
   - generic OpenAI-compatible local endpoint lane

2. Add or finish:
   - `hermes_cli/jarvis_prime/model_scorecard.py`
   - `tests/test_jarvis_prime_model_scorecard.py`
   - `docs/ai-intelligence/JARVIS_MODEL_ROUTER_SCORECARD.md`

3. Scorecard fields:
   - model name
   - provider
   - task type
   - risk class
   - tokens in/out
   - latency
   - cost if known
   - tests passed/failed
   - reviewer findings
   - owner corrections
   - hallucination corrections
   - accepted diff rate
   - repeated error count
   - memory usefulness
   - created_at

4. CLI:
   - list models
   - recommend for task
   - emit local endpoint packet with no sign-in assumption
   - record scorecard after job

5. Hard rule:
   - OSS/local models are “wired and ready” only as config/local endpoint packets unless weights/server are actually installed.
   - Do not claim a local model is running unless a smoke request succeeds.

---

# G. Approved proposal executor

## Goal

Move self-update proposals from approve/reject-only into safe execution packet generation. Do not auto-merge.

## Required files

Add or update:

- `hermes_cli/jarvis_prime/proposal_executor.py`
- `tests/test_jarvis_prime_proposal_executor.py`
- `docs/jarvis_architecture/APPROVED_PROPOSAL_EXECUTOR.md`

## Required behavior

Approved proposal executor should:

- read approved proposals
- create a bounded coding packet
- create branch name recommendation
- generate exact test commands
- generate rollback plan
- optionally write packet artifact
- never merge/deploy/publish
- require owner approval before GitHub writes unless explicitly invoked in draft-only local mode
- integrate with `natural_language_coder`

---

# H. Continuous monitors and daily owner brief

## Goal

Create fail-visible monitors and a daily owner brief.

## Required files

Add:

- `hermes_cli/jarvis_prime/monitors.py`
- `hermes_cli/jarvis_prime/owner_brief.py`
- `tests/test_jarvis_prime_monitors.py`
- `tests/test_jarvis_prime_owner_brief.py`
- `docs/jarvis_architecture/CONTINUOUS_MONITORS_AND_OWNER_BRIEF.md`

## Monitor classes

Support:

- repo state monitor
- open PR monitor
- failing tests monitor
- stale docs monitor
- memory contradiction monitor
- skill proposal monitor
- model failure monitor
- Android capability monitor

## Required behavior

- read-only by default
- per-source last-success timestamp
- per-source failure count
- blind-spot detection
- severity classification
- daily brief:
  - what changed
  - what matters
  - what needs approval
  - what is blocked
  - what JARVIS learned
  - monitor coverage attestation

---

# I. Android companion / avatar / personal action authority

## Goal

Make Android companion and avatar behavior safe, explicit, test-covered, and personal-use ready where possible.

## Inspect existing Android files first

Do not rewrite blindly. Work with the current Android structure.

## Required work

1. Ensure avatar presence:
   - customizable avatar profile
   - mini/corner/full modes
   - living state machine
   - animation separate from real device actions
   - permission education
   - emergency stop visible

2. Ensure personal action authority:
   - standing owner-authorized profile may exist
   - Android system permissions remain technical gates
   - external post/send/purchase/security/destructive actions pause before final irreversible step
   - actions return:
     - direct_execute
     - blocked_missing_capability
     - requires_final_confirmation
     - blocked_by_policy

3. Add/verify Kotlin tests:
   - no action without Android permission/capability
   - final confirmation for irreversible actions
   - emergency stop blocks execution
   - missing accessibility service blocks gestures
   - avatar animation can run without real gesture

4. Do not request background camera/microphone behavior unless explicitly opted in and documented.

5. Do not add spyware-like behavior.

---

# J. Local HTTP bridge / gateway

## Goal

Make JARVIS callable locally by the Android companion and command surfaces without exposing unsafe execution.

## Inspect

- `gateway/jarvis_local_http.py`
- `tests/gateway/test_jarvis_local_http.py`

## Required behavior

- local-only default bind
- request schema
- owner gate reporting
- emergency stop endpoint
- packetize endpoint
- memory/search endpoint if safe
- no secrets in logs
- no external network exposure by default
- tests for unsafe bind refusal or warning

---

# K. Claude Code project support

## Goal

Add Claude Code helpers only if useful and not disruptive.

## Optional files

Add if repo convention allows:

```text
.claude/agents/jarvis-memory-architect.md
.claude/agents/jarvis-packet-reviewer.md
.claude/agents/jarvis-android-safety-reviewer.md
.claude/skills/jarvis-packetize/SKILL.md
.claude/skills/jarvis-memory-audit/SKILL.md
```

## Rules

- Keep concise.
- Subagents must have clear boundaries.
- Review agents should be read-only.
- Do not depend on Claude memory as enforcement.

---

# L. CLI integration

## Goal

Make the new features usable.

Update `hermes_cli/jarvis_prime/__main__.py` carefully.

Required commands where practical:

```bash
python -m hermes_cli.jarvis_prime memory-tree add ...
python -m hermes_cli.jarvis_prime memory-tree search ...
python -m hermes_cli.jarvis_prime memory-tree outline
python -m hermes_cli.jarvis_prime memory-tree export-markdown
python -m hermes_cli.jarvis_prime packetize "add memory tree support" --json
python -m hermes_cli.jarvis_prime packetize "add memory tree support" --markdown
python -m hermes_cli.jarvis_prime packetize "click Facebook when I ask" --gate-check
python -m hermes_cli.jarvis_prime research list --json
python -m hermes_cli.jarvis_prime model-scorecard add ...
python -m hermes_cli.jarvis_prime owner-brief --json
```

Do not break existing commands:

```bash
python -m hermes_cli.jarvis_prime --help
python -m hermes_cli.jarvis_prime handle "audit repo" --skip-perceive --json
python -m hermes_cli.jarvis_prime avatar --json
python -m hermes_cli.jarvis_prime models tasks --json
```

---

# M. Docs and implementation packets

Add/update docs:

```text
docs/jarvis_architecture/JARVIS_SYSTEM_OVERVIEW.md
docs/jarvis_architecture/JARVIS_PERSONAL_USE_COMPLETION_STATUS.md
docs/jarvis_architecture/JARVIS_OWNER_GATES_AND_PERSONAL_AUTHORITY.md
docs/jarvis_architecture/JARVIS_MEMORY_TREE_AND_NATURAL_LANGUAGE_CODER_SPEC.md
docs/jarvis_architecture/JARVIS_RESEARCH_VAULT.md
docs/jarvis_architecture/TOKENJUICE_CONTEXT_COMPILER.md
docs/jarvis_architecture/APPROVED_PROPOSAL_EXECUTOR.md
docs/jarvis_architecture/CONTINUOUS_MONITORS_AND_OWNER_BRIEF.md
docs/jarvis_research/JARVIS_CURRENT_RESEARCH_DOSSIER.md
docs/implementation-packets/JARVIS_MEMORY_TREE_NL_CODER_COMPLETION_PACKET.md
docs/implementation-packets/JARVIS_PERSONAL_ACTION_ANDROID_COMPLETION_PACKET.md
```

Each doc must state:

- shipped vs scaffolded vs missing
- exact commands to run
- exact files involved
- owner gates
- rollback plan
- remaining risks

---

# N. Testing and smoke requirements

Run focused tests:

```bash
python -m compileall -q hermes_cli/jarvis_prime gateway
pytest -q tests/test_jarvis_prime_memory_tree.py
pytest -q tests/test_jarvis_prime_natural_language_coder.py
pytest -q tests/test_jarvis_prime_companion_presence.py
pytest -q tests/test_jarvis_prime_memory.py
pytest -q tests/test_jarvis_prime_gates.py
pytest -q tests/test_oss_model_brain.py tests/test_model_catalog.py
pytest -q tests/gateway/test_jarvis_local_http.py
```

Run CLI smoke:

```bash
python -m hermes_cli.jarvis_prime --help
python -m hermes_cli.jarvis_prime handle "audit hermes repo for jarvis readiness" --skip-perceive --json
python -m hermes_cli.jarvis_prime packetize "add memory tree support" --json
python -m hermes_cli.jarvis_prime packetize "click Facebook when I ask" --json
python -m hermes_cli.jarvis_prime avatar --json
python -m hermes_cli.jarvis_prime models tasks --json
```

Run Android tests if available:

```bash
cd apps/android
./gradlew test
```

If Android Gradle cannot run in the environment, record the exact failure and do not claim Android tests passed.

Run broader tests if practical:

```bash
pytest -q
```

If full tests are too slow or fail due to unrelated environment issues, record:

- exact command
- exact failure
- whether it is related to changed files
- recommended follow-up

---

# O. Completion criteria

You may only call the build “complete for this PR” if:

1. JARVIS identity is clear in README/docs/CLI.
2. Memory Tree has provenance, freshness, sensitivity, confidence, approval, contradiction, supersession, context packing, persistence, and tests.
3. Natural-language coder emits gate-compatible packets with risk classes, owner gates, validation, markdown, and tests.
4. Research Vault exists or a precise blocker packet exists.
5. TokenJuice exists or a precise blocker packet exists.
6. Model router scorecards exist or a precise blocker packet exists.
7. Proposal executor exists or a precise blocker packet exists.
8. Monitors and daily brief exist or a precise blocker packet exists.
9. Android companion/avatar safety is documented and tested where possible.
10. Local HTTP bridge is safe by default.
11. Focused Python tests pass.
12. CLI smoke passes.
13. Android tests pass or are honestly marked not run with reason.
14. PR body is updated with files changed, tests, risk, and remaining gaps.
15. PR remains draft unless Jeremiah explicitly says to mark ready.
16. Nothing owner-gated was executed.

If any core area is not implemented, do not hide it. Add a documented implementation packet and mark it remaining.

## Final response to Jeremiah

When finished, respond with:

```text
Status:
Files changed:
Tests run:
Smoke results:
What is now shipped:
What remains:
Risks:
PR status:
Need owner approval for:
```

Do not merge. Do not mark ready. Do not deploy.
