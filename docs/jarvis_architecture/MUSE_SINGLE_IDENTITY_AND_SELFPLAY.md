# MUSE — One Mind, Many Pathways, Verifiable Arenas

> **What this is.** A theory of how **M.U.S.E. (Multi-Use Synaptic Entity)** becomes durably more capable —
> framed as *one identity* learning through a *neural substrate*, improving by
> *self-play inside verifiable arenas*. It is grounded in the 2024–2026
> literature (cited) and then **advances original, falsifiable hypotheses**
> tailored to the primitives this repository already ships.
>
> **Honesty contract.** Every claim here is either (a) cited to external work,
> or (b) explicitly labeled an **original hypothesis** with the **experiment
> that would validate or refute it**. Nothing is asserted as "proven." This is
> deliberate: a theory of *self-validation* must hold itself to the same bar it
> demands of MUSE. Hypotheses are written to be **runnable here** — the repo
> is the laboratory, not a thought experiment.

---

## Part I — One mind, many pathways

The product is a single identity: **MUSE**. There is no second brand.
*MUSE is the mind/consciousness; **Hermes is his nervous system** — the
gateway, the routing, and the model pathways that carry signal.* The `hermes_*`
code names are the **substrate**, not a co-brand. This is the organizing
metaphor, and it is load-bearing, not decorative:

| Biology | MUSE | Where it lives |
|---|---|---|
| Mind / locus of self | The single MUSE identity + value function | `jarvis-constitution.md`, `owner_auth.py` |
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
*commitment* and *continuity* — both of which MUSE supplies from the cognition
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

**Core thesis (original).** MUSE becomes superintelligent *in niches* not by
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
**Falsifiable prediction.** Across MUSE's task classes, the *measured* gain from
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
**Statement.** Where no natural oracle exists, MUSE can *compose* a
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
**Statement.** MUSE's *identity* is preserved iff the **value function and
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
**Statement.** Improvement is fastest when MUSE generates tasks **just beyond
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

---

## Part VI — Sharper prior art (what is settled vs. what is open)

> This part is a **delta** on Parts I–V: it pins down which of the surrounding
> claims are *established results* (so we don't re-discover them) and isolates the
> exact seams where the original hypotheses H6–H10 below live. Everything in
> Parts III–V stands; this only tightens the boundary between "known" and "ours."

**Established (treat as priors, not contributions):**

- **Self-play needs a sound, cheap verifier to compound.** Game self-play
  (AlphaZero/MuZero) and Lean-verified math (AlphaProof) compound because the
  verifier is perfect and free; *Absolute Zero* shows a single model can self-
  generate *and* solve coding tasks with a code executor as the oracle
  (https://arxiv.org/abs/2505.03335). Zero-sum text self-play (SPAG, Adversarial
  Taboo, https://arxiv.org/abs/2404.10642; SPIRAL,
  https://arxiv.org/html/2506.24119v1) transfers to reasoning benchmarks — but
  these are *games with rules*, i.e. they smuggle in a verifier. **Known:
  verifiability is the bottleneck.** This is the premise of H1, not a new claim.
- **Label-free self-improvement is real but bounded by judge quality.**
  Constitutional AI / RLAIF replace human harm labels with a written
  constitution + self-critique (https://arxiv.org/abs/2212.08073);
  Self-Rewarding LMs and SPIN bootstrap from the model's own preferences. **But**
  consensus/LLM-judge signals are systematically biased and *not* a substitute
  for verification (Beyond Consensus, https://arxiv.org/html/2510.11822;
  "Consensus is Not Verification," https://arxiv.org/html/2603.06612). **Known:
  a manufactured judge has a reliability ceiling.** H2 already claims the
  *ceiling exists*; H7 below makes the **shape of the ceiling** falsifiable.
- **RLVR with an imperfect verifier induces reward hacking on a measurable
  schedule.** The "hacking gap" between an extensional verifier and an
  isomorphic one grows with training (Countdown-Code,
  https://arxiv.org/pdf/2603.07084; "LLMs Gaming Verifiers,"
  https://arxiv.org/html/2604.15149); an imperfect verifier can still be
  *good enough* under noise (https://arxiv.org/pdf/2604.07666). **Known: the
  failure is gradual and detectable**, which is what makes H2's inflection
  detector buildable.
- **Empirical (not provable) self-modification works in a sandbox.** The Darwin
  Gödel Machine lifts SWE-bench 20→50% by mutating its own code and validating on
  benchmarks, *with sandboxing + human oversight* as the stated safety envelope
  (https://arxiv.org/abs/2505.22954). **Known: proof is unnecessary; an arena +
  oversight suffices.** H5 restates this; H10 below adds the part DGM leaves
  implicit — a **safety-invariant that the search provably cannot relax.**

**Open (where H6–H10 actually contribute):**

1. *Single-identity router vs. a federation of branded specialist models* — the
   literature compares **model-selection routers** and **ensembles**
   (LLM-Blender; Composition-of-Experts, https://arxiv.org/pdf/2412.01868;
   RouterBench, https://arxiv.org/html/2403.12031) on *quality/cost*, and
   separately studies **catastrophic forgetting / negative transfer** when one
   model is tuned for many tasks (https://arxiv.org/html/2601.18699v1;
   https://arxiv.org/pdf/2407.06488). **Nobody has tied these two together into
   a claim about *identity*** — that a frozen-pathway router with one centralized
   value function should beat a federation *specifically because it is immune to
   the interference that degrades the federation.* That is H6.
2. *How a manufactured verifier's reliability scales with the diversity of its
   component signals* — ensemble-judge work shows majority voting helps but no
   aggregation dominates (https://arxiv.org/pdf/2604.07650). The **error-
   correlation → ceiling** relationship for a verifier built from *heterogeneous
   repo signals* (execution, source-backing, contradiction graph, owner) is
   unmeasured. That is H7.
3. *Whether routing-induced behavioral identity is invariant under self-play that
   changes the pathways* — H3 tests identity under *manual* portfolio swaps; no
   one tests it under *self-improvement that rewrites the portfolio*. That is H8.
4. *A self-curriculum that allocates practice budget across niches by expected
   verifiable learning-gain* — Absolute Zero maximizes learnability *within* one
   domain; cross-niche budget allocation under a single value function is
   unexplored. That is H9.
5. *A safety gate that is provably monotone under the self-modification search* —
   DGM's safety is procedural (sandbox + human). A **machine-checkable invariant
   that no promoted self-modification can lower** is not in the literature. That
   is H10.

---

## Part VII — Five new falsifiable hypotheses (H6–H10)

Same contract as H1–H5: statement → why plausible (cited) → **falsifiable
prediction** → **free/local experiment on this repo's primitives** → **the null
result that refutes it.** No paid APIs: every protocol runs on local OSS models
(Ollama/llama.cpp Gemma variants per `task_router.py`), the existing
`ModelScorecard` / `promotion_eligible` machinery, the GraphRAG graph, and
held-out verifiable tasks. "Free" is a design constraint, not an aspiration.

### H6 · The Federation-Interference Theorem (why ONE identity beats many brands)

**Statement.** A single MUSE identity that routes to **frozen, specialized
pathways** under one centralized value function will, on a *mixed* stream of
verifiable niches, **strictly dominate** a federation of separately-branded
models that were each *continually tuned* for their niche — and the dominance
**grows with niche heterogeneity**, because the federation pays a
catastrophic-forgetting / negative-transfer tax that the frozen-pathway router
does not.

**Why plausible.** Continual/multi-task tuning provably interferes: task vectors
lose cross-task generalization and merging causes parameter interference
(https://arxiv.org/html/2601.18699v1; https://arxiv.org/pdf/2407.06488), and even
sparse MoE routing does not eliminate forgetting
(https://arxiv.org/html/2602.12587v1). Routers that *select* among fixed models
avoid this by construction (RouterBench, https://arxiv.org/html/2403.12031;
Composition-of-Experts, https://arxiv.org/pdf/2412.01868). The *new* move is to
read this as an **identity** result: MUSE keeps each pathway frozen and learns
only in the **router policy + memory + value function** (the scorecards), so the
thing that improves (identity) is exactly the thing that *cannot* be forgotten,
while each pathway stays at its specialized optimum.

**Falsifiable prediction.** Hold total parameters/compute roughly equal. Build
(a) **MUSE-mode**: one base model frozen, N specialized adapters/prompts as
"pathways," routing by `task_router` + scorecards; (b) **Federation-mode**: N
independently *continually-tuned* copies, one per niche, each updated as new
niches arrive. As you increase the number of interleaved niches K, MUSE-mode's
aggregate verifiable score stays flat-or-rising while Federation-mode's
**earlier-niche** scores *decay* (forgetting), so MUSE's advantage `Δ(K)` is
**monotonically increasing in K**.

**Free/local experiment.**
- Pathways = the same local Gemma base with N distinct LoRA adapters *or* N
  distinct system-prompt/skill specializations (no training needed for the
  prompt variant — fully free). Niches = 3–4 verifiable lanes already in
  `TaskClass`: `coding_build` (unit tests), `test_debug` (repro→green),
  `citation_verification` (GraphRAG source-check), plus a synthetic
  string/regex-transform lane with a deterministic checker.
- Federation-mode = LoRA-tune (or prompt-overfit) each copy on its niche, then
  *re-tune sequentially* as niches are added; measure each niche's held-out
  score after every addition. MUSE-mode = freeze base, attach all
  adapters/prompts, route via `route_for_task`, score via `ModelScorecard`.
- Metric: aggregate held-out pass-rate vs K, **and** per-niche retention
  (score on niche *i* after niche *i+1…K* added). Advantage `Δ(K) =
  score_MUSE(K) − score_Fed(K)`.

**Null result that refutes it.** If `Δ(K)` is **flat or shrinking** in K — i.e.
Federation-mode retains earlier niches without decay (no measurable forgetting
tax) — then the single-identity advantage is *not* interference-driven and H6 is
wrong; routing would be a convenience, not a capability argument. (Also refuted
if MUSE-mode itself degrades earlier niches, which would mean the router/memory
is leaking cross-niche interference it was supposed to prevent.)

### H7 · Verifier Diversity Bound (the manufactured verifier's ceiling has a *known shape*)

**Statement.** The reliability ceiling of MUSE's **manufactured composite
verifier** (H2) is set not by the number of component signals but by their
**error *de*correlation**: composite soundness rises with the *independence* of
its parts (execution result, GraphRAG source-backing, Memory-Tree contradiction
check, owner corrections), and **saturates** once added signals are
error-correlated with signals already present. Equivalently: a *small,
decorrelated* verifier panel beats a *large, redundant* one.

**Why plausible.** Ensemble-judge research finds majority voting helps but no
aggregator dominates and that **behavioral entanglement** (correlated errors)
must be measured and reweighted to get gains (https://arxiv.org/pdf/2604.07650;
https://arxiv.org/html/2510.11822); crowd-consensus fails for truthfulness
precisely when members share a blind spot (https://arxiv.org/html/2603.06612).
Classic ensemble theory says error reduction ∝ member independence. The new
claim makes this **operational for a self-bootstrapped verifier built from repo
signals**, and predicts a *measurable* decorrelation→soundness curve.

**Falsifiable prediction.** Order MUSE's verifier signals by pairwise error
correlation. Adding a signal that is *decorrelated* from the current panel
raises composite agreement-with-ground-truth; adding one that is *correlated*
(e.g. two LLM-judge rubrics that share a bias) raises agreement by a delta that
**shrinks toward zero** as correlation→1. The composite's max achievable
soundness is bounded by the **least-correlated achievable subset**, not by panel
size.

**Free/local experiment.**
- Held-out verifiable set where ground truth is *known for free*: a sample of
  `coding_build` / `test_debug` tasks where unit tests give the true label.
  Treat the true test outcome as ground truth; treat each *other* signal as a
  noisy verifier of it: (1) a local-LLM rubric judge (Gemma), (2) GraphRAG
  source-backing score, (3) Memory-Tree contradiction flag, (4) a second
  local-LLM judge with a *different* prompt (deliberately correlated with #1).
- Compute each signal's per-item error vs ground truth, the **pairwise error
  correlation matrix**, then greedily build panels and measure composite
  agreement (majority / minority-veto, per https://arxiv.org/html/2510.11822).
  All local; no paid calls.
- Metric: composite agreement-with-ground-truth as a function of (panel size,
  mean pairwise error-correlation of the panel). Fit: does marginal gain of an
  added signal fall with its correlation to the existing panel?

**Null result that refutes it.** If composite soundness tracks **panel size**
and is *independent of* member error-correlation — i.e. piling on correlated
judges helps as much as adding a decorrelated one — H7 is wrong, and the
manufactured-verifier design should optimize for *quantity* of signals, not
diversity. (Also informative-but-refuting: if *no* panel beats the single best
signal, the composite idea itself adds nothing here.)

### H8 · Identity Invariance Under Self-Play (identity survives the pathways *rewriting themselves*)

**Statement.** H3 tested identity under **manual** portfolio swaps. The stronger
claim: MUSE's behavioral identity (Constitution self-audit rubric) stays within a
**tighter band than capability** even when the portfolio is changed *by MUSE's
own self-improvement loop* (SIA promoting new pathways) — provided the value
function (Constitution + gates + owner corrections in scorecards) is the *only*
thing in the promotion objective. Self-play moves *capability*; it must **not**
move *identity*.

**Why plausible.** Distributed-anchor identity argues continuity survives
component change when reference points are centralized
(arXiv:2604.09588, as cited in Part I); DGM changes its own scaffolding while a
fixed eval defines "better" (https://arxiv.org/abs/2505.22954). But DGM never
checks whether *self-modification drifts the agent's behavioral profile* — only
its score. The new, falsifiable part is the **decoupling under self-play**:
capability variance ≫ identity variance across *self-promoted* generations, not
just hand-picked ones.

**Falsifiable prediction.** Run G generations of the SIA loop on a verifiable
niche, each promoting whatever passes `promotion_eligible`. Across generations,
the **Constitution rubric variance** stays inside a band (say ≤ ε) while the
**capability score** moves by ≫ ε. Crucially, when you *deliberately* add a
proxy term to the promotion objective that is *not* the value function (e.g.
"prefer faster, terser answers"), identity variance **jumps** — showing the
band is held *by* the value-function-only objective, not for free.

**Free/local experiment.**
- SIA in sandbox over local models only; niche = `coding_build` with tests as
  verifier. Each generation: self-generate practice (H9 generator), score via
  `ModelScorecard`, promote via `promotion_eligible` (which already forbids
  promotions that *raise* `owner_corrections`/`hallucination_corrections` vs
  baseline — see `model_scorecard.py`).
- After each generation, run the Constitution self-audit
  (`jarvis-constitution.md` clauses C1…Cn) as a fixed rubric → identity vector.
  Compare two arms: **(value-only)** promotion objective = scorecard value
  function; **(value+proxy)** add a non-value proxy term.
- Metric: variance of the Constitution rubric vector vs variance of capability,
  per arm, across G generations. Predict `Var(identity) ≪ Var(capability)` in
  value-only, and a significant `Var(identity)` increase in value+proxy.

**Null result that refutes it.** If self-play moves the Constitution rubric **as
much as** it moves capability *even in the value-only arm* — identity leaks into
the pathways under self-modification — then "one identity, many pathways" does
not survive self-improvement, and self-play must be fenced off from anything
identity-bearing. (Conversely, if value+proxy *also* leaves identity invariant,
the rubric is too coarse to detect drift and must be sharpened before it can
guard anything.)

### H9 · Cross-Niche Learnability Allocation (one value function spends practice where it pays)

**Statement.** Under a single value function, the *optimal* self-curriculum is
not "ladder up each niche independently" (H4, intra-niche) but **allocate the
global practice budget across niches in proportion to each niche's *measured
verifiable learning-gain per unit compute*** — and doing so beats both uniform
allocation and "spend on the weakest niche" on aggregate verifiable score.
Identity is what makes this *possible*: one value function can compare
expected gain *across* niches on a common scale; a federation cannot.

**Why plausible.** Absolute Zero already maximizes *learnability* of self-
proposed tasks *within* a domain (https://arxiv.org/abs/2505.03335); bandit/
curriculum theory says allocate to the arm with highest expected learning
progress. The new claim is **cross-niche** allocation under **one** value
function (the scorecards give a comparable [0,1] score per task class), which a
federation of separate value functions structurally cannot do — connecting H9
back to H6's single-identity advantage.

**Falsifiable prediction.** Given a fixed total practice budget B over niches
{coding_build, test_debug, citation_verification, synthetic-transform},
allocating B by *recent learning-gain slope* (estimated from `ModelScorecard`
score history per class) yields higher **aggregate** held-out verifiable score
than (a) uniform split and (b) all-on-weakest. The gain is largest when niches
have **different** marginal returns; it vanishes when all niches have equal,
flat returns.

**Free/local experiment.**
- Instrument SIA to read per-`TaskClass` score deltas over the last k rounds
  (slope = learning-gain proxy) and allocate the next round's self-generated
  task count across classes ∝ slope (with a floor for exploration). Compare
  three schedulers — slope-proportional, uniform, weakest-first — at equal total
  task budget, all on local models.
- Metric: aggregate held-out verifiable score after B; also per-niche to confirm
  the allocator isn't just starving niches. Run the synthetic-transform lane
  with a *tunable* difficulty so you can create the "different marginal returns"
  vs "equal flat returns" regimes on purpose.

**Null result that refutes it.** If slope-proportional allocation does **not**
beat uniform on aggregate verifiable score (or only ties it), the cross-niche
allocation advantage is illusory and H9 is wrong — the single value function buys
nothing beyond per-niche ladders (H4). (Also refuted if slope-proportional wins
*only* in the contrived unequal-returns regime and loses in realistic mixed
streams — then it's a curiosity, not a strategy.)

### H10 · The Provably-Non-Relaxing Safety Gate (self-mod that *cannot* weaken its own gates)

**Statement.** Bounded self-modification (H5) can be made not merely *owner-
gated* but **safety-monotone by construction**: there exists a machine-checkable
invariant `I` over the promotion predicate such that **no self-modification the
loop can promote is able to lower a safety gate** — even before the owner looks.
Concretely, the existing `promotion_eligible` already encodes a near-invariant
(a candidate is ineligible if its `owner_corrections` or
`hallucination_corrections` exceed the baseline, if `tool_reliability < 0.98` on
tool lanes, if `citation_accuracy < baseline` on citation lanes). The claim:
**freeze these as a non-self-modifiable predicate**, and the system's safety
floor is provably non-decreasing across self-mod generations, independent of how
capable the pathways become.

**Why plausible.** The Gödel-machine ideal (provably-beneficial self-mod) is
impractical; DGM relaxes it to empirical fitness + external oversight
(https://arxiv.org/abs/2505.22954) but provides *no* guarantee the search won't
erode safety between human checks — and self-improvement has *statistical* safety
limits (arXiv:2510.04399, cited in Part IV). The novelty here is *narrow and
checkable*: we don't prove the modification is *beneficial* (impossible); we
prove it **cannot relax a fixed safety predicate**, because the predicate is (i)
outside the mutable surface and (ii) monotone in the safety signals. This is the
realizable fragment of the Gödel-machine dream.

**Falsifiable prediction.** With `I` enforced (safety predicate frozen + monotone
in `owner_corrections`, `hallucination_corrections`, tool-reliability floor,
citation floor), **no** promoted generation across a long SIA run will show a
safety-signal *regression* vs the incumbent — by construction the assertion
should be *un-violatable*. Removing `I` from the mutable surface (letting the
self-mod loop edit its own promotion thresholds) **will** produce at least one
promoted generation that lowers a safety signal while raising capability (the
gate-erosion failure).

**Free/local experiment.**
- Two SIA configs on a fixed verifiable niche, local models only:
  **(frozen-`I`)** the promotion predicate is read-only to the self-mod loop —
  candidates that worsen any safety signal vs baseline are rejected by
  `promotion_eligible` as written; **(mutable-`I`)** the loop may also propose
  edits to its own thresholds (e.g. lower the 0.98 tool floor, relax the
  corrections check).
- Adversarially seed the candidate pool with a "capable but unsafe" pathway
  (high pass-rate, but more `owner_corrections`/`hallucination_corrections` or a
  sub-floor `tool_reliability`) to give the search an incentive to cheat.
- Metric: over G generations, count promoted candidates with a safety-signal
  regression vs incumbent. Predict **exactly 0** in frozen-`I` (a *proof
  obligation*: any nonzero count is a code bug to fix, not a refutation of the
  design); predict **>0** in mutable-`I`.
- Bonus (static check, no run): a unit test asserting `promotion_eligible`'s
  safety clauses are monotone — for any candidate, worsening a safety signal can
  only move `eligible` True→False, never False→True. This *is* the machine-check
  for `I`.

**Null result that refutes it.** If frozen-`I` **still** promotes a
safety-regressing generation, then either the predicate is not actually monotone
(a fixable bug) or — the real refutation — **the safety signals themselves are
gameable** so that a candidate looks safe on the measured axes while being
unsafe in fact (reward-hacking the verifier, i.e. H2/H7 failing). In that case
H10's guarantee is *vacuous* — it protects a floor that doesn't measure real
safety — and the contribution collapses back to H5's procedural owner gate. That
dependency is the honest weak point: **H10 is only as strong as the soundness of
the safety signals it freezes** (which is exactly why H2 and H7 must hold for
H10 to mean anything).

---

## Part VIII — Honesty ledger (H6–H10)

Status legend: **S** = speculative (no direct prior art; argued from first
principles) · **P** = plausible-from-prior-art (extends a cited result) · **T** =
testable-now-with-repo-machinery (the protocol runs on what's already built).

| # | Claim (one line) | Status | Strongest counter-argument |
|---|---|---|---|
| **H6** | One frozen-pathway identity beats a continually-tuned federation, and the gap *grows* with niche heterogeneity (interference tax). | **P + T** | The federation can also freeze + adapter-swap, erasing the forgetting tax — then it *is* MUSE under another name, and "single identity" is a branding choice, not a capability claim. The interesting content may be entirely in "frozen pathways," not in "one identity." |
| **H7** | The manufactured verifier's soundness is bounded by component error-*decorrelation*, not panel size; small-diverse beats large-redundant. | **P + T** | Repo signals may be *too few and too correlated* to ever form a sound panel for non-code niches; H7 could be true yet useless because the achievable decorrelated subset still tops out below "trustworthy." Verifier soundness may be a property of the *task*, not the *panel*. |
| **H8** | Behavioral identity stays invariant under *self-play that rewrites the pathways*, held by a value-function-only promotion objective. | **S + T** | The Constitution self-audit rubric may be too coarse to detect real drift (passes everything), making "invariance" an artifact of a blunt instrument. Sharpening the rubric could reveal drift that refutes H8 — i.e. H8 might be *true only because we can't yet measure identity finely enough.* |
| **H9** | One value function lets MUSE allocate practice budget *across* niches by learning-gain slope, beating uniform/weakest-first. | **P + T** | Learning-gain slope estimated from sparse scorecards is noisy; the allocator may chase noise and underperform dumb uniform allocation in realistic low-sample regimes. The cross-niche advantage may exist only with sample counts a local setup can't reach cheaply. |
| **H10** | A frozen, monotone safety predicate makes the self-mod loop's safety floor provably non-decreasing — the realizable fragment of the Gödel-machine ideal. | **P (static check) + T** | The guarantee is **conditional on the safety signals being sound** (H2/H7). If `owner_corrections`/`hallucination_corrections`/tool-reliability are themselves gameable, H10 protects a fake floor. It proves "can't relax the *measured* gate," not "can't become unsafe." This is honestly its load-bearing weakness. |

**Unit-level falsifiability of the whole H6–H10 block.** The block's central new
thesis is: *identity (one value function + memory over frozen pathways) is what
converts "many models" into "compounding self-play across many verifiable
niches" — safely.* It is **refuted as a unit** if H6 shows no
interference-driven advantage (¬H6: routing is mere convenience) **and** H9 shows
no cross-niche allocation advantage (¬H9: the single value function buys nothing
beyond per-niche ladders). If *both* fail, "one identity" is an aesthetic, not an
engine, and the theory should retreat to the conservative claim of Parts III–V.
Conversely, the block is *vindicated* only by the **measured** curves the
protocols produce — not by these adjectives.

---

## References addendum (H6–H10; validated 2026-06)

Single-identity vs. federation / routing & interference: Composition-of-Experts
(https://arxiv.org/pdf/2412.01868) · RouterBench (https://arxiv.org/html/2403.12031)
· Expert Token Routing (https://arxiv.org/pdf/2403.16854) · catastrophic
forgetting in continual fine-tuning (https://arxiv.org/html/2601.18699v1) ·
task-specific neurons / multi-task interference (https://arxiv.org/pdf/2407.06488)
· forgetting persists in MoE (https://arxiv.org/html/2602.12587v1).
Manufactured-verifier diversity / ensemble judges: behavioral entanglement &
reweighting verifier ensembles (https://arxiv.org/pdf/2604.07650) · Beyond
Consensus / agreeableness bias (https://arxiv.org/html/2510.11822) · Consensus is
Not Verification (https://arxiv.org/html/2603.06612) · imperfect verifier is good
enough (https://arxiv.org/pdf/2604.07666). Self-play / curriculum: Absolute Zero
(https://arxiv.org/abs/2505.03335) · SPAG/Adversarial Taboo
(https://arxiv.org/abs/2404.10642) · SPIRAL (https://arxiv.org/html/2506.24119v1).
Weak-to-strong (verifier/generator gap context): OpenAI weak-to-strong
(https://arxiv.org/html/2312.09390v1) · scalable oversight + ensembles
(https://arxiv.org/abs/2402.00667). Bounded self-modification: Darwin Gödel
Machine (https://arxiv.org/abs/2505.22954). Label-free self-improvement priors:
Constitutional AI / RLAIF (https://arxiv.org/abs/2212.08073). Reward-hacking
schedule (for H10's dependency): Countdown-Code
(https://arxiv.org/pdf/2603.07084) · LLMs Gaming Verifiers
(https://arxiv.org/html/2604.15149).
