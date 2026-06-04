# Training-data capability clusters

This doc explains the **clusters** added to the open-data-sources registry
(`docs/ai-intelligence/open-data-sources.yaml`, schema v2): why each exists,
which Hermes capability domain and model routing task-class it trains, the
free/permissive datasets in it, and the evidence that each cluster produces a
**qualitative improvement** (the validation pass).

## The gap (why clusters were added)

The original registry (21 sources) was **100% GitHub/code/SWE** — The Stack v2,
GH Archive, GitHub BigQuery, Software Heritage, SWE-bench, etc. But Hermes'
actual model routing (`docs/ai-intelligence/model-routing-task-classes.md`) and
its agent/skill inventory span far more than code:

- it is fundamentally a **tool / MCP / function-calling agent** (177 "hermes"
  integration agents, the `mcp` skill, `model_tools.py`) — yet had **zero**
  agentic training data;
- it has a **research engine + citation/evidence gate**, a **planner/strategy/
  critic** reasoning path, conversational **companion/mobile/voice** surfaces,
  and a **constitution + verification gates + self-audit** safety layer — none
  of which had matching training data.

Clusters group sources by the capability domain they train, so ingestion and
fine-tuning can target the lanes that actually move the product.

## The clusters

| Cluster | Capability domains | Model task-classes | Core-ingest sources |
|---|---|---|---|
| `code-github` (existing) | code build/review, repo nav, test-debug | `coding_*`, `test_debug` | The Stack v2, GH Archive, BigQuery, SWH, SWE-smith, CodeNet, The Vault, CommitPackFT, D2A, TravisTorrent |
| `agentic-tool-use` | tool-use, function-calling, MCP, orchestration | `coding_build`, `tool_reliability` | **TOUCAN** (Apache-2.0), **xLAM-60k** (CC-BY-4.0) |
| `instruction-following` | companion, chat, summarization | `mobile_chat`, `voice_reply`, `summarization` | **SmolTalk** (Apache-2.0) |
| `reasoning-math` | planning, strategy, critic | `coding_plan`, `research` | **OpenR1-Math-220k**, **OpenThoughts2-1M**, **NuminaMath-CoT** (all Apache-2.0) |
| `research-rag-citations` | research, evidence-verification, citations, memory | `research`, `citation_verification`, `memory_curator` | **ASQA** (Apache-2.0) |
| `preference-safety` | alignment, safety, refusal, owner-gates | `coding_review`, `research` | **HelpSteer3** (CC-BY-4.0) |

Non-core sources in each cluster (Tülu-3-SFT, Infinity-Instruct, ToolMind,
NQ-open, HotpotQA, UltraFeedback, PKU-SafeRLHF) are tracked but flagged
`verify_at_ingest` / `mixed` for license or content reasons — see their
`license_notes` in the YAML.

## Validation — do the clusters make sense and produce qualitative gains?

Each cluster maps to a **measured** capability lane and is backed by published
evidence that training on its data improves that lane:

- **agentic-tool-use** — the single highest-value gap. **TOUCAN** (1.5M
  trajectories synthesized from *495 real MCP servers / 2,000+ tools*) reports
  fine-tuned models **beating larger closed models on BFCL V3** and extending
  the **MCP-Universe** Pareto frontier — i.e., directly the multi-tool/MCP loop
  Hermes runs. **xLAM-60k** is execution-verified with **>95% human-rated
  function-call correctness**. Hermes routes on a `tool_reliability` scorecard
  axis with a 0.98 floor — this cluster is exactly what raises it.
- **reasoning-math** — **OpenThoughts2-1M** is the first *public* reasoning data
  to let an open model (**OpenThinker2-32B**) match **DeepSeek-R1-Distill-32B**
  on **AIME / LiveCodeBench**; **OpenR1-Math-220k** ships R1 traces verified by
  Math-Verify. Trains the planner/critic decomposition that orchestration and
  the `coding_plan` lane depend on.
- **instruction-following** — **SmolTalk** (the SmolLM2 SFT mix) and Tülu-3 are
  the strongest permissive general-SFT mixtures; they lift the companion/chat/
  summarization surfaces (`mobile_chat`, `voice_reply`) that every gateway uses.
- **research-rag-citations** — **ASQA** (part of the ALCE citation benchmark)
  trains *attributable* long-form answers; **HotpotQA** trains multi-hop
  supporting-evidence selection. These map 1:1 onto the research engine's
  citation/evidence-verification gate and the `citation_verification` task-class.
- **preference-safety** — **HelpSteer3** (clean CC-BY-4.0 multi-attribute
  preferences) calibrates the reviewer lane and reward modeling; **PKU-SafeRLHF**
  (decoupled help/harm) supports refusal/owner-gate behavior — backing the
  constitution and verification gates.

Conclusion: the six clusters are a 1:1 cover of Hermes' routed capability
domains, each justified by a real benchmark gain, with the agentic-tool-use and
reasoning clusters closing the largest gaps. License postures are conservative
(only Apache/MIT/CC-BY marked core; share-alike, mixed, and own-license sources
are `verify_at_ingest`).

## Using it

```bash
# Browse clusters and their source counts / task-classes
python -m hermes_cli.jarvis_prime data-sources clusters

# List sources in one cluster (or just the core-ingest set)
python -m hermes_cli.jarvis_prime data-sources list --cluster agentic-tool-use --core

# Bridge every source into the Research Vault as a provenance card
python -m hermes_cli.jarvis_prime data-sources register-vault --dry-run
```

Ingestion path (already wired): registry → `register-vault` →
`learning_ingest.from_research_artifact` → owner-approved `DatasetStore` →
`hermes_cli.nlp_training` validation → Together LoRA SFT
(`docs/nlp_training.md`). All license-aware and owner-gated.

## Keeping it current ("train on constantly")

The registry is the refresh point. To keep clusters current: re-run the
research, add/update entries (new datasets get a `cluster` + accurate
`legal_posture`), bump `as_of`, and re-`register-vault`. Only `core_ingest`
sources with clearly permissive licenses (Apache/MIT/CC-BY) should be marked for
default training; everything else stays `verify_at_ingest` until checked. The
`benchmark_wall` set is never trained on (decontamination).
