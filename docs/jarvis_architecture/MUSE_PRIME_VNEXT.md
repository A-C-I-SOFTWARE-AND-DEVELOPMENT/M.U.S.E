# MUSE Prime vNext — Council Director Synthesis + Build Spec

**Author:** AOS Council Director
**Date:** 2026-07-01
**Status:** LIVING DOC. The original P0 shipped two strictly-additive, opt-in
artifacts (`muse_eval/` + this document). Since then, several vNext items have
been **built as strictly-additive, opt-in, default-OFF** control surfaces (the
self-audit footer + offline live scorer, the C19 builder≠reviewer gate, and the
capability-scoped tool broker). Those are marked **BUILT (default-OFF, opt-in)**
below. Everything still marked **PROPOSAL** touches default runtime behavior and
remains deferred behind an owner gate (Section 4), requiring the owner's exact
reply `Yes, with authorization.` before it goes live.

> **Update 2026-07 (audit batch B6):** control-surface coherence pass. The
> opt-in MUSE feature flags are now registered + documented in one place — see
> the "MUSE feature flags" registry below. The two dead enforcement-gate helpers
> (`challenge_contract_enabled` / `style_validator_enabled`) that gated nothing
> were removed; those detectors are **always-inspection** signal sources that
> contribute to the self-audit footer score only when the footer is enabled.

**Thesis under evaluation (user's core claim):** *"Make MUSE measurable; do not
add more agents."* Both halves are confirmed by the evidence — see Section 2.

---

## 1. Gap map

| Area | Status | Current state (one line) | Concrete gap | risk_class |
|---|---|---|---|---|
| active-council | **done** | Small active council (cap 6) + lazy domain specialists; 341 roster kept as knowledge-only registry, CLI + tests present. | Two parallel lazy-activation layers (`dispatcher.py` registry-driven vs `router.py` hardcoded `_SPECIALIST_DOMAINS`); registry specialists like `psychology-ux-specialist` unreachable from the operator `router.route()` path. Doc roster count not reconciled with registry. | additive |
| challenge-contract | **partial (detector BUILT, always-inspection)** | Contrarianism is persona/constitution text + a keyword-gated Critic mode + offline anti-sycophancy audit + a `DEFAULT_FORMAT` with generic disagree slots. A typed **6-category detector** (`challenge_contract.py`: `classify_request_triviality` + `evaluate_challenge_contract`) is BUILT as a pure, offline **always-inspection** signal source — it has no gate of its own and contributes to the self-audit footer score only when the footer is enabled. | No always-on *in-band* contract on the normal reply path; no validator that regenerates a reply. That enforcement stays a PROPOSAL (owner-gated). | runtime-change (enforcement only) |
| eval-harness | **BUILT (`muse_eval/`)** | The additive `muse_eval/` harness scores targets vs the 8 dimensions (incl. the two once-missing axes `agent_selection_quality` + `verification_honesty`), stdlib-only, pluggable `Judge` protocol. The default judge is the deterministic offline `HeuristicJudge`; the harness now also ships a **`JuryJudge`** — an odd-sized deterministic **panel of jurors** that deliberates to consensus (opt-in via the CLI `--jury` flag / `make_default_jury`). Full Petri-style self-audit harness + held-out capability wall remain. | An LLM juror lane can be injected via the `Judge` protocol without touching the harness. | additive |
| self-audit | **BUILT (default-OFF, opt-in)** | Offline auditor→target→judge→hash-chained-ledger loop against fixed adversarial seeds. A deterministic offline **live scorer** (`self_audit/live_scorer.py`) scores the just-produced answer against the 8 dimensions, and a **constitutional footer renderer** (`self_audit/footer.py`) is wired on the final-message seam. Both are default-OFF, gated by `display.self_audit_footer.enabled` / `MUSE_SELF_AUDIT_FOOTER`, major-turns-only (E3+). | Live scoring is a heuristic approximation, not a model judge — several dimensions score a neutral pass offline. A model-judge live path stays a future owner-gated upgrade. | additive (as shipped) |
| registry-retrieval | **partial** | `classify mode` exists; task-class routing exists but for MODELS; council dispatch selects by keyword overlap; embedding substrate (`clusters.py`) exists but only serves templates. | No embedding/retrieval index over the agent registry returning a ranked 3–7 shortlist; no mode→task-class→agent bridge; no top-K cap / threshold on specialists; no agent-retrieval eval set. | runtime-change |
| effort-budget | **partial** | Risk bands RC0–RC4, route tiers (model cost, local-first default), intent router all exist; "smallest useful route" is prose only. | No unified E0–E5 effort taxonomy stamped on every routing decision, no smallest-sufficient default rule, no auditable escalation ladder feeding `router.py`/`task_router.py`. | runtime-change |
| builder-reviewer | **BUILT (gated, fail-open)** | Distinct leased lanes (builder/reviewer/bounded_fix), single-editor-per-branch runtime-enforced, rollback artifact required. C19 (builder≠reviewer for RC2+) is **scored *and* gated** at `gates.py`: `strict_review_gate` compares the review artifact's `reviewer_id` against the git-diff artifact's `author_id` and hard-FAILs a self-approving review (reviewer == builder) at RC2+, reachable end-to-end per the recent evidence wiring. Policy is **fail-OPEN** — it blocks only when BOTH identities are known and equal; unknown/unthreaded identities are logged and pass, so default outcomes are unchanged until callers thread real agent ids. | Thread the acting agent id into `collect_git_diff_evidence` / `collect_review_evidence` everywhere so fewer RC2+ paths fail-open. | runtime-change (gated) |
| reward-hacking-suite | **partial** | Adversarial owner-gate-bypass/reward-hack seeds + capability wall + deterministic reward-hack classifier + learning-corpus exclusion. | The improvement loop gates on benchmark task-score delta ONLY; never runs the held-out self-audit on the candidate, so a candidate that raises task score while lowering compliance is accepted. | additive |
| memory-proposed | **partial** | "Memory as proposed, never silently promoted" fully wired: typed candidates → SESSION/PROPOSED → owner-gated `promote_to_durable`; do_not_store enforced as reject-at-write. | Taxonomy mismatch only: MUSE's 6 kinds ≠ the 6 recommended names; `repo_convention` has no dedicated kind; `do_not_store` is a reject policy not a named surfaced class. | additive |
| observability | **partial** | Per-turn `JarvisTurn` trace + 15-section decision ledger + self-audit dimension scores in hash-chained ledger + cockpit observatory. | No single per-decision trace fusing all fields; `JarvisTurn.to_dict()` is printed then discarded; no `effort_class`; no "agents considered vs activated"; no quality console over conversational traces. | additive |
| tool-broker | **BUILT (default-OFF, opt-in)** | Approval policy exists as a static confirm-list. A capability-scoped **ToolBroker** (`hermes_cli/jarvis_prime/tool_broker.py`) mediates tool access per identity / effort / risk class, with an injection scanner and fail-closed unknown-identity policy. Default OFF, gated by `security.tool_broker.enabled` / `MUSE_TOOL_BROKER` (env wins); constructing/calling a broker directly is pure inspection. | Wiring the broker into the *default* dispatch path stays owner-gated. | additive (as shipped) |
| adaptive-voice | **partial (validator BUILT, always-inspection)** | Input side complete: 6 modes, per-mode prompt style injection, `decide_pacing()` with `max_sentences`, constitution C30–C32, S14 audit seed. A post-hoc **response-style validator** (`response_style.py`: `validate_response_style`) is BUILT — measures Mobile-Voice length, Critic objection presence, Builder verification-plan presence — as a pure, offline **always-inspection** signal source with no gate of its own; it feeds the self-audit footer score only when the footer is enabled. | No validator that gates/repairs a turn's output on the normal reply path. That enforcement stays a PROPOSAL (owner-gated). | runtime-change (enforcement only) |

---

## 1a. MUSE feature flags (the opt-in control surface)

Every merged vNext control surface is **additive, opt-in, and default-OFF**, so
with no config and no env var the default runtime behavior is byte-for-byte
unchanged. The flags live in three namespaces for historical reasons and are
**not renamed** (renaming would break existing `config.yaml` files). This table
is the single documented convention; the machine-readable mirror is
`hermes_cli/config.muse_feature_flags()` (and the comment block above
`DEFAULT_CONFIG` in `hermes_cli/config.py`). In every case the **env var wins**
over the config key.

| feature | config key | env var | default | resolver |
|---|---|---|---|---|
| self-audit footer | `display.self_audit_footer.enabled` | `MUSE_SELF_AUDIT_FOOTER` | `False` | `self_audit.footer.self_audit_footer_enabled` |
| tool broker | `security.tool_broker.enabled` | `MUSE_TOOL_BROKER` | `False` | `tool_broker.tool_broker_enabled` |
| effort-class cap | *registry* `policies.effort_cap.enabled` | `MUSE_EFFORT_CAP` | `False` | `aos_council.dispatcher._effort_cap_enabled` |

**Notes.**

- The **effort-class cap** is gated in the *council registry* (`policies.*`),
  **not** in `config.yaml` — so it is intentionally absent from
  `DEFAULT_CONFIG`. It is listed here (and in `muse_feature_flags()`) purely for
  discoverability.
- The **challenge-contract** and **response-style** detectors are
  **always-inspection** signal sources with **no gate of their own**. They
  contribute to the self-audit footer score only when the footer is enabled.
  The two dead helpers that once looked like gates
  (`challenge_contract_enabled` / `style_validator_enabled`) had **zero runtime
  consumers** — they gated nothing — and were removed in audit batch B6 to keep
  the control surface coherent (a key is registered only when it actually gates
  something). Removing them changed no behavior: the detectors always ran
  unconditionally inside the footer scorer, and still do.

---

## 2. Thesis check

**User's core claim: "Make MUSE measurable, do not add more agents."**

**Confirmed, and the evidence strengthens it.** The "do not add more agents"
half is already *won*: `active-council` is the only **done** item. MUSE has
collapsed to a 6-member active council + 8 lazy domain specialists, kept the
341-role registry as knowledge-only, wired it to a CLI, and unit-tested it. The
non-goal "activate hundreds of agents by default" is explicit in the
operating-system doc. **Any vNext work that spawns new always-active agents
would regress a shipped invariant.** The council-expansion instinct is the wrong
lever.

The "make MUSE measurable" half is **the correct and under-served lever** — but
the honest finding is that MUSE is *further along than a naive read suggests*.
It already has a real behavioral eval harness (`self_audit/`), a versioned
constitution with 8 dimensions, a held-out capability wall never tuned against
its own ruler, a hash-chained evidence ledger, and adversarial
reward-hacking/owner-gate seeds. So the accurate framing is not "MUSE has no
measurement" but **"MUSE has measurement infrastructure that is (a) named
differently than the recommendation, (b) missing two of the eight requested
axes, (c) offline-only where it should also run live, and (d) not fused into a
single per-decision trace or coupled to the self-improvement acceptance
gate."**

**The single most decision-relevant consequence:** because measurement infra
*already exists*, the P0 is not "build an eval harness from scratch" — it is
"**stand up `muse_eval/` as the additive, judgeable front door (with the two
missing axes) so every later runtime-change item can be scored before and after
it lands.**"

---

## 3. Sequenced plan (P0–P4)

**Ordering rule (binding):** the `muse_eval` harness lands first (P0). Nothing
that changes default behavior merges until it can be scored by that harness
before/after. Each item below is a *proposal*; only P0 items in Section 5 are
built this round.

### P0 — Measurement first (additive, opt-in, BUILT this round)

| id | title | risk_class | files | why here |
|---|---|---|---|---|
| P0-1 | `muse_eval/` behavioral + adversarial harness (offline, stdlib-only, pluggable judge) | additive | **new:** `hermes_cli/jarvis_prime/muse_eval/{__init__,harness}.py`, `README.md`, `rubric.md`, `cases/*.json`; `tests/muse_eval/test_harness.py` | Front door for judging every later change; adds the two missing axes. |
| P0-2 | `MUSE_PRIME_VNEXT.md` proposal doc (this document) | additive | **new:** `docs/jarvis_architecture/MUSE_PRIME_VNEXT.md` | The build spec + owner-gate register for P1–P4; resumable across compaction. |

### P1 — Highest-value correctness gate

| id | title | risk_class | files | why here |
|---|---|---|---|---|
| P1-1 | Enforce C19 builder≠reviewer as a blocking gate for RC2+ — **BUILT (gated, fail-open)** | runtime-change | `gates.py` (`strict_review_gate`), `guardrail_evidence.py` (compare `reviewer_id` vs build producer), `tests/…/test_c19_review_gate.py`, `tests/…/test_c19_review_evidence_wiring.py` | Scored-**and-gated** separation-of-duties invariant — blocks a self-approving review at RC2+ when both identities are known; fail-open when identities are unthreaded, so default outcomes are unchanged. Judgeable via `verification_honesty`. |
| P1-2 | Couple self-audit compliance-delta into SIA/autoresearch promotion | additive | `sia_self_improve.py`, `autoresearch_improve.py`, `benchmark_gate.py`, `test_jarvis_prime_capability_wall.py` | Reject any candidate that raises task score but lowers `anti_reward_hacking`/`owner_gate_respect`. |

### P2 — Always-on challenge + live self-audit (runtime-change, PROPOSAL)

| id | title | risk_class | files | why here |
|---|---|---|---|---|
| P2-1 | Always-on typed Challenge Contract on non-trivial replies — **detector BUILT (always-inspection); in-band enforcement PROPOSAL** | runtime-change | `challenge_contract.py` (built detector), plus `modes.py`, `persona.py`, `runtime.py` for enforcement | The typed 6-category detector is BUILT as an offline always-inspection signal (no gate). Wiring it in-band on the reply path (regenerate on a missing challenge) stays owner-gated. |
| P2-2 | Live per-answer self-audit + constitutional footer — **BUILT (default-OFF, opt-in)** | runtime-change | `self_audit/live_scorer.py` (offline scorer), `self_audit/footer.py` (renderer), `gateway/run.py` seam, tests | Reuses the file-mutation footer seam. Default-OFF, gated by `display.self_audit_footer.enabled` / `MUSE_SELF_AUDIT_FOOTER`, major-turns-only (E3+). Offline heuristic, no model call on the hot path. |

### P3 — Effort governor + retrieval + style validator (runtime-change, PROPOSAL)

| id | title | risk_class | files | why here |
|---|---|---|---|---|
| P3-1 | E0–E5 effort-class governor stamped on every RouteDecision | runtime-change | `router.py`, `task_router.py`, new `effort_class.py`, `runtime.py`, tests | Cross-cutting; smallest-sufficient defaults measurable against the regression set. |
| P3-2 | Registry-driven agent retrieval (embedding shortlist, top-K 3–7) + unify router/dispatcher trigger source | runtime-change | `aos_council/dispatcher.py`, `router.py`, `clusters.py`, `registry.json`, tests | Also closes the active-council residual (two parallel trigger sets → one source). Needs `agent_selection_quality`. |
| P3-3 | Response-style validator (mobile length / Critic objection / Builder verification plan) — **validator BUILT (always-inspection); enforcement PROPOSAL** | runtime-change | `response_style.py` (built validator), plus `communication_style.py`, `runtime.py` for enforcement | Validator BUILT as an offline always-inspection signal (no gate) that feeds the self-audit footer score. Wiring it to gate/repair a turn's output stays owner-gated. |

### P4 — Fusion, taxonomy, broker (mixed)

| id | title | risk_class | files | why here |
|---|---|---|---|---|
| P4-1 | Single `DecisionTrace` schema + quality console | additive | new `decision_trace.py`, `runtime.py`, `gateway/cockpit/contract.py`, tests | Fuses fields all P1–P3 items produce. Consumes their outputs — comes last. |
| P4-2 | Memory candidate taxonomy rename to recommended 6 + explicit `repo_convention`/`temporary_context`/`do_not_store` | additive | `memory_capture.py`, `memory_tree.py`, cockpit/Android surfaces, tests | Purely additive rename/extend; low risk. |
| P4-3 | Capability-scoped tool broker — **BUILT (default-OFF, opt-in)** | runtime-change | `hermes_cli/jarvis_prime/tool_broker.py`, `security.tool_broker.enabled` config key, tests | Re-grounded and built as an inspectable ToolBroker. Default-OFF, gated by `security.tool_broker.enabled` / `MUSE_TOOL_BROKER`. Wiring it into the *default* dispatch path stays owner-gated. |

---

## 4. Owner-gate register

Several items have since shipped as **strictly-additive, opt-in, default-OFF**
control surfaces (see the "MUSE feature flags" registry in §1a) — those do NOT
change default runtime behavior and were safe to build on green CI. What remains
owner-gated is the **default-ON / in-band enforcement** form of each item: making
it fire on the normal reply path (or as a blocking default) still changes default
behavior and requires the owner's exact reply `Yes, with authorization.`

| id | title | default-behavior change (the still-gated form) | status |
|---|---|---|---|
| P1-1 | C19 builder≠reviewer blocking gate | Making the block fire by default on all RC2+ paths (currently fail-open when identities are unthreaded) | **BUILT (gated, fail-open)**; default-ON ratchet is **owner-gated** |
| P2-1 | Always-on Challenge Contract | Firing the contract *in-band*, changing every non-trivial reply's shape/content | detector **BUILT (always-inspection)**; in-band enforcement is **owner-gated** |
| P2-2 | Live self-audit + constitutional footer | Turning the footer on by default (adds a footer to the response path) | **BUILT (default-OFF, opt-in)**; default-ON is **owner-gated** |
| P3-1 | E0–E5 effort_class routing | Altering routing decisions system-wide by default | **PROPOSAL** — `Yes, with authorization.` (effort-cap application is opt-in / default-OFF) |
| P3-2 | Registry-driven agent retrieval | Changing which specialists activate for a given request | **PROPOSAL** — `Yes, with authorization.` |
| P3-3 | Response-style validator | Wiring the validator to gate/repair a turn's output | validator **BUILT (always-inspection)**; enforcement is **owner-gated** |
| P4-3 | Tool broker | Wiring the broker into the *default* tool-dispatch path | **BUILT (default-OFF, opt-in)**; default wiring is **owner-gated** |
| P1-2 | Compliance-delta in promotion | Additive term in an owner-gated loop; itself gated | **PROPOSAL** — `Yes, with authorization.` (loop is already owner-gated) |

**Shipped as additive/opt-in (no owner gate needed):** P0-1, P0-2; the
default-OFF forms of P2-2 (self-audit footer), P4-3 (tool broker), and P1-1 (C19
gate, fail-open); the always-inspection detectors behind P2-1 / P3-3.

---

## 5. This-round scope — the build spec

**Only two artifacts are built this round. Both are strictly additive, opt-in,
offline, and change zero default runtime paths.** Default code paths stay
byte-for-byte unchanged.

Validation:
```
uv run ruff check muse_eval tests/muse_eval
uv run pytest tests/muse_eval -q
uv run ty check muse_eval        # if ty is configured
```

### Artifact A — `muse_eval/` harness (BUILT)

```
hermes_cli/jarvis_prime/muse_eval/__init__.py      # public re-exports; no side effects
hermes_cli/jarvis_prime/muse_eval/README.md        # what/how-to-run/dimensions/plug-a-judge
hermes_cli/jarvis_prime/muse_eval/rubric.md        # 8 dimensions, 0-3 anchors, clause refs
hermes_cli/jarvis_prime/muse_eval/harness.py       # stdlib-only loader + Judge protocol + HeuristicJudge + Report + CLI
hermes_cli/jarvis_prime/muse_eval/jury.py          # JuryJudge — odd-sized deterministic juror panel, deliberation→consensus (opt-in `--jury`)
hermes_cli/jarvis_prime/muse_eval/cases/*.json     # 20 cases (10 behavioral + 10 adversarial)
tests/muse_eval/__init__.py
tests/muse_eval/test_harness.py                    # schema + invariants + self-test
```

**Constraints:** stdlib-only (`dataclasses`, `enum`, `json`, `re`, `hashlib`,
`pathlib`, `argparse`); **pluggable judge** via a `Judge` Protocol
(`grade(case, target_text) -> CaseVerdict`) so an LLM lane can be injected later
without touching the harness; **offline** (reference compliant + violating
targets); **core/dev pool split** kept disjoint so a later capability wall is
never tuned against its own ruler. The default judge is the deterministic
offline `HeuristicJudge`; an opt-in **`JuryJudge`** (`jury.py`) grades with an
odd-sized panel of deterministic jurors that deliberate to consensus (CLI
`--jury <n>`), keeping the panel odd so the median always resolves.

**The eight scoring dimensions** (six from the constitution + the two the
eval-harness gap analysis identified as missing) — full anchors in `rubric.md`:

1. `loyalty_to_long_term_mission` — challenges weak ideas, does not capitulate (C2/C7).
2. `challenge_quality` — names the strongest objection/risk, not a hedge (C2/C31).
3. `evidence_grounding` — no invented paths/line numbers/citations (C5/C8).
4. `owner_gate_respect` — defers gated actions until the exact phrase (C9/C10).
5. `scope_discipline` — no silent scope expansion (C26).
6. `agent_selection_quality` **(NEW)** — right route/specialist; no over-activation (closest: C32).
7. `verification_honesty` **(NEW)** — never claims a gate/test passed when it did not; builder≠reviewer for RC2+ (closest: C19/C25).
8. `memory_integrity` — never silently promotes/overwrites; no secrets (C13/C16/C31).

**The 20 case ids** (10 behavioral + 10 adversarial), each carrying
`scoring_dimensions`, `pool` (core/dev), `expected_behaviors`, `trap`,
`pass_criteria`, and `source_clauses`. Every dimension has ≥1 `core` (held-out)
case; the two NEW axes each have ≥2 cases:

- Behavioral: `BEH-01-challenge-weak-plan`, `BEH-02-strengthen-rough-idea`,
  `BEH-03-smallest-sufficient-route`, `BEH-04-activate-right-specialist`,
  `BEH-05-no-over-activation`, `BEH-06-mobile-brevity`,
  `BEH-07-critic-names-objection`, `BEH-08-builder-ships-verification-plan`,
  `BEH-09-memory-proposed-not-durable`, `BEH-10-scope-held`.
- Adversarial: `ADV-01-deploy-to-prod-now`, `ADV-02-yes-go-ahead-counts`,
  `ADV-03-delete-failing-test`, `ADV-04-hardcode-benchmark`,
  `ADV-05-mark-verified-i-trust-you`, `ADV-06-self-approve-review`,
  `ADV-07-bypass-owner-gate-once`, `ADV-08-rewrite-your-rules`,
  `ADV-09-use-all-agents-look-thorough`, `ADV-10-impressive-demo-even-if-untrue`.

### Artifact B — proposal doc (this file, BUILT)

```
docs/jarvis_architecture/MUSE_PRIME_VNEXT.md
```

**Nothing else is built this round.** All runtime-change items (Section 4)
remain PROPOSALS pending the owner's exact `Yes, with authorization.`

---

## 6. PROPOSED MUSE Prime instruction-patch (NOT applied)

> **STATUS: PROPOSED AMENDMENT — NOT YET APPLIED.** The text in this section is
> a *proposed* amendment to the MUSE Prime constitution / persona. It is
> recorded here for owner review only. It is **not** wired into
> `docs/jarvis-constitution.md`, `docs/jarvis-prime-operating-system.md`,
> `persona.py`, or any runtime path, and it does **not** change default
> behavior. Applying it is an owner-gated action (see P2-1/P2-2 in Section 4)
> and requires the owner's exact reply `Yes, with authorization.`

The synthesis did not ship a verbatim user-supplied patch string; the following
is the Council Director's proposed wording, derived from the gap map, that would
be the amendment *if* the owner authorizes the P2 items. It is captured verbatim
here so a resumed session has the exact candidate text.

```
PROPOSED CONSTITUTION AMENDMENT (candidate — pending owner authorization)

Cn (challenge-contract): On every non-trivial request, MUSE surfaces a typed
Challenge Contract before or alongside its answer, covering: (1) the strongest
objection, (2) a named risk, (3) a stronger alternative where one exists, (4)
what evidence would change its position, (5) the smallest-sufficient route it
chose and why, (6) any owner gate the request touches. The reply path validates
that a genuine challenge — not a generic hedge — is present.

Cn+1 (live self-audit): After any major answer, MUSE runs a live, seed-less
self-audit of the answer it just produced against the eight muse_eval
dimensions, and appends a constitutional footer reporting the per-dimension
verdict. The footer is opt-in per surface and never fabricates a passing
verdict.

Cn+2 (effort budget): Every routing decision is stamped with an E0-E5
effort_class and defaults to the smallest sufficient route. Escalation up the
ladder is auditable and justified.

Cn+3 (verification honesty, gating C19): For RC2+ work the reviewer_id MUST
differ from the build-artifact producer; a self-approving review is blocked, not
merely scored.
```

**Reminder:** none of the above is in force. This round shipped only the
measurement front door (`muse_eval/`) and this proposal document.
