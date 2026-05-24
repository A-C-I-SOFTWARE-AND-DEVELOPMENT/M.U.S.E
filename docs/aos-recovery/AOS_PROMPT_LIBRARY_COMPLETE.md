# AOS Prompt Library — Complete

> Every prompt template / system-prompt scaffold / copy-paste-ready agent prompt recovered from both repos.
> Each entry: source path · purpose · activation context.

## Hand-authored copy-paste prompts (in this pack)

- **`master-audit-prompt`** — Full council audit of a repo / surface — copy-paste into Hermes / Claude Code / Codex.
  - Path: `skills/aos-enterprise-council/prompts/master-audit-prompt.md`
- **`claude-code-build-prompt`** — Council-governed Claude Code build prompt with risk class + allow/forbid lists.
  - Path: `skills/aos-enterprise-council/prompts/claude-code-build-prompt.md`
- **`codex-implementation-prompt`** — Codex Task Packet (v1) — bounded autonomous code execution contract.
  - Path: `skills/aos-enterprise-council/prompts/codex-implementation-prompt.md`
- **`repo-recovery-prompt`** — Repo-wide AOS recovery prompt — what produced this very pack.
  - Path: `skills/aos-enterprise-council/prompts/repo-recovery-prompt.md`
- **`launch-readiness-prompt`** — Council launch-readiness gate prompt (to be authored).
  - Path: `skills/aos-enterprise-council/prompts/launch-readiness-prompt.md`

## Skill prompts (hazmat `.claude/skills/<name>/SKILL.md`)

Every Anthropic-format SKILL.md is itself a prompt template — frontmatter activates it, body is the system prompt the agent runs.

| Skill | Path |
| --- | --- |
| `claims-substantiation-review` | `recovered-agent-sources/from-hazmat-command/skills/claims-substantiation-review/SKILL.md` |
| `codex-return-envelope-verify` | `recovered-agent-sources/from-hazmat-command/skills/codex-return-envelope-verify/SKILL.md` |
| `codex-task-packet-dispatch` | `recovered-agent-sources/from-hazmat-command/skills/codex-task-packet-dispatch/SKILL.md` |
| `commercial-grade-implementation` | `recovered-agent-sources/from-hazmat-command/skills/commercial-grade-implementation/SKILL.md` |
| `complex-bug-fix` | `recovered-agent-sources/from-hazmat-command/skills/complex-bug-fix/SKILL.md` |
| `compliance-rule-change` | `recovered-agent-sources/from-hazmat-command/skills/compliance-rule-change/SKILL.md` |
| `enterprise-procurement-readiness` | `recovered-agent-sources/from-hazmat-command/skills/enterprise-procurement-readiness/SKILL.md` |
| `evidence-bundle-build` | `recovered-agent-sources/from-hazmat-command/skills/evidence-bundle-build/SKILL.md` |
| `execution-blueprint-compile` | `recovered-agent-sources/from-hazmat-command/skills/execution-blueprint-compile/SKILL.md` |
| `full-autonomous-sprint-router` | `recovered-agent-sources/from-hazmat-command/skills/full-autonomous-sprint-router/SKILL.md` |
| `master-plan-synthesis` | `recovered-agent-sources/from-hazmat-command/skills/master-plan-synthesis/SKILL.md` |
| `mission-brief-build` | `recovered-agent-sources/from-hazmat-command/skills/mission-brief-build/SKILL.md` |
| `multi-plan-council-run` | `recovered-agent-sources/from-hazmat-command/skills/multi-plan-council-run/SKILL.md` |
| `pilot-demo-readiness` | `recovered-agent-sources/from-hazmat-command/skills/pilot-demo-readiness/SKILL.md` |
| `plan-comparison-scorecard` | `recovered-agent-sources/from-hazmat-command/skills/plan-comparison-scorecard/SKILL.md` |
| `post-merge-verification` | `recovered-agent-sources/from-hazmat-command/skills/post-merge-verification/SKILL.md` |
| `pr-readiness-and-owner-handoff` | `recovered-agent-sources/from-hazmat-command/skills/pr-readiness-and-owner-handoff/SKILL.md` |
| `red-team-plan-review` | `recovered-agent-sources/from-hazmat-command/skills/red-team-plan-review/SKILL.md` |
| `release-go-no-go-review` | `recovered-agent-sources/from-hazmat-command/skills/release-go-no-go-review/SKILL.md` |
| `research-dossier-build` | `recovered-agent-sources/from-hazmat-command/skills/research-dossier-build/SKILL.md` |
| `security-or-authz-change` | `recovered-agent-sources/from-hazmat-command/skills/security-or-authz-change/SKILL.md` |

## Hermes-side skill prompts (`skills/<name>/SKILL.md`)

Total: 120 files.

| Skill | Path |
| --- | --- |
| `ai-improvement-radar` | `skills/ai-improvement-radar/SKILL.md` |
| `aos-council-director` | `skills/aos-council-director/SKILL.md` |
| `aos-enterprise-council` | `skills/aos-enterprise-council/SKILL.md` |
| `aos-full-agent-team` | `skills/aos-full-agent-team/SKILL.md` |
| `apple-notes` | `skills/apple/apple-notes/SKILL.md` |
| `apple-reminders` | `skills/apple/apple-reminders/SKILL.md` |
| `findmy` | `skills/apple/findmy/SKILL.md` |
| `imessage` | `skills/apple/imessage/SKILL.md` |
| `macos-computer-use` | `skills/apple/macos-computer-use/SKILL.md` |
| `assurance-risk-director` | `skills/assurance-risk-director/SKILL.md` |
| `claude-code` | `skills/autonomous-ai-agents/claude-code/SKILL.md` |
| `codex` | `skills/autonomous-ai-agents/codex/SKILL.md` |
| `hermes-agent` | `skills/autonomous-ai-agents/hermes-agent/SKILL.md` |
| `kanban-codex-lane` | `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md` |
| `opencode` | `skills/autonomous-ai-agents/opencode/SKILL.md` |
| `best-coding-tool-mission` | `skills/best-coding-tool-mission/SKILL.md` |
| `codex-dispatch-governor` | `skills/codex-dispatch-governor/SKILL.md` |
| `commercial-strategist` | `skills/commercial-strategist/SKILL.md` |
| `competitive-feature-harvester` | `skills/competitive-feature-harvester/SKILL.md` |
| `contrarian-red-flag-analyst` | `skills/contrarian-red-flag-analyst/SKILL.md` |
| `contrarian-reviewer` | `skills/contrarian-reviewer/SKILL.md` |
| `architecture-diagram` | `skills/creative/architecture-diagram/SKILL.md` |
| `ascii-art` | `skills/creative/ascii-art/SKILL.md` |
| `ascii-video` | `skills/creative/ascii-video/SKILL.md` |
| `baoyu-article-illustrator` | `skills/creative/baoyu-article-illustrator/SKILL.md` |
| `baoyu-comic` | `skills/creative/baoyu-comic/SKILL.md` |
| `baoyu-infographic` | `skills/creative/baoyu-infographic/SKILL.md` |
| `claude-design` | `skills/creative/claude-design/SKILL.md` |
| `comfyui` | `skills/creative/comfyui/SKILL.md` |
| `ideation` | `skills/creative/creative-ideation/SKILL.md` |
| `design-md` | `skills/creative/design-md/SKILL.md` |
| `excalidraw` | `skills/creative/excalidraw/SKILL.md` |
| `humanizer` | `skills/creative/humanizer/SKILL.md` |
| `manim-video` | `skills/creative/manim-video/SKILL.md` |
| `p5js` | `skills/creative/p5js/SKILL.md` |
| `pixel-art` | `skills/creative/pixel-art/SKILL.md` |
| `popular-web-designs` | `skills/creative/popular-web-designs/SKILL.md` |
| `pretext` | `skills/creative/pretext/SKILL.md` |
| `sketch` | `skills/creative/sketch/SKILL.md` |
| `songwriting-and-ai-music` | `skills/creative/songwriting-and-ai-music/SKILL.md` |
| `touchdesigner-mcp` | `skills/creative/touchdesigner-mcp/SKILL.md` |
| `jupyter-live-kernel` | `skills/data-science/jupyter-live-kernel/SKILL.md` |
| `decision-quality-gate` | `skills/decision-quality-gate/SKILL.md` |
| `delivery-scope-controller` | `skills/delivery-scope-controller/SKILL.md` |
| `developer-ux-command-center` | `skills/developer-ux-command-center/SKILL.md` |
| `kanban-orchestrator` | `skills/devops/kanban-orchestrator/SKILL.md` |
| `kanban-worker` | `skills/devops/kanban-worker/SKILL.md` |
| `webhook-subscriptions` | `skills/devops/webhook-subscriptions/SKILL.md` |
| `dogfood` | `skills/dogfood/SKILL.md` |
| `himalaya` | `skills/email/himalaya/SKILL.md` |
| `enterprise-customer-service` | `skills/enterprise-council/customer-service/SKILL.md` |
| `enterprise-finance` | `skills/enterprise-council/finance/SKILL.md` |
| `enterprise-hr` | `skills/enterprise-council/hr/SKILL.md` |
| `enterprise-judge` | `skills/enterprise-council/judge/SKILL.md` |
| `enterprise-monitor` | `skills/enterprise-council/monitor/SKILL.md` |
| `enterprise-operations` | `skills/enterprise-council/operations/SKILL.md` |
| `enterprise-orchestrator` | `skills/enterprise-council/orchestrator/SKILL.md` |
| `enterprise-sales` | `skills/enterprise-council/sales/SKILL.md` |
| `evidence-architect` | `skills/evidence-architect/SKILL.md` |
| `minecraft-modpack-server` | `skills/gaming/minecraft-modpack-server/SKILL.md` |
| `pokemon-player` | `skills/gaming/pokemon-player/SKILL.md` |
| `github-publisher` | `skills/github-publisher/SKILL.md` |
| `codebase-inspection` | `skills/github/codebase-inspection/SKILL.md` |
| `github-auth` | `skills/github/github-auth/SKILL.md` |
| `github-code-review` | `skills/github/github-code-review/SKILL.md` |
| `github-issues` | `skills/github/github-issues/SKILL.md` |
| `github-pr-workflow` | `skills/github/github-pr-workflow/SKILL.md` |
| `github-repo-management` | `skills/github/github-repo-management/SKILL.md` |
| `hermes-orchestration-pipeline` | `skills/hermes-orchestration-pipeline/SKILL.md` |
| `local-quality-gate` | `skills/local-quality-gate/SKILL.md` |
| `native-mcp` | `skills/mcp/native-mcp/SKILL.md` |
| `gif-search` | `skills/media/gif-search/SKILL.md` |
| `heartmula` | `skills/media/heartmula/SKILL.md` |
| `songsee` | `skills/media/songsee/SKILL.md` |
| `spotify` | `skills/media/spotify/SKILL.md` |
| `youtube-content` | `skills/media/youtube-content/SKILL.md` |
| `evaluating-llms-harness` | `skills/mlops/evaluation/lm-evaluation-harness/SKILL.md` |
| `weights-and-biases` | `skills/mlops/evaluation/weights-and-biases/SKILL.md` |
| `huggingface-hub` | `skills/mlops/huggingface-hub/SKILL.md` |
| `llama-cpp` | `skills/mlops/inference/llama-cpp/SKILL.md` |
| `obliteratus` | `skills/mlops/inference/obliteratus/SKILL.md` |
| `serving-llms-vllm` | `skills/mlops/inference/vllm/SKILL.md` |
| `audiocraft-audio-generation` | `skills/mlops/models/audiocraft/SKILL.md` |
| `segment-anything-model` | `skills/mlops/models/segment-anything/SKILL.md` |
| `dspy` | `skills/mlops/research/dspy/SKILL.md` |
| `model-router` | `skills/model-router/SKILL.md` |
| `obsidian` | `skills/note-taking/obsidian/SKILL.md` |
| `principal-systems-architect` | `skills/principal-systems-architect/SKILL.md` |
| `product-experience-architect` | `skills/product-experience-architect/SKILL.md` |
| `airtable` | `skills/productivity/airtable/SKILL.md` |
| `google-workspace` | `skills/productivity/google-workspace/SKILL.md` |
| `linear` | `skills/productivity/linear/SKILL.md` |
| `maps` | `skills/productivity/maps/SKILL.md` |
| `nano-pdf` | `skills/productivity/nano-pdf/SKILL.md` |
| `notion` | `skills/productivity/notion/SKILL.md` |
| `ocr-and-documents` | `skills/productivity/ocr-and-documents/SKILL.md` |
| `powerpoint` | `skills/productivity/powerpoint/SKILL.md` |
| `teams-meeting-pipeline` | `skills/productivity/teams-meeting-pipeline/SKILL.md` |
| `godmode` | `skills/red-teaming/godmode/SKILL.md` |
| `research-validator` | `skills/research-validator/SKILL.md` |
| `arxiv` | `skills/research/arxiv/SKILL.md` |
| `blogwatcher` | `skills/research/blogwatcher/SKILL.md` |
| `llm-wiki` | `skills/research/llm-wiki/SKILL.md` |
| `polymarket` | `skills/research/polymarket/SKILL.md` |
| `research-paper-writing` | `skills/research/research-paper-writing/SKILL.md` |
| `self-improvement-loop` | `skills/self-improvement-loop/SKILL.md` |
| `openhue` | `skills/smart-home/openhue/SKILL.md` |
| `xurl` | `skills/social-media/xurl/SKILL.md` |
| `debugging-hermes-tui-commands` | `skills/software-development/debugging-hermes-tui-commands/SKILL.md` |
| `hermes-agent-skill-authoring` | `skills/software-development/hermes-agent-skill-authoring/SKILL.md` |
| `node-inspect-debugger` | `skills/software-development/node-inspect-debugger/SKILL.md` |
| `plan` | `skills/software-development/plan/SKILL.md` |
| `python-debugpy` | `skills/software-development/python-debugpy/SKILL.md` |
| `requesting-code-review` | `skills/software-development/requesting-code-review/SKILL.md` |
| `spike` | `skills/software-development/spike/SKILL.md` |
| `subagent-driven-development` | `skills/software-development/subagent-driven-development/SKILL.md` |
| `systematic-debugging` | `skills/software-development/systematic-debugging/SKILL.md` |
| `test-driven-development` | `skills/software-development/test-driven-development/SKILL.md` |
| `writing-plans` | `skills/software-development/writing-plans/SKILL.md` |
| `yuanbao` | `skills/yuanbao/SKILL.md` |

## Hermes optional skill prompts (`optional-skills/<name>/SKILL.md`)

Total: 81 files.

| Skill | Path |
| --- | --- |
| `blackbox` | `optional-skills/autonomous-ai-agents/blackbox/SKILL.md` |
| `honcho` | `optional-skills/autonomous-ai-agents/honcho/SKILL.md` |
| `evm` | `optional-skills/blockchain/evm/SKILL.md` |
| `hyperliquid` | `optional-skills/blockchain/hyperliquid/SKILL.md` |
| `solana` | `optional-skills/blockchain/solana/SKILL.md` |
| `one-three-one-rule` | `optional-skills/communication/one-three-one-rule/SKILL.md` |
| `blender-mcp` | `optional-skills/creative/blender-mcp/SKILL.md` |
| `concept-diagrams` | `optional-skills/creative/concept-diagrams/SKILL.md` |
| `hyperframes` | `optional-skills/creative/hyperframes/SKILL.md` |
| `kanban-video-orchestrator` | `optional-skills/creative/kanban-video-orchestrator/SKILL.md` |
| `meme-generation` | `optional-skills/creative/meme-generation/SKILL.md` |
| `inference-sh-cli` | `optional-skills/devops/cli/SKILL.md` |
| `docker-management` | `optional-skills/devops/docker-management/SKILL.md` |
| `pinggy-tunnel` | `optional-skills/devops/pinggy-tunnel/SKILL.md` |
| `watchers` | `optional-skills/devops/watchers/SKILL.md` |
| `adversarial-ux-test` | `optional-skills/dogfood/adversarial-ux-test/SKILL.md` |
| `agentmail` | `optional-skills/email/agentmail/SKILL.md` |
| `3-statement-model` | `optional-skills/finance/3-statement-model/SKILL.md` |
| `comps-analysis` | `optional-skills/finance/comps-analysis/SKILL.md` |
| `dcf-model` | `optional-skills/finance/dcf-model/SKILL.md` |
| `excel-author` | `optional-skills/finance/excel-author/SKILL.md` |
| `lbo-model` | `optional-skills/finance/lbo-model/SKILL.md` |
| `merger-model` | `optional-skills/finance/merger-model/SKILL.md` |
| `pptx-author` | `optional-skills/finance/pptx-author/SKILL.md` |
| `stocks` | `optional-skills/finance/stocks/SKILL.md` |
| `fitness-nutrition` | `optional-skills/health/fitness-nutrition/SKILL.md` |
| `neuroskill-bci` | `optional-skills/health/neuroskill-bci/SKILL.md` |
| `fastmcp` | `optional-skills/mcp/fastmcp/SKILL.md` |
| `mcporter` | `optional-skills/mcp/mcporter/SKILL.md` |
| `openclaw-migration` | `optional-skills/migration/openclaw-migration/SKILL.md` |
| `huggingface-accelerate` | `optional-skills/mlops/accelerate/SKILL.md` |
| `chroma` | `optional-skills/mlops/chroma/SKILL.md` |
| `clip` | `optional-skills/mlops/clip/SKILL.md` |
| `faiss` | `optional-skills/mlops/faiss/SKILL.md` |
| `optimizing-attention-flash` | `optional-skills/mlops/flash-attention/SKILL.md` |
| `guidance` | `optional-skills/mlops/guidance/SKILL.md` |
| `huggingface-tokenizers` | `optional-skills/mlops/huggingface-tokenizers/SKILL.md` |
| `outlines` | `optional-skills/mlops/inference/outlines/SKILL.md` |
| `instructor` | `optional-skills/mlops/instructor/SKILL.md` |
| `lambda-labs-gpu-cloud` | `optional-skills/mlops/lambda-labs/SKILL.md` |
| `llava` | `optional-skills/mlops/llava/SKILL.md` |
| `modal-serverless-gpu` | `optional-skills/mlops/modal/SKILL.md` |
| `nemo-curator` | `optional-skills/mlops/nemo-curator/SKILL.md` |
| `peft-fine-tuning` | `optional-skills/mlops/peft/SKILL.md` |
| `pinecone` | `optional-skills/mlops/pinecone/SKILL.md` |
| `pytorch-fsdp` | `optional-skills/mlops/pytorch-fsdp/SKILL.md` |
| `pytorch-lightning` | `optional-skills/mlops/pytorch-lightning/SKILL.md` |
| `qdrant-vector-search` | `optional-skills/mlops/qdrant/SKILL.md` |
| `sparse-autoencoder-training` | `optional-skills/mlops/saelens/SKILL.md` |
| `simpo-training` | `optional-skills/mlops/simpo/SKILL.md` |
| `slime-rl-training` | `optional-skills/mlops/slime/SKILL.md` |
| `stable-diffusion-image-generation` | `optional-skills/mlops/stable-diffusion/SKILL.md` |
| `tensorrt-llm` | `optional-skills/mlops/tensorrt-llm/SKILL.md` |
| `distributed-llm-pretraining-torchtitan` | `optional-skills/mlops/torchtitan/SKILL.md` |
| `axolotl` | `optional-skills/mlops/training/axolotl/SKILL.md` |
| `fine-tuning-with-trl` | `optional-skills/mlops/training/trl-fine-tuning/SKILL.md` |
| `unsloth` | `optional-skills/mlops/training/unsloth/SKILL.md` |
| `whisper` | `optional-skills/mlops/whisper/SKILL.md` |
| `canvas` | `optional-skills/productivity/canvas/SKILL.md` |
| `here.now` | `optional-skills/productivity/here-now/SKILL.md` |
| `memento-flashcards` | `optional-skills/productivity/memento-flashcards/SKILL.md` |
| `shop-app` | `optional-skills/productivity/shop-app/SKILL.md` |
| `shopify` | `optional-skills/productivity/shopify/SKILL.md` |
| `siyuan` | `optional-skills/productivity/siyuan/SKILL.md` |
| `telephony` | `optional-skills/productivity/telephony/SKILL.md` |
| `bioinformatics` | `optional-skills/research/bioinformatics/SKILL.md` |
| `darwinian-evolver` | `optional-skills/research/darwinian-evolver/SKILL.md` |
| `domain-intel` | `optional-skills/research/domain-intel/SKILL.md` |
| `drug-discovery` | `optional-skills/research/drug-discovery/SKILL.md` |
| `duckduckgo-search` | `optional-skills/research/duckduckgo-search/SKILL.md` |
| `gitnexus-explorer` | `optional-skills/research/gitnexus-explorer/SKILL.md` |
| `osint-investigation` | `optional-skills/research/osint-investigation/SKILL.md` |
| `parallel-cli` | `optional-skills/research/parallel-cli/SKILL.md` |
| `qmd` | `optional-skills/research/qmd/SKILL.md` |
| `scrapling` | `optional-skills/research/scrapling/SKILL.md` |
| `searxng-search` | `optional-skills/research/searxng-search/SKILL.md` |
| `1password` | `optional-skills/security/1password/SKILL.md` |
| `oss-forensics` | `optional-skills/security/oss-forensics/SKILL.md` |
| `sherlock` | `optional-skills/security/sherlock/SKILL.md` |
| `rest-graphql-debug` | `optional-skills/software-development/rest-graphql-debug/SKILL.md` |
| `page-agent` | `optional-skills/web-development/page-agent/SKILL.md` |
