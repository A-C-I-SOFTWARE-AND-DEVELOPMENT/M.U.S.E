# JARVIS — One Mind, Many Pathways, Verifiable Arenas

> **What this is.** A theory of how JARVIS becomes durably more capable —
> framed as *one identity* learning through a *neural substrate*, improving by
> *self-play inside verifiable arenas*. It is grounded in the 2024–2026
> literature (cited) and then **advances original, falsifiable hypotheses**
> tailored to the primitives this repository already ships.
>
> **Honesty contract.** Every claim here is either (a) cited to external work,
> or (b) explicitly labeled an **original hypothesis** with the **experiment
> that would validate or refute it**. Nothing is asserted as "proven." This is
> deliberate: a theory of *self-validation* must hold itself to the same bar it
> demands of JARVIS. Hypotheses are written to be **runnable here** — the repo
> is the laboratory, not a thought experiment.

---

## Part I — One mind, many pathways

The product is a single identity: **JARVIS**. There is no second brand.
*JARVIS is the mind/consciousness; **Hermes is his nervous system** — the
gateway, the routing, and the model pathways that carry signal.* The `hermes_*`
code names are the **substrate**, not a co-brand. This is the organizing
metaphor, and it is load-bearing, not decorative:

| Biology | JARVIS | Where it lives |
|---|---|---|
| Mind / locus of self | The single JARVIS identity + value function | `jarvis-constitution.md`, `owner_auth.py` |
| Long-term memory / identity continuity | Memory Tree, Research Vault | `memory_tree.py`, `JARVIS_RESEARCH_VAULT.md` |
| Thalamus / relay & gating | Task-class **model router** | `task_router.py` |
| Cortical pathways / specialists | The routed open + worker models | `oss_model_brain.py`, `worker_registry.py` |
| Afferent signal (was this good?) | **Scorecards** (measured outcomes) | `model_scorecard.py` |
| Associative cortex | GraphRAG knowledge graph | `graphrag/` |
| Reflex arcs / safety | Verification + owner gates, emergency stop | `gates.py`, `owner_auth.py` |

This mirrors, but does not merely restate, the convergent 2024–2026 view that
capable agents are **one controller broadcasting over many specialists**:
Global Workspace Theory applied to language agents [Butlin/Long et al., 2024;
arXiv:2410.11407], the event-driven *Theater of Mind* workspace [2026;
arXiv:2604.08206], and **identity-as-distributed-anchors** rather than a single
store [Menon, 2026; arXiv:2604.09588]. Our claim is sharper than "use a
workspace": **identity is a property of the value function and memory, not of
any pathway** — which becomes a testable hypothesis (H3) rather than a posture.

The classical lineage (SOAR/ACT-R's observe–decide–act cycle [arXiv:2201.09305])
matters because it warns what a single controller lacks by default —
*commitment* and *continuity* — both of which JARVIS supplies from the cognition
plane (Memory Tree + Constitution), not from the model of the moment.

---

## Part II — The substrate we just built

The merged model-intelligence upgrade (task-class-aware routing + scorecards +
GraphRAG context handoff) is, in this framing, the **nervous system coming
online**:

- **Routing = thalamic gating.** `task_router.py` selects, per task class, which
  pathway (model) carries the signal — free/local-first, owner-gated for spend.
  Swapping pathways changes *capability*, not *who is deciding*.
- **Scorecards = verifiable afferent reward.** `model_scorecard.py` records
  measured outcomes (tests passed, accepted-diff rate, owner corrections,
  hallucination corrections, tool reliability, citation accuracy) and gates
  promotion behind **eight conditions**. This is exactly *Reinforcement Learning
  with Verifiable Rewards* (RLVR) [Lambert et al. / Label Studio, 2025] expressed
  as a routing policy: **vendor benchmarks are priors; only measured outcomes
  promote.**
- **GraphRAG = associative recall.** `graphrag/` supplies source-backed context
  (files, tests, prior decisions) so a pathway reuses prior work instead of
  re-deriving it — the substrate's "myelination."

The upgrade is therefore not a feature; it is **the precondition** for everything
below. You cannot run self-play without a reward signal, and scorecards are that
signal.

---

## Part III — The verifiable-arena theory (original)

**Core thesis (original).** JARVIS becomes superintelligent *in niches* not by
scaling one model, but by **owning a self-curated portfolio of verifiable
arenas** and learning through the substrate under a **single value function**.
The game-playing breakthroughs (AlphaZero self-play; AlphaProof/AlphaGeometry's
Lean-verified curriculum [DeepMind, 2024–2025]; *Absolute Zero*'s
propose-and-solve loop with a code executor as verifier [arXiv:2505.03335]) all
share one ingredient that open-ended chat lacks: a **sound, cheap verifier**.
The literature's single biggest open problem is precisely the **verifier gap**
in non-game domains [CompassVerifier, arXiv:2508.03686; LLM-judge unreliability,
arXiv:2603.05399]. The theory below is a strategy for an *agent* (not a model) to
manufacture, rank, and safely exploit verifiers across its real fields of work.

Each hypothesis: a statement, why it might be true (cited), a **falsifiable
prediction**, and a **validation protocol** that runs on this repo's primitives.

### H1 · Verifiable-Niche Primacy
**Statement.** For an agent, the ceiling on self-improvement in a niche is set by
that niche's *verifiability*, far more than by the base model.
**Why plausible.** Success has tracked verifiability empirically: coding
(unit-tested) went ~10%→~70% SWE-bench in ~a year; formal math (Lean-verified)
reached silver-medal IMO; open-ended dialogue improved far slower
[arXiv:2602.10975]. Games have a perfect verifier; chat does not.
**Falsifiable prediction.** Across JARVIS's task classes, the *measured* gain from
self-generated practice will correlate with a per-class **verifier-soundness**
score (execution/test ≫ source-check ≫ rubric/LLM-judge ≫ none). A weak-verifier
niche will plateau or regress under the *same* practice budget that lifts a
strong-verifier niche.
**Validation protocol.** Tag each `ModelScorecard` with a `verifier_type`. Run the
SIA self-improvement worker (`docs/integrations/sia-self-improvement.md`) to
self-generate practice in two high-verifiability lanes (`coding_build` w/ tests,
`citation_verification` w/ GraphRAG source-check) and two low ones
(`mobile_chat`, `summarization`). Compare score-deltas. **Refuted if** a
low-verifiability lane improves as much as a high one.

### H2 · The Manufactured Verifier
**Statement.** Where no natural oracle exists, JARVIS can *compose* a
"good-enough" verifier from signals it already has — and that composite has a
measurable **agreement ceiling** beyond which more self-play *degrades* quality
(reward hacking).
**Why plausible.** Process- and consensus-style verification helps in
non-verifiable domains but is bounded by judge reliability [arXiv:2604.24198;
arXiv:2603.05399]; reward hacking emerges precisely when a proxy is over-optimized
[Countdown-Code, arXiv:2603.07084].
**Falsifiable prediction.** A *consensus verifier* built from GraphRAG
source-backing + Memory-Tree contradiction detection + the verification gates +
owner corrections will raise quality up to a ceiling, after which additional
self-play *increases* owner-correction rate (the hacking signature).
**Validation protocol.** Build the composite from existing parts; track
agreement-with-owner and a diversity metric over rounds; predict — and detect —
the inflection where `owner_corrections` rises while self-reported score keeps
climbing. **Refuted if** quality rises monotonically with no hacking inflection
(verifier is sounder than theorized) **or** never rises (verifier is unsound).

### H3 · Thalamic Routing / Identity Invariance
**Statement.** JARVIS's *identity* is preserved iff the **value function and
memory are centralized**, even as the **pathways (models) change arbitrarily**.
**Why plausible.** Distributed-anchor identity work argues continuity survives
component failure when reference points are centralized, not stored in any one
module [arXiv:2604.09588]; GWT broadcasts *over* swappable specialists
[arXiv:2604.08206].
**Falsifiable prediction.** Swapping the routed model portfolio changes
*capability* scores but leaves *behavioral identity* — measured as the
Constitution self-audit rubric (`jarvis-constitution.md`, clauses C1…Cn) — within
a stable band.
**Validation protocol.** Run the Constitution self-audit across N distinct routed
configurations (local-only, hosted, worker-led). Predict rubric variance ≪
capability variance. **Refuted if** routing changes move the Constitution rubric
as much as they move capability (identity leaks into the pathways).

### H4 · Niche Self-Curriculum (Challenge Ladders)
**Statement.** Improvement is fastest when JARVIS generates tasks **just beyond
its current measured competence** per niche — not uniform or random self-play,
which collapses.
**Why plausible.** *Absolute Zero* maximizes *learnability* of self-proposed
tasks [arXiv:2505.03335]; without cross-iteration diversity control, self-play
exhibits the "diversity illusion" and mode-cycles [R-Diverse, arXiv:2602.13103].
**Falsifiable prediction.** Difficulty-matched task generation (difficulty
estimated from scorecard history) yields steeper, **non-collapsing** improvement
than random self-play in a verifiable niche.
**Validation protocol.** A/B the SIA task generator (competence-matched vs
random) in `coding_build`; measure sustained gain plus a collapse metric
(n-gram/skill diversity across iterations). **Refuted if** random matches matched,
or if matched also collapses.

### H5 · Bounded Self-Modification = Proposal + Arena + Owner Gate
**Statement.** Safe self-improvement is achievable **without** proving correctness
(the Gödel-machine ideal) by confining every self-modification to a pipeline:
**sandbox → verifiable arena (it scores the change) → owner gate (promotion)** —
which is exactly the existing SIA pattern.
**Why plausible.** The Darwin Gödel Machine replaces proof with empirical
validation on benchmarks [arXiv:2505.22954]; STOP self-improves scaffolding
[2024]; but both risk local optima/drift, and self-improvement has *statistical*
safety limits [arXiv:2510.04399].
**Falsifiable prediction.** Capability rises monotonically *only* when promotion
requires passing the arena **and** the owner gate; removing **either** gate
produces measurable drift/regression.
**Validation protocol.** Run SIA in three modes — both gates, arena-only,
owner-only — on a fixed niche; measure capability and drift (distribution shift +
owner-correction rate). Predict both gates necessary. **Refuted if** a single gate
suffices, or if even both gates fail to prevent drift (then the arena is unsound —
see H2).

---

## Part IV — Risk & the safety envelope

Self-improving systems fail in known ways; the substrate must contain them:

- **Reward hacking / proxy gaming** [arXiv:2603.07084; arXiv:2604.02986] →
  contained by H2's hacking-inflection detector + the scorecard
  `owner_corrections`/`hallucination_corrections` penalties already in
  `model_scorecard.py`.
- **Diversity collapse / mode-cycling** [arXiv:2602.13103] → contained by H4's
  collapse metric gating curriculum generation.
- **Distribution drift / specification gaming** → contained by H3 (identity
  invariance audit) + the Constitution self-audit + capability bands.
- **Unbounded recursive self-mod** [arXiv:2510.04399] → contained by H5: every
  promotion is owner-gated; *execution of self-updates stays proposal-only* until
  the owner authorizes (the repo's existing rule). Statistical spending-rule /
  e-test controls bound the improvement rate.

The single value function — the **Constitution + owner gates + emergency stop** —
is what keeps "many pathways" from becoming "many agents." Identity is the
safety mechanism.

---

## Part V — Honesty ledger

- This document proposes; it does not report results. H1–H5 are **conjectures**
  with protocols, not findings.
- The whole theory is **falsifiable as a unit**: if measured gains do *not* track
  verifiability (¬H1) and a single gate suffices for safe self-mod (¬H5), the
  "verifiable-arena" framing is wrong and should be discarded.
- "Revolutionary" is earned only by experiments, not by adjectives. The
  contribution we can stand behind today is the **synthesis**: mapping the
  frontier's five open problems onto primitives that already exist here, so the
  experiments are cheap to run and the failure modes are pre-instrumented.
- No claim of consciousness is made. "Mind," "consciousness," and "nervous
  system" are **architectural metaphors** for a single locus of control over
  specialized pathways — useful, not literal.

---

## References (validated 2026-06; treat as a snapshot)

Self-play / verifiable training: Absolute Zero (arXiv:2505.03335) · AlphaProof/
AlphaGeometry 2 (deepmind.google, 2024) · RLVR (labelstud.io, 2025) ·
Process-Level Reward Modeling (arXiv:2604.24198) · CompassVerifier
(arXiv:2508.03686) · LLM-judge reliability (arXiv:2603.05399).
Self-curriculum / collapse: R-Diverse (arXiv:2602.13103) · FeatureBench
(arXiv:2602.10975). Single-identity architecture: AI-consciousness/GWT
(arXiv:2410.11407) · Theater of Mind (arXiv:2604.08206) · Persistent identity
(arXiv:2604.09588) · ACT-R/SOAR (arXiv:2201.09305) · agent memory
(mem0.ai, 2026). Self-improvement & limits: Darwin Gödel Machine
(arXiv:2505.22954) · STOP (2024) · reward hacking (arXiv:2603.07084,
arXiv:2604.02986) · statistical limits of self-improvement (arXiv:2510.04399).

*Cross-references:* `JARVIS_SYSTEM_OVERVIEW.md` · `GRAPHRAG_KNOWLEDGE_GRAPH.md` ·
`../jarvis-constitution.md` · `../jarvis-verification-gates.md` ·
`../integrations/sia-self-improvement.md` ·
`../ai-intelligence/task-class-model-routing.md`.
