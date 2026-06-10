# AOS Full Source Inventory

> **Generated:** 2026-05-24 by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw`.
>
> One row per file scanned across both source repos plus the on-disk snapshot at `recovered-agent-sources/`.
> Categories: `AGENT-SPEC`, `SUB-AGENT-SPEC`, `SKILL`, `WORKFLOW`, `PROMPT`, `RULE`, `GOVERNANCE`, `TEMPLATE`, `WORKER-PROFILE`, `MEMORY-CONFIG`, `ROUTING-CONFIG`, `PERSONA`, `INDEX`, `RECOVERY-ARTIFACT`, `OTHER`.
> Confidence labels: `HIGH` (file is self-evidently this kind of artifact), `MEDIUM` (inferred from filename / one section), `LOW` (unclear, flagged for review).
>
> Companion files: `AOS_AGENT_REGISTRY_COMPLETE.md`, `AOS_SUBAGENT_REGISTRY_COMPLETE.md`,
> `AOS_PROMPT_LIBRARY_COMPLETE.md`, `AOS_WORKFLOW_LIBRARY_COMPLETE.md`,
> `AOS_MEMORY_AND_CONTEXT_RECOVERY.md`, `AOS_DUPLICATE_AND_CONFLICT_REPORT.md`,
> `AOS_AGENT_RECOVERY_REPORT.md`, `AOS_INSTALLATION_REPORT.md`.

## Summary counts

| Source | Count |
| --- | --- |
| Hermes-agent live `skills/**/SKILL.md` | 120 |
| Hermes-agent live `optional-skills/**/SKILL.md` | 81 |
| Hermes-agent live `docs/orchestration/**/*.md` | 35 |
| Hermes-agent live `enterprise/**/*.py` | 13 |
| Snapshot `recovered-agent-sources/from-hazmat-command/agents/` | 11 |
| Snapshot `recovered-agent-sources/from-hazmat-command/skills/` | 21 |
| Snapshot `recovered-agent-sources/from-hazmat-command/rules/` | 7 |
| Snapshot `recovered-agent-sources/from-hazmat-command/docs/agents/` | 11 |
| Snapshot `recovered-agent-sources/from-hazmat-command/docs/governance/` | 19 |
| Snapshot `recovered-agent-sources/from-hazmat-command/docs/workflows/` | 12 |
| Snapshot `recovered-agent-sources/from-hazmat-command/docs/skills/` | 41 |
| Snapshot `recovered-agent-sources/from-hazmat-command/docs/templates/` | 22 |
| Snapshot `recovered-agent-sources/from-hermes-agent/` SKILL.md | 17 |
| **Snapshot total (all files in `recovered-agent-sources/`)** | **166** |


## File inventory (one row per file)

| Path | Source repo | Subsystem | Category | Confidence | Detected name | One-line note |
| --- | --- | --- | --- | --- | --- | --- |
| `skills/ai-improvement-radar/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | ai-improvement-radar | Track\ AI\ coding-agent\ improvements\ (Codex,\ Claude\ Code,\ Aider,\ Goose,\ Continue,\  |
| `skills/aos-council-director/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | aos-council-director | Director:\ decomposes\ goal,\ dispatches\ AoS\ council,\ decides. |
| `skills/aos-enterprise-council/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | aos-enterprise-council | AOS\ Enterprise\ Council\ —\ full\ 11-division\ autonomous-enterprise\ smart\ team\ (chi |
| `skills/aos-full-agent-team/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | aos-full-agent-team | Full\ AoS\ council:\ spin\ up\ all\ 16\ specialists\ end-to-end. |
| `skills/apple/apple-notes/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | apple-notes | Manage\ Apple\ Notes\ via\ memo\ CLI:\ create,\ search,\ edit. |
| `skills/apple/apple-reminders/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | apple-reminders | Apple\ Reminders\ via\ remindctl:\ add,\ list,\ complete. |
| `skills/apple/findmy/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | findmy | Track\ Apple\ devices/AirTags\ via\ FindMy.app\ on\ macOS. |
| `skills/apple/imessage/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | imessage | Send\ and\ receive\ iMessages/SMS\ via\ the\ imsg\ CLI\ on\ macOS. |
| `skills/apple/macos-computer-use/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | macos-computer-use | / |
| `skills/assurance-risk-director/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | assurance-risk-director | Risk\ director:\ safety,\ security,\ legal,\ compliance,\ veto. |
| `skills/autonomous-ai-agents/claude-code/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | claude-code | Delegate\ coding\ to\ Claude\ Code\ CLI\ (features,\ PRs). |
| `skills/autonomous-ai-agents/codex/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | codex | Delegate\ coding\ to\ OpenAI\ Codex\ CLI\ (features,\ PRs). |
| `skills/autonomous-ai-agents/hermes-agent/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | hermes-agent | Configure,\ extend,\ or\ contribute\ to\ Hermes\ Agent. |
| `skills/autonomous-ai-agents/kanban-codex-lane/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | kanban-codex-lane | Use\ when\ a\ Hermes\ Kanban\ worker\ wants\ to\ run\ Codex\ CLI\ as\ an\ isolated\ implem |
| `skills/autonomous-ai-agents/opencode/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | opencode | Delegate\ coding\ to\ OpenCode\ CLI\ (features,\ PR\ review). |
| `skills/best-coding-tool-mission/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | best-coding-tool-mission | Anchor\ every\ job\ to\ Hermes'\ mission\ as\ the\ best\ private\ local-first\ developer\  |
| `skills/codex-dispatch-governor/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | codex-dispatch-governor | Routes\ coding\ tasks\ to\ Codex/external\ agents\ safely. |
| `skills/commercial-strategist/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | commercial-strategist | Owns\ commercial\ angle:\ market,\ GTM,\ pricing,\ competition. |
| `skills/competitive-feature-harvester/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | competitive-feature-harvester | Harvest\ competitor\ agent\ features\ into\ a\ Hermes\ backlog. |
| `skills/contrarian-red-flag-analyst/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | contrarian-red-flag-analyst | Alias\ of\ contrarian-reviewer\ (legacy\ upstream\ name). |
| `skills/contrarian-reviewer/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | contrarian-reviewer | Devil's\ advocate:\ red\ flags,\ weak\ arguments,\ blind\ spots. |
| `skills/creative/architecture-diagram/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | architecture-diagram | Dark-themed\ SVG\ architecture/cloud/infra\ diagrams\ as\ HTML. |
| `skills/creative/ascii-art/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | ascii-art | ASCII\ art:\ pyfiglet,\ cowsay,\ boxes,\ image-to-ascii. |
| `skills/creative/ascii-video/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | ascii-video | ASCII\ video:\ convert\ video/audio\ to\ colored\ ASCII\ MP4/GIF. |
| `skills/creative/baoyu-article-illustrator/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | baoyu-article-illustrator | Article\ illustrations:\ type\ ×\ style\ ×\ palette\ consistency. |
| `skills/creative/baoyu-comic/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | baoyu-comic | Knowledge\ comics\ (知识漫画):\ educational,\ biography,\ tutorial. |
| `skills/creative/baoyu-infographic/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | baoyu-infographic | Infographics:\ 21\ layouts\ x\ 21\ styles\ (信息图,\ 可视化). |
| `skills/creative/claude-design/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | claude-design | Design\ one-off\ HTML\ artifacts\ (landing,\ deck,\ prototype). |
| `skills/creative/comfyui/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | comfyui | Generate\ images,\ video,\ and\ audio\ with\ ComfyUI\ —\ install,\ launch,\ manage\ node |
| `skills/creative/creative-ideation/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | ideation | Generate\ project\ ideas\ via\ creative\ constraints. |
| `skills/creative/design-md/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | design-md | Author/validate/export\ Google's\ DESIGN.md\ token\ spec\ files. |
| `skills/creative/excalidraw/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | excalidraw | Hand-drawn\ Excalidraw\ JSON\ diagrams\ (arch,\ flow,\ seq). |
| `skills/creative/humanizer/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | humanizer | Humanize\ text:\ strip\ AI-isms\ and\ add\ real\ voice. |
| `skills/creative/manim-video/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | manim-video | Manim\ CE\ animations:\ 3Blue1Brown\ math/algo\ videos. |
| `skills/creative/p5js/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | p5js | p5.js\ sketches:\ gen\ art,\ shaders,\ interactive,\ 3D. |
| `skills/creative/pixel-art/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | pixel-art | Pixel\ art\ w/\ era\ palettes\ (NES,\ Game\ Boy,\ PICO-8). |
| `skills/creative/popular-web-designs/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | popular-web-designs | 54\ real\ design\ systems\ (Stripe,\ Linear,\ Vercel)\ as\ HTML/CSS. |
| `skills/creative/pretext/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | pretext | Use\ when\ building\ creative\ browser\ demos\ with\ @chenglou/pretext\ —\ DOM-free\ tex |
| `skills/creative/sketch/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | sketch | Throwaway\ HTML\ mockups:\ 2-3\ design\ variants\ to\ compare. |
| `skills/creative/songwriting-and-ai-music/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | songwriting-and-ai-music | Songwriting\ craft\ and\ Suno\ AI\ music\ prompts. |
| `skills/creative/touchdesigner-mcp/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | touchdesigner-mcp | Control\ a\ running\ TouchDesigner\ instance\ via\ twozero\ MCP\ —\ create\ operators,\  |
| `skills/data-science/jupyter-live-kernel/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | jupyter-live-kernel | Iterative\ Python\ via\ live\ Jupyter\ kernel\ (hamelnb). |
| `skills/decision-quality-gate/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | decision-quality-gate | Force\ Hermes\ to\ produce\ a\ visible\ decision\ ledger\ before\ non-trivial\ actions\ — |
| `skills/delivery-scope-controller/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | delivery-scope-controller | Owns\ scope,\ sequencing,\ dependencies,\ delivery\ shape. |
| `skills/developer-ux-command-center/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | developer-ux-command-center | Developer-facing\ surface\ for\ the\ Hermes\ orchestration\ pipeline.\ Use\ to\ drive\ scr |
| `skills/devops/kanban-orchestrator/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | kanban-orchestrator | Decomposition\ playbook\ +\ anti-temptation\ rules\ for\ an\ orchestrator\ profile\ routin |
| `skills/devops/kanban-worker/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | kanban-worker | Pitfalls,\ examples,\ and\ edge\ cases\ for\ Hermes\ Kanban\ workers.\ The\ lifecycle\ its |
| `skills/devops/webhook-subscriptions/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | webhook-subscriptions | Webhook\ subscriptions:\ event-driven\ agent\ runs. |
| `skills/dogfood/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | dogfood | Exploratory\ QA\ of\ web\ apps:\ find\ bugs,\ evidence,\ reports. |
| `skills/email/himalaya/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | himalaya | Himalaya\ CLI:\ IMAP/SMTP\ email\ from\ terminal. |
| `skills/enterprise-council/customer-service/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-customer-service | CS\ leaf:\ ticket\ classification,\ knowledge\ base\ retrieval,\ escalation,\ mass\ commun |
| `skills/enterprise-council/finance/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-finance | Finance\ leaf:\ invoicing,\ budgeting,\ reporting\ against\ Stripe/NetSuite/QuickBooks. |
| `skills/enterprise-council/hr/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-hr | HR\ leaf:\ recruitment\ screening,\ policy\ lookup,\ offer\ +\ termination\ workflows. |
| `skills/enterprise-council/judge/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-judge | Validator\ /\ Judge:\ schema\ +\ policy\ +\ parallel-pass\ cross-checks\ on\ every\ leaf\  |
| `skills/enterprise-council/monitor/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-monitor | Post-run\ reviewer:\ scans\ the\ audit\ trail,\ proposes\ improvements,\ hands\ them\ to\  |
| `skills/enterprise-council/operations/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-operations | Operations\ leaf:\ logistics\ planning\ +\ execution,\ compliance\ checks\ +\ filings,\ in |
| `skills/enterprise-council/orchestrator/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-orchestrator | Decompose\ a\ one-tap\ enterprise\ goal\ into\ autonomous\ tasks\ across\ domain\ agents. |
| `skills/enterprise-council/sales/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | enterprise-sales | Sales\ leaf:\ lead\ tracking,\ proposal\ drafting\ +\ sending,\ contract\ execution,\ disc |
| `skills/evidence-architect/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | evidence-architect | Builds\ the\ evidence\ base:\ facts,\ citations,\ provenance. |
| `skills/gaming/minecraft-modpack-server/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | minecraft-modpack-server | Host\ modded\ Minecraft\ servers\ (CurseForge,\ Modrinth). |
| `skills/gaming/pokemon-player/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | pokemon-player | Play\ Pokemon\ via\ headless\ emulator\ +\ RAM\ reads. |
| `skills/github-publisher/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-publisher | Promote\ a\ Hermes\ orchestration\ job's\ github/\ artifacts\ (branch,\ commit\ message,\  |
| `skills/github/codebase-inspection/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | codebase-inspection | Inspect\ codebases\ w/\ pygount:\ LOC,\ languages,\ ratios. |
| `skills/github/github-auth/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-auth | GitHub\ auth\ setup:\ HTTPS\ tokens,\ SSH\ keys,\ gh\ CLI\ login. |
| `skills/github/github-code-review/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-code-review | Review\ PRs:\ diffs,\ inline\ comments\ via\ gh\ or\ REST. |
| `skills/github/github-issues/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-issues | Create,\ triage,\ label,\ assign\ GitHub\ issues\ via\ gh\ or\ REST. |
| `skills/github/github-pr-workflow/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-pr-workflow | GitHub\ PR\ lifecycle:\ branch,\ commit,\ open,\ CI,\ merge. |
| `skills/github/github-repo-management/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | github-repo-management | Clone/create/fork\ repos;\ manage\ remotes,\ releases. |
| `skills/hermes-orchestration-pipeline/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | hermes-orchestration-pipeline | Phase-02\ foundation\ contract\ for\ the\ Hermes\ multi-worker\ orchestration\ pipeline.\  |
| `skills/local-quality-gate/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | local-quality-gate | Run\ local\ validation\ gates\ against\ a\ workspace\ before\ publishing\ —\ git/secrets |
| `skills/mcp/native-mcp/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | native-mcp | MCP\ client:\ connect\ servers,\ register\ tools\ (stdio/HTTP). |
| `skills/media/gif-search/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | gif-search | Search/download\ GIFs\ from\ Tenor\ via\ curl\ +\ jq. |
| `skills/media/heartmula/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | heartmula | HeartMuLa:\ Suno-like\ song\ generation\ from\ lyrics\ +\ tags. |
| `skills/media/songsee/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | songsee | Audio\ spectrograms/features\ (mel,\ chroma,\ MFCC)\ via\ CLI. |
| `skills/media/spotify/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | spotify | Spotify:\ play,\ search,\ queue,\ manage\ playlists\ and\ devices. |
| `skills/media/youtube-content/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | youtube-content | YouTube\ transcripts\ to\ summaries,\ threads,\ blogs. |
| `skills/mlops/evaluation/lm-evaluation-harness/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | evaluating-llms-harness | lm-eval-harness:\ benchmark\ LLMs\ (MMLU,\ GSM8K,\ etc.). |
| `skills/mlops/evaluation/weights-and-biases/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | weights-and-biases | W&B:\ log\ ML\ experiments,\ sweeps,\ model\ registry,\ dashboards. |
| `skills/mlops/huggingface-hub/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | huggingface-hub | HuggingFace\ hf\ CLI:\ search/download/upload\ models,\ datasets. |
| `skills/mlops/inference/llama-cpp/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | llama-cpp | llama.cpp\ local\ GGUF\ inference\ +\ HF\ Hub\ model\ discovery. |
| `skills/mlops/inference/obliteratus/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | obliteratus | OBLITERATUS:\ abliterate\ LLM\ refusals\ (diff-in-means). |
| `skills/mlops/inference/vllm/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | serving-llms-vllm | vLLM:\ high-throughput\ LLM\ serving,\ OpenAI\ API,\ quantization. |
| `skills/mlops/models/audiocraft/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | audiocraft-audio-generation | AudioCraft:\ MusicGen\ text-to-music,\ AudioGen\ text-to-sound. |
| `skills/mlops/models/segment-anything/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | segment-anything-model | SAM:\ zero-shot\ image\ segmentation\ via\ points,\ boxes,\ masks. |
| `skills/mlops/research/dspy/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | dspy | DSPy:\ declarative\ LM\ programs,\ auto-optimize\ prompts,\ RAG. |
| `skills/model-router/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | model-router | Choose\ the\ best\ worker/model\ mix\ for\ each\ Hermes\ workflow.\ Considers\ task\ type, |
| `skills/note-taking/obsidian/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | obsidian | Read,\ search,\ create,\ and\ edit\ notes\ in\ the\ Obsidian\ vault. |
| `skills/principal-systems-architect/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | principal-systems-architect | Owns\ system\ architecture:\ components,\ interfaces,\ data\ flow. |
| `skills/product-experience-architect/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | product-experience-architect | Owns\ product/UX:\ journeys,\ jobs,\ experience\ quality. |
| `skills/productivity/airtable/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | airtable | Airtable\ REST\ API\ via\ curl.\ Records\ CRUD,\ filters,\ upserts. |
| `skills/productivity/google-workspace/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | google-workspace | Gmail,\ Calendar,\ Drive,\ Docs,\ Sheets\ via\ gws\ CLI\ or\ Python. |
| `skills/productivity/linear/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | linear | Linear:\ manage\ issues,\ projects,\ teams\ via\ GraphQL\ +\ curl. |
| `skills/productivity/maps/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | maps | Geocode,\ POIs,\ routes,\ timezones\ via\ OpenStreetMap/OSRM. |
| `skills/productivity/nano-pdf/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | nano-pdf | Edit\ PDF\ text/typos/titles\ via\ nano-pdf\ CLI\ (NL\ prompts). |
| `skills/productivity/notion/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | notion | Notion\ API\ +\ ntn\ CLI:\ pages,\ databases,\ markdown,\ Workers. |
| `skills/productivity/ocr-and-documents/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | ocr-and-documents | Extract\ text\ from\ PDFs/scans\ (pymupdf,\ marker-pdf). |
| `skills/productivity/powerpoint/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | powerpoint | Create,\ read,\ edit\ .pptx\ decks,\ slides,\ notes,\ templates. |
| `skills/productivity/teams-meeting-pipeline/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | teams-meeting-pipeline | Operate\ the\ Teams\ meeting\ summary\ pipeline\ via\ Hermes\ CLI\ —\ summarize\ meeting |
| `skills/red-teaming/godmode/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | godmode | Jailbreak\ LLMs:\ Parseltongue,\ GODMODE,\ ULTRAPLINIAN. |
| `skills/research-validator/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | research-validator | Gather\ evidence\ and\ validate\ claims\ before\ Hermes\ commits\ to\ a\ decision.\ Compan |
| `skills/research/arxiv/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | arxiv | Search\ arXiv\ papers\ by\ keyword,\ author,\ category,\ or\ ID. |
| `skills/research/blogwatcher/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | blogwatcher | Monitor\ blogs\ and\ RSS/Atom\ feeds\ via\ blogwatcher-cli\ tool. |
| `skills/research/llm-wiki/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | llm-wiki | Karpathy's\ LLM\ Wiki:\ build/query\ interlinked\ markdown\ KB. |
| `skills/research/polymarket/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | polymarket | Query\ Polymarket:\ markets,\ prices,\ orderbooks,\ history. |
| `skills/research/research-paper-writing/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | research-paper-writing | Write\ ML\ papers\ for\ NeurIPS/ICML/ICLR:\ design→submit. |
| `skills/self-improvement-loop/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | self-improvement-loop | Close\ every\ job\ with\ a\ learning\ pass:\ read\ artifacts\ +\ scorecard,\ propose\ upda |
| `skills/smart-home/openhue/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | openhue | Control\ Philips\ Hue\ lights,\ scenes,\ rooms\ via\ OpenHue\ CLI. |
| `skills/social-media/xurl/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | xurl | X/Twitter\ via\ xurl\ CLI:\ post,\ search,\ DM,\ media,\ v2\ API. |
| `skills/software-development/debugging-hermes-tui-commands/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | debugging-hermes-tui-commands | Debug\ Hermes\ TUI\ slash\ commands:\ Python,\ gateway,\ Ink\ UI. |
| `skills/software-development/hermes-agent-skill-authoring/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | hermes-agent-skill-authoring | Author\ in-repo\ SKILL.md:\ frontmatter,\ validator,\ structure. |
| `skills/software-development/node-inspect-debugger/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | node-inspect-debugger | Debug\ Node.js\ via\ --inspect\ +\ Chrome\ DevTools\ Protocol\ CLI. |
| `skills/software-development/plan/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | plan | Plan\ mode:\ write\ markdown\ plan\ to\ .hermes/plans/,\ no\ exec. |
| `skills/software-development/python-debugpy/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | python-debugpy | Debug\ Python:\ pdb\ REPL\ +\ debugpy\ remote\ (DAP). |
| `skills/software-development/requesting-code-review/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | requesting-code-review | Pre-commit\ review:\ security\ scan,\ quality\ gates,\ auto-fix. |
| `skills/software-development/spike/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | spike | Throwaway\ experiments\ to\ validate\ an\ idea\ before\ build. |
| `skills/software-development/subagent-driven-development/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | subagent-driven-development | Execute\ plans\ via\ delegate_task\ subagents\ (2-stage\ review). |
| `skills/software-development/systematic-debugging/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | systematic-debugging | 4-phase\ root\ cause\ debugging:\ understand\ bugs\ before\ fixing. |
| `skills/software-development/test-driven-development/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | test-driven-development | TDD:\ enforce\ RED-GREEN-REFACTOR,\ tests\ before\ code. |
| `skills/software-development/writing-plans/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | writing-plans | Write\ implementation\ plans:\ bite-sized\ tasks,\ paths,\ code. |
| `skills/yuanbao/SKILL.md` | hermes-agent | skills/ | SKILL | HIGH | yuanbao | Yuanbao\ (元宝)\ groups:\ @mention\ users,\ query\ info/members. |
| `optional-skills/autonomous-ai-agents/blackbox/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | blackbox | Delegate\ coding\ tasks\ to\ Blackbox\ AI\ CLI\ agent.\ Multi-model\ agent\ with\ built-in |
| `optional-skills/autonomous-ai-agents/honcho/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | honcho | Configure\ and\ use\ Honcho\ memory\ with\ Hermes\ --\ cross-session\ user\ modeling,\ mul |
| `optional-skills/blockchain/evm/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | evm | Read-only\ EVM\ client:\ wallets,\ tokens,\ gas\ across\ 8\ chains. |
| `optional-skills/blockchain/hyperliquid/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | hyperliquid | Hyperliquid\ market\ data,\ account\ history,\ trade\ review. |
| `optional-skills/blockchain/solana/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | solana | Query\ Solana\ blockchain\ data\ with\ USD\ pricing\ —\ wallet\ balances,\ token\ portfo |
| `optional-skills/communication/one-three-one-rule/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | one-three-one-rule | > |
| `optional-skills/creative/blender-mcp/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | blender-mcp | Control\ Blender\ directly\ from\ Hermes\ via\ socket\ connection\ to\ the\ blender-mcp\ a |
| `optional-skills/creative/concept-diagrams/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | concept-diagrams | Generate\ flat,\ minimal\ light/dark-aware\ SVG\ diagrams\ as\ standalone\ HTML\ files,\ u |
| `optional-skills/creative/hyperframes/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | hyperframes | Create\ HTML-based\ video\ compositions,\ animated\ title\ cards,\ social\ overlays,\ capt |
| `optional-skills/creative/kanban-video-orchestrator/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | kanban-video-orchestrator | Plan,\ set\ up,\ and\ monitor\ a\ multi-agent\ video\ production\ pipeline\ backed\ by\ He |
| `optional-skills/creative/meme-generation/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | meme-generation | Generate\ real\ meme\ images\ by\ picking\ a\ template\ and\ overlaying\ text\ with\ Pillo |
| `optional-skills/devops/cli/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | inference-sh-cli | Run\ 150+\ AI\ apps\ via\ inference.sh\ CLI\ (infsh)\ —\ image\ generation,\ video\ crea |
| `optional-skills/devops/docker-management/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | docker-management | Manage\ Docker\ containers,\ images,\ volumes,\ networks,\ and\ Compose\ stacks\ —\ life |
| `optional-skills/devops/pinggy-tunnel/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | pinggy-tunnel | Zero-install\ localhost\ tunnels\ over\ SSH\ via\ Pinggy. |
| `optional-skills/devops/watchers/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | watchers | Poll\ RSS,\ JSON\ APIs,\ and\ GitHub\ with\ watermark\ dedup. |
| `optional-skills/dogfood/adversarial-ux-test/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | adversarial-ux-test | Roleplay\ the\ most\ difficult,\ tech-resistant\ user\ for\ your\ product.\ Browse\ the\ a |
| `optional-skills/email/agentmail/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | agentmail | Give\ the\ agent\ its\ own\ dedicated\ email\ inbox\ via\ AgentMail.\ Send,\ receive,\ and |
| `optional-skills/finance/3-statement-model/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | 3-statement-model | Build\ fully-integrated\ 3-statement\ models\ (IS,\ BS,\ CF)\ in\ Excel\ with\ working\ ca |
| `optional-skills/finance/comps-analysis/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | comps-analysis | Build\ comparable\ company\ analysis\ in\ Excel\ —\ operating\ metrics,\ valuation\ mult |
| `optional-skills/finance/dcf-model/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | dcf-model | Build\ institutional-quality\ DCF\ valuation\ models\ in\ Excel\ —\ revenue\ projections |
| `optional-skills/finance/excel-author/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | excel-author | Build\ auditable\ Excel\ workbooks\ headless\ with\ openpyxl\ —\ blue/black/green\ cell\ |
| `optional-skills/finance/lbo-model/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | lbo-model | Build\ leveraged\ buyout\ models\ in\ Excel\ —\ sources\ &\ uses,\ debt\ schedule,\ cash |
| `optional-skills/finance/merger-model/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | merger-model | Build\ accretion/dilution\ (merger)\ models\ in\ Excel\ —\ pro-forma\ P&L,\ synergies,\  |
| `optional-skills/finance/pptx-author/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | pptx-author | Build\ PowerPoint\ decks\ headless\ with\ python-pptx.\ Pairs\ with\ excel-author\ for\ mo |
| `optional-skills/finance/stocks/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | stocks | Stock\ quotes,\ history,\ search,\ compare,\ crypto\ via\ Yahoo. |
| `optional-skills/health/fitness-nutrition/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | fitness-nutrition | > |
| `optional-skills/health/neuroskill-bci/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | neuroskill-bci | > |
| `optional-skills/mcp/fastmcp/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | fastmcp | Build,\ test,\ inspect,\ install,\ and\ deploy\ MCP\ servers\ with\ FastMCP\ in\ Python.\  |
| `optional-skills/mcp/mcporter/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | mcporter | Use\ the\ mcporter\ CLI\ to\ list,\ configure,\ auth,\ and\ call\ MCP\ servers/tools\ dire |
| `optional-skills/migration/openclaw-migration/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | openclaw-migration | Migrate\ a\ user's\ OpenClaw\ customization\ footprint\ into\ Hermes\ Agent.\ Imports\ Her |
| `optional-skills/mlops/accelerate/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | huggingface-accelerate | Simplest\ distributed\ training\ API.\ 4\ lines\ to\ add\ distributed\ support\ to\ any\ P |
| `optional-skills/mlops/chroma/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | chroma | Open-source\ embedding\ database\ for\ AI\ applications.\ Store\ embeddings\ and\ metadata |
| `optional-skills/mlops/clip/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | clip | OpenAI's\ model\ connecting\ vision\ and\ language.\ Enables\ zero-shot\ image\ classifica |
| `optional-skills/mlops/faiss/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | faiss | Facebook's\ library\ for\ efficient\ similarity\ search\ and\ clustering\ of\ dense\ vecto |
| `optional-skills/mlops/flash-attention/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | optimizing-attention-flash | Optimizes\ transformer\ attention\ with\ Flash\ Attention\ for\ 2-4x\ speedup\ and\ 10-20x |
| `optional-skills/mlops/guidance/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | guidance | Control\ LLM\ output\ with\ regex\ and\ grammars,\ guarantee\ valid\ JSON/XML/code\ genera |
| `optional-skills/mlops/huggingface-tokenizers/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | huggingface-tokenizers | Fast\ tokenizers\ optimized\ for\ research\ and\ production.\ Rust-based\ implementation\  |
| `optional-skills/mlops/inference/outlines/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | outlines | Outlines:\ structured\ JSON/regex/Pydantic\ LLM\ generation. |
| `optional-skills/mlops/instructor/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | instructor | Extract\ structured\ data\ from\ LLM\ responses\ with\ Pydantic\ validation,\ retry\ faile |
| `optional-skills/mlops/lambda-labs/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | lambda-labs-gpu-cloud | Reserved\ and\ on-demand\ GPU\ cloud\ instances\ for\ ML\ training\ and\ inference.\ Use\  |
| `optional-skills/mlops/llava/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | llava | Large\ Language\ and\ Vision\ Assistant.\ Enables\ visual\ instruction\ tuning\ and\ image |
| `optional-skills/mlops/modal/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | modal-serverless-gpu | Serverless\ GPU\ cloud\ platform\ for\ running\ ML\ workloads.\ Use\ when\ you\ need\ on-d |
| `optional-skills/mlops/nemo-curator/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | nemo-curator | GPU-accelerated\ data\ curation\ for\ LLM\ training.\ Supports\ text/image/video/audio.\ F |
| `optional-skills/mlops/peft/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | peft-fine-tuning | Parameter-efficient\ fine-tuning\ for\ LLMs\ using\ LoRA,\ QLoRA,\ and\ 25+\ methods.\ Use |
| `optional-skills/mlops/pinecone/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | pinecone | Managed\ vector\ database\ for\ production\ AI\ applications.\ Fully\ managed,\ auto-scali |
| `optional-skills/mlops/pytorch-fsdp/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | pytorch-fsdp | Expert\ guidance\ for\ Fully\ Sharded\ Data\ Parallel\ training\ with\ PyTorch\ FSDP\ -\ p |
| `optional-skills/mlops/pytorch-lightning/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | pytorch-lightning | High-level\ PyTorch\ framework\ with\ Trainer\ class,\ automatic\ distributed\ training\ ( |
| `optional-skills/mlops/qdrant/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | qdrant-vector-search | High-performance\ vector\ similarity\ search\ engine\ for\ RAG\ and\ semantic\ search.\ Us |
| `optional-skills/mlops/saelens/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | sparse-autoencoder-training | Provides\ guidance\ for\ training\ and\ analyzing\ Sparse\ Autoencoders\ (SAEs)\ using\ SA |
| `optional-skills/mlops/simpo/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | simpo-training | Simple\ Preference\ Optimization\ for\ LLM\ alignment.\ Reference-free\ alternative\ to\ D |
| `optional-skills/mlops/slime/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | slime-rl-training | Provides\ guidance\ for\ LLM\ post-training\ with\ RL\ using\ slime,\ a\ Megatron+SGLang\  |
| `optional-skills/mlops/stable-diffusion/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | stable-diffusion-image-generation | State-of-the-art\ text-to-image\ generation\ with\ Stable\ Diffusion\ models\ via\ Hugging |
| `optional-skills/mlops/tensorrt-llm/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | tensorrt-llm | Optimizes\ LLM\ inference\ with\ NVIDIA\ TensorRT\ for\ maximum\ throughput\ and\ lowest\  |
| `optional-skills/mlops/torchtitan/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | distributed-llm-pretraining-torchtitan | Provides\ PyTorch-native\ distributed\ LLM\ pretraining\ using\ torchtitan\ with\ 4D\ para |
| `optional-skills/mlops/training/axolotl/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | axolotl | Axolotl:\ YAML\ LLM\ fine-tuning\ (LoRA,\ DPO,\ GRPO). |
| `optional-skills/mlops/training/trl-fine-tuning/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | fine-tuning-with-trl | TRL:\ SFT,\ DPO,\ PPO,\ GRPO,\ reward\ modeling\ for\ LLM\ RLHF. |
| `optional-skills/mlops/training/unsloth/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | unsloth | Unsloth:\ 2-5x\ faster\ LoRA/QLoRA\ fine-tuning,\ less\ VRAM. |
| `optional-skills/mlops/whisper/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | whisper | OpenAI's\ general-purpose\ speech\ recognition\ model.\ Supports\ 99\ languages,\ transcri |
| `optional-skills/productivity/canvas/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | canvas | Canvas\ LMS\ integration\ —\ fetch\ enrolled\ courses\ and\ assignments\ using\ API\ tok |
| `optional-skills/productivity/here-now/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | here.now | Publish\ static\ sites\ to\ {slug}.here.now\ and\ store\ private\ files\ in\ cloud\ Drives |
| `optional-skills/productivity/memento-flashcards/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | memento-flashcards | >- |
| `optional-skills/productivity/shop-app/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | shop-app | Shop.app:\ product\ search,\ order\ tracking,\ returns,\ reorder. |
| `optional-skills/productivity/shopify/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | shopify | Shopify\ Admin\ &\ Storefront\ GraphQL\ APIs\ via\ curl.\ Products,\ orders,\ customers,\  |
| `optional-skills/productivity/siyuan/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | siyuan | SiYuan\ Note\ API\ for\ searching,\ reading,\ creating,\ and\ managing\ blocks\ and\ docum |
| `optional-skills/productivity/telephony/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | telephony | Give\ Hermes\ phone\ capabilities\ without\ core\ tool\ changes.\ Provision\ and\ persist\ |
| `optional-skills/research/bioinformatics/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | bioinformatics | Gateway\ to\ 400+\ bioinformatics\ skills\ from\ bioSkills\ and\ ClawBio.\ Covers\ genomic |
| `optional-skills/research/darwinian-evolver/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | darwinian-evolver | Evolve\ prompts/regex/SQL/code\ with\ Imbue's\ evolution\ loop. |
| `optional-skills/research/domain-intel/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | domain-intel | Passive\ domain\ reconnaissance\ using\ Python\ stdlib.\ Subdomain\ discovery,\ SSL\ certi |
| `optional-skills/research/drug-discovery/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | drug-discovery | > |
| `optional-skills/research/duckduckgo-search/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | duckduckgo-search | Free\ web\ search\ via\ DuckDuckGo\ —\ text,\ news,\ images,\ videos.\ No\ API\ key\ nee |
| `optional-skills/research/gitnexus-explorer/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | gitnexus-explorer | Index\ a\ codebase\ with\ GitNexus\ and\ serve\ an\ interactive\ knowledge\ graph\ via\ we |
| `optional-skills/research/osint-investigation/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | osint-investigation | Public-records\ OSINT\ investigation\ framework\ —\ SEC\ EDGAR\ filings,\ USAspending\ c |
| `optional-skills/research/parallel-cli/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | parallel-cli | Optional\ vendor\ skill\ for\ Parallel\ CLI\ —\ agent-native\ web\ search,\ extraction,\ |
| `optional-skills/research/qmd/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | qmd | Search\ personal\ knowledge\ bases,\ notes,\ docs,\ and\ meeting\ transcripts\ locally\ us |
| `optional-skills/research/scrapling/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | scrapling | Web\ scraping\ with\ Scrapling\ -\ HTTP\ fetching,\ stealth\ browser\ automation,\ Cloudfl |
| `optional-skills/research/searxng-search/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | searxng-search | Free\ meta-search\ via\ SearXNG\ —\ aggregates\ results\ from\ 70+\ search\ engines.\ Se |
| `optional-skills/security/1password/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | 1password | Set\ up\ and\ use\ 1Password\ CLI\ (op).\ Use\ when\ installing\ the\ CLI,\ enabling\ desk |
| `optional-skills/security/oss-forensics/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | oss-forensics | / |
| `optional-skills/security/sherlock/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | sherlock | OSINT\ username\ search\ across\ 400+\ social\ networks.\ Hunt\ down\ social\ media\ accou |
| `optional-skills/software-development/rest-graphql-debug/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | rest-graphql-debug | Debug\ REST/GraphQL\ APIs:\ status\ codes,\ auth,\ schemas,\ repro. |
| `optional-skills/web-development/page-agent/SKILL.md` | hermes-agent | optional-skills/ | SKILL | HIGH | page-agent | Embed\ alibaba/page-agent\ into\ your\ own\ web\ application\ —\ a\ pure-JavaScript\ in- |
| `docs/orchestration/NEXT_PHASE_IMPLEMENTATION_PROMPT.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Next-Phase\ Implementation\ Prompt |
| `docs/orchestration/PHASES.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ —\ phase\ log |
| `docs/orchestration/README.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ Orchestration |
| `docs/orchestration/android-termux-demo.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Demo\ —\ Android\ cockpit\ +\ Termux\ runtime |
| `docs/orchestration/decision-ledger.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Decision\ Ledger |
| `docs/orchestration/decision-quality-system.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ Decision\ Quality\ System |
| `docs/orchestration/faq.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ FAQ |
| `docs/orchestration/final-10-10-readiness-report.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ —\ 10/10\ final\ readiness\ report |
| `docs/orchestration/final-hermes-orchestration-integration-report.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ Orchestration\ —\ Final\ Integration\ Report |
| `docs/orchestration/getting-started.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Getting\ started\ with\ Hermes\ Orchestration |
| `docs/orchestration/github-publisher-runtime.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ GitHub\ publisher\ runtime |
| `docs/orchestration/hermes-agent-skill-map.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ Agent\ Skill\ Map\ —\ AoS\ Council |
| `docs/orchestration/hermes-orchestration-pipeline.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ pipeline |
| `docs/orchestration/job-controller-roadmap.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Job\ Controller\ Roadmap\ (Phase\ 7) |
| `docs/orchestration/known-limitations.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ —\ known\ limitations |
| `docs/orchestration/local-api-backend.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Local\ Orchestrator\ API\ Backend |
| `docs/orchestration/local-validation-gates.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Local\ Validation\ Gates |
| `docs/orchestration/next-roadmap.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ —\ next\ roadmap |
| `docs/orchestration/orchestrator-command-reference.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Orchestrator\ slash\ command\ reference |
| `docs/orchestration/orchestrator-command-roadmap.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Orchestrator\ Command\ Roadmap\ (Phase\ 7) |
| `docs/orchestration/parallel-workers-and-worktrees.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Parallel\ workers\ and\ git\ worktrees |
| `docs/orchestration/phase-0-evidence-audit.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Phase\ 0\ —\ Evidence\ Audit\ for\ Hermes\ Prompt-First\ Orchestration |
| `docs/orchestration/phase-9-validation-report.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Phase\ 9\ —\ Validation\ and\ Quality\ Gate\ Report |
| `docs/orchestration/private-local-mode.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Private\ /\ local-only\ mode |
| `docs/orchestration/prompt-to-pr-demo.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Demo\ —\ Prompt\ to\ PR |
| `docs/orchestration/release-checklist.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Hermes\ orchestration\ —\ release\ checklist |
| `docs/orchestration/scoring-and-merge-engine.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Scoring\ and\ merge\ engine\ (Phase\ 13) |
| `docs/orchestration/self-improvement-loop.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Self-Improvement\ Loop\ —\ Orchestration |
| `docs/orchestration/troubleshooting.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Troubleshooting |
| `docs/orchestration/worker-adapter-interface.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Worker\ Adapter\ Interface\ (Phase\ 7) |
| `docs/orchestration/worker-adapters.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Worker\ adapters |
| `docs/orchestration/workers/aider-worker.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Aider\ worker |
| `docs/orchestration/workers/claude-code-worker.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Claude\ Code\ worker |
| `docs/orchestration/workers/codex-worker.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Codex\ Worker |
| `docs/orchestration/workers/goose-worker.md` | hermes-agent | docs/orchestration/ | GOVERNANCE | HIGH | — | #\ Goose\ worker |
| `enterprise/__init__.py` | hermes-agent | enterprise/ | WORKER-PROFILE | MEDIUM | — | """Enterprise\ Council\ —\ autonomous\ multi-agent\ system\ for\ Hermes. |
| `enterprise/adapters/__init__.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """Domain\ adapter\ shims\ for\ the\ enterprise\ council. |
| `enterprise/adapters/cs.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """CustomerService\ domain\ adapter\ —\ mock\ Zendesk\ /\ Intercom\ /\ KB.""" |
| `enterprise/adapters/finance.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """Finance\ domain\ adapter\ —\ mock\ Stripe\ /\ NetSuite\ /\ QuickBooks. |
| `enterprise/adapters/hr.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """HR\ domain\ adapter\ —\ mock\ Workday\ /\ Greenhouse\ /\ BambooHR.""" |
| `enterprise/adapters/ops.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """Operations\ domain\ adapter\ —\ mock\ SAP\ /\ SlackOps\ /\ ComplianceDB.""" |
| `enterprise/adapters/sales.py` | hermes-agent | enterprise/adapters/ | WORKER-PROFILE | HIGH | — | """Sales\ domain\ adapter\ —\ mock\ Salesforce\ /\ HubSpot\ /\ DocuSign.""" |
| `enterprise/audit.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Structured\ audit\ trail\ for\ enterprise\ council\ runs. |
| `enterprise/council.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Orchestrator\ runtime\ for\ the\ enterprise\ council. |
| `enterprise/judge.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Validator\ /\ Judge\ for\ enterprise\ council\ outputs. |
| `enterprise/monitor.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Post-run\ review\ that\ proposes\ prompt/policy\ improvements. |
| `enterprise/policy.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Risk\ classification\ +\ human-in-the-loop\ gating\ for\ the\ enterprise\ council. |
| `enterprise/secrets.py` | hermes-agent | enterprise/ | ROUTING-CONFIG | HIGH | — | """Secret\ retrieval\ facade\ for\ enterprise\ council\ agents. |
| `recovered-agent-sources/from-hazmat-command/agents/assurance-security-compliance-office.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | assurance-security-compliance-office | Independent\ reviewer\ for\ security,\ compliance,\ reliability,\ and\ regulator-facing\ c |
| `recovered-agent-sources/from-hazmat-command/agents/chief-orchestrator.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | chief-orchestrator | Top-level\ coordinator\ for\ HazMat\ Command.\ Use\ proactively\ whenever\ a\ session\ spa |
| `recovered-agent-sources/from-hazmat-command/agents/codex-implementation-fabric.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | codex-implementation-fabric | Thin\ wrapper\ for\ the\ Codex\ bounded-implementation\ fabric.\ Authority\ cap\ L3,\ trus |
| `recovered-agent-sources/from-hazmat-command/agents/commercial-strategy-growth-office.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | commercial-strategy-growth-office | Use\ only\ for\ pricing,\ packaging,\ positioning,\ claims,\ GTM\ messaging,\ competitor\  |
| `recovered-agent-sources/from-hazmat-command/agents/engineering-architecture-factory.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | engineering-architecture-factory | Primary\ implementation\ agent\ for\ HazMat\ Command\ product\ code.\ Use\ for\ code\ chan |
| `recovered-agent-sources/from-hazmat-command/agents/knowledge-operations-self-improvement.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | knowledge-operations-self-improvement | Use\ to\ maintain\ durable\ artifacts\ —\ the\ index,\ the\ doc-freshness\ ledger,\ the\ |
| `recovered-agent-sources/from-hazmat-command/agents/legal-policy-contracts-trust-office.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | legal-policy-contracts-trust-office | Use\ only\ for\ legal,\ policy,\ trust,\ and\ contractual\ artifacts\ (ToS,\ Privacy,\ NDA |
| `recovered-agent-sources/from-hazmat-command/agents/pilot-readiness-judge.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | pilot-readiness-judge | Use\ before\ a\ real\ customer\ demo\ or\ pilot\ session.\ Produces\ a\ binary\ go\ /\ no- |
| `recovered-agent-sources/from-hazmat-command/agents/principal-code-reviewer.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | principal-code-reviewer | Hard-nosed\ independent\ code\ reviewer.\ Use\ on\ every\ code-bearing\ PR\ before\ owner\ |
| `recovered-agent-sources/from-hazmat-command/agents/product-pilot-experience-studio.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | product-pilot-experience-studio | Use\ when\ a\ request\ is\ about\ user\ experience,\ founder\ demo,\ pilot/customer\ walkt |
| `recovered-agent-sources/from-hazmat-command/agents/research-evidence-bureau.md` | hazmat-command (snapshot) | .claude/agents/ | AGENT-SPEC | HIGH | research-evidence-bureau | Read-only\ research\ and\ evidence\ agent.\ Use\ whenever\ a\ task\ requires\ verifying\ a |
| `recovered-agent-sources/from-hazmat-command/skills/claims-substantiation-review/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | claims-substantiation-review | Use\ whenever\ externally-visible\ copy\ is\ being\ added\ or\ edited\ (marketing,\ RFP,\  |
| `recovered-agent-sources/from-hazmat-command/skills/codex-return-envelope-verify/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | codex-return-envelope-verify | Use\ after\ a\ Codex\ Task\ Packet\ execution\ returns.\ Parses\ the\ return\ envelope,\ a |
| `recovered-agent-sources/from-hazmat-command/skills/codex-task-packet-dispatch/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | codex-task-packet-dispatch | Manual-only.\ Owner-triggered.\ Drafts\ and\ dispatches\ a\ Codex\ Task\ Packet\ per\ docs |
| `recovered-agent-sources/from-hazmat-command/skills/commercial-grade-implementation/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | commercial-grade-implementation | The\ default\ implementation\ workflow\ for\ any\ code-bearing\ task\ in\ this\ repo.\ Enf |
| `recovered-agent-sources/from-hazmat-command/skills/complex-bug-fix/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | complex-bug-fix | Use\ when\ a\ defect\ spans\ more\ than\ one\ file,\ more\ than\ one\ role,\ or\ appears\  |
| `recovered-agent-sources/from-hazmat-command/skills/compliance-rule-change/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | compliance-rule-change | Use\ when\ changing\ 49\ CFR\ /\ TDG\ rule-engine\ logic,\ ERG\ data,\ placard\ thresholds |
| `recovered-agent-sources/from-hazmat-command/skills/enterprise-procurement-readiness/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | enterprise-procurement-readiness | Use\ when\ preparing\ for\ an\ enterprise\ procurement\ /\ RFP\ /\ security\ review.\ Walk |
| `recovered-agent-sources/from-hazmat-command/skills/evidence-bundle-build/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | evidence-bundle-build | Use\ immediately\ after\ mission-brief-build.\ Assembles\ repo\ facts,\ external\ citation |
| `recovered-agent-sources/from-hazmat-command/skills/execution-blueprint-compile/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | execution-blueprint-compile | Use\ after\ owner\ approves\ the\ revised\ synthesized\ master\ plan.\ Converts\ the\ appr |
| `recovered-agent-sources/from-hazmat-command/skills/full-autonomous-sprint-router/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | full-autonomous-sprint-router | Use\ at\ the\ start\ of\ a\ multi-domain\ or\ ambiguous\ request\ to\ classify\ the\ work, |
| `recovered-agent-sources/from-hazmat-command/skills/master-plan-synthesis/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | master-plan-synthesis | Use\ after\ plan-comparison-scorecard.\ Produces\ 04-synthesized-plan.md\ by\ curating\ su |
| `recovered-agent-sources/from-hazmat-command/skills/mission-brief-build/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | mission-brief-build | Use\ at\ the\ start\ of\ any\ Council\ Mode\ run\ or\ any\ substantive\ sprint\ that\ land |
| `recovered-agent-sources/from-hazmat-command/skills/multi-plan-council-run/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | multi-plan-council-run | Manual-only.\ Owner-triggered.\ Dispatches\ N\ parallel\ plan-generation\ passes\ for\ Cou |
| `recovered-agent-sources/from-hazmat-command/skills/pilot-demo-readiness/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | pilot-demo-readiness | Use\ to\ prepare\ for\ and\ judge\ readiness\ of\ a\ real\ customer\ demo\ or\ pilot\ sess |
| `recovered-agent-sources/from-hazmat-command/skills/plan-comparison-scorecard/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | plan-comparison-scorecard | Use\ after\ multi-plan-council-run\ produces\ N\ materially-distinct\ plans.\ Scores\ each |
| `recovered-agent-sources/from-hazmat-command/skills/post-merge-verification/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | post-merge-verification | Use\ immediately\ after\ an\ owner-approved\ merge\ to\ main.\ Confirms\ the\ merge\ commi |
| `recovered-agent-sources/from-hazmat-command/skills/pr-readiness-and-owner-handoff/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | pr-readiness-and-owner-handoff | Use\ at\ the\ end\ of\ every\ substantive\ run\ to\ assemble\ the\ final\ PR\ body\ and\ t |
| `recovered-agent-sources/from-hazmat-command/skills/red-team-plan-review/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | red-team-plan-review | Use\ after\ master-plan-synthesis.\ Independently\ attacks\ the\ synthesized\ master\ plan |
| `recovered-agent-sources/from-hazmat-command/skills/release-go-no-go-review/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | release-go-no-go-review | Use\ before\ tagging\ or\ shipping\ a\ release.\ Verifies\ G0–G4\ release\ governance\ p |
| `recovered-agent-sources/from-hazmat-command/skills/research-dossier-build/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | research-dossier-build | Use\ when\ an\ RC3\ change,\ new\ commercial\ claim,\ new\ legal\ document,\ pricing\ deci |
| `recovered-agent-sources/from-hazmat-command/skills/security-or-authz-change/SKILL.md` | hazmat-command (snapshot) | .claude/skills/ | SKILL | HIGH | security-or-authz-change | Use\ when\ changing\ authz,\ RBAC,\ RLS,\ audit\ ledger,\ OCR\ provenance,\ secret\ handli |
| `recovered-agent-sources/from-hazmat-command/rules/00-commercial-delivery-standard.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | #\ 00\ —\ Commercial\ Delivery\ Standard\ (unconditional) |
| `recovered-agent-sources/from-hazmat-command/rules/android-mobile-and-release-surface.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/rules/docs-claims-legal-and-commercial.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/rules/engineering-production-quality.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/rules/hazmat-compliance-and-regulated-output.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/rules/security-authz-and-trust-boundaries.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/rules/testing-and-verification.md` | hazmat-command (snapshot) | .claude/rules/ | RULE | HIGH | — | --- |
| `recovered-agent-sources/from-hazmat-command/docs/agents/00-agent-organization-overview.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 00\ —\ Agent\ Organization\ Overview |
| `recovered-agent-sources/from-hazmat-command/docs/agents/01-executive-command-and-orchestration.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 01\ —\ Executive\ Command\ &\ Orchestration |
| `recovered-agent-sources/from-hazmat-command/docs/agents/02-research-and-evidence-bureau.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 02\ —\ Research\ &\ Evidence\ Bureau |
| `recovered-agent-sources/from-hazmat-command/docs/agents/03-product-and-pilot-experience-studio.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 03\ —\ Product\ &\ Pilot\ Experience\ Studio |
| `recovered-agent-sources/from-hazmat-command/docs/agents/04-engineering-and-architecture-factory.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 04\ —\ Engineering\ &\ Architecture\ Factory |
| `recovered-agent-sources/from-hazmat-command/docs/agents/05-assurance-security-reliability-compliance-office.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 05\ —\ Assurance,\ Security,\ Reliability\ &\ Compliance\ Office |
| `recovered-agent-sources/from-hazmat-command/docs/agents/06-commercial-strategy-pricing-growth-office.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 06\ —\ Commercial\ Strategy,\ Pricing\ &\ Growth\ Office |
| `recovered-agent-sources/from-hazmat-command/docs/agents/07-legal-policy-contracts-trust-office.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 07\ —\ Legal,\ Policy,\ Contracts\ &\ Trust\ Office |
| `recovered-agent-sources/from-hazmat-command/docs/agents/08-pilot-operations-and-customer-intelligence.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 08\ —\ Pilot\ Operations\ &\ Customer\ Intelligence |
| `recovered-agent-sources/from-hazmat-command/docs/agents/09-knowledge-operations-and-self-improvement.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ 09\ —\ Knowledge\ Operations\ &\ Self-Improvement |
| `recovered-agent-sources/from-hazmat-command/docs/agents/subagent-task-contract.md` | hazmat-command (snapshot) | docs/agents/ | AGENT-SPEC | HIGH | — | #\ Subagent\ Task\ Contract |
| `recovered-agent-sources/from-hazmat-command/docs/governance/00-autonomous-enterprise-organization-overview.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 00\ —\ HazMat\ Command\ Autonomous\ Enterprise\ Organization\ Overview |
| `recovered-agent-sources/from-hazmat-command/docs/governance/01-source-of-truth-hierarchy.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 01\ —\ Source-of-Truth\ Hierarchy |
| `recovered-agent-sources/from-hazmat-command/docs/governance/02-agent-authority-matrix.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 02\ —\ Agent\ Authority\ Matrix |
| `recovered-agent-sources/from-hazmat-command/docs/governance/03-change-risk-matrix.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 03\ —\ Change\ Risk\ Matrix |
| `recovered-agent-sources/from-hazmat-command/docs/governance/04-workflow-router.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 04\ —\ Workflow\ Router |
| `recovered-agent-sources/from-hazmat-command/docs/governance/05-research-dossier-standard.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 05\ —\ Research\ Dossier\ Standard |
| `recovered-agent-sources/from-hazmat-command/docs/governance/06-maker-checker-independent-review.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 06\ —\ Maker-Checker\ Independent\ Review |
| `recovered-agent-sources/from-hazmat-command/docs/governance/07-tool-trust-zones-and-agent-permissions.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 07\ —\ Tool\ Trust\ Zones\ and\ Agent\ Permissions |
| `recovered-agent-sources/from-hazmat-command/docs/governance/08-artifact-registry-and-memory-discipline.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 08\ —\ Artifact\ Registry\ and\ Memory\ Discipline |
| `recovered-agent-sources/from-hazmat-command/docs/governance/09-release-freeze-and-safety-budget-policy.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 09\ —\ Release\ Freeze\ and\ Safety\ Budget\ Policy |
| `recovered-agent-sources/from-hazmat-command/docs/governance/10-feature-flag-and-beta-gate-registry.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 10\ —\ Feature\ Flag\ and\ Beta\ Gate\ Registry |
| `recovered-agent-sources/from-hazmat-command/docs/governance/11-commercial-claims-substantiation-policy.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 11\ —\ Commercial\ Claims\ Substantiation\ Policy |
| `recovered-agent-sources/from-hazmat-command/docs/governance/12-legal-document-generation-policy.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 12\ —\ Legal\ Document\ Generation\ Policy |
| `recovered-agent-sources/from-hazmat-command/docs/governance/13-agent-evaluation-and-scoreboard.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 13\ —\ Agent\ Evaluation\ and\ Scoreboard |
| `recovered-agent-sources/from-hazmat-command/docs/governance/14-supply-chain-and-agent-security.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 14\ —\ Supply\ Chain\ and\ Agent\ Security |
| `recovered-agent-sources/from-hazmat-command/docs/governance/15-doc-freshness-and-contradiction-control.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 15\ —\ Doc\ Freshness\ and\ Contradiction\ Control |
| `recovered-agent-sources/from-hazmat-command/docs/governance/16-deliberative-planning-and-council-mode.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 16\ —\ Deliberative\ Planning\ and\ Council\ Mode |
| `recovered-agent-sources/from-hazmat-command/docs/governance/17-codex-bounded-implementation-fabric.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ 17\ —\ Codex\ Bounded\ Implementation\ Fabric |
| `recovered-agent-sources/from-hazmat-command/docs/governance/agent-performance-scoreboard-schema.md` | hazmat-command (snapshot) | docs/governance/ | GOVERNANCE | HIGH | — | #\ Agent\ Performance\ Scoreboard\ Schema |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/00-workflow-overview.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ 00\ —\ Workflow\ Overview |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/codex-implementation-fabric.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Codex\ Implementation\ Fabric |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/complex-bug-fix.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Complex\ Bug\ Fix |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/compliance-rule-change.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Compliance\ Rule\ Change |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/deliberative-council-planning.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Deliberative\ Council\ Planning |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/enterprise-procurement-readiness.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Enterprise\ Procurement\ Readiness |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/legal-document-generation.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Legal\ Document\ Generation |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/marketing-gtm.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Marketing\ /\ GTM |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/new-product-or-major-feature.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ New\ Product\ or\ Major\ Feature |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/pilot-demo-readiness.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Pilot\ /\ Demo\ Readiness |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/pricing-and-packaging.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Pricing\ and\ Packaging |
| `recovered-agent-sources/from-hazmat-command/docs/workflows/security-or-authz-change.md` | hazmat-command (snapshot) | docs/workflows/ | WORKFLOW | HIGH | — | #\ Workflow\ —\ Security\ or\ Authz\ Change |
| `recovered-agent-sources/from-hazmat-command/docs/skills/00-skill-library-overview.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ 00\ —\ Skill\ Library\ Overview |
| `recovered-agent-sources/from-hazmat-command/docs/skills/49cfr-rule-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ 49cfr-rule-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/agent-run-retrospective.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ agent-run-retrospective |
| `recovered-agent-sources/from-hazmat-command/docs/skills/app-store-policy-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ app-store-policy-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/artifact-index-update.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ artifact-index-update |
| `recovered-agent-sources/from-hazmat-command/docs/skills/b2b-saas-pricing-study.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ b2b-saas-pricing-study |
| `recovered-agent-sources/from-hazmat-command/docs/skills/carrier-roi-model.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ carrier-roi-model |
| `recovered-agent-sources/from-hazmat-command/docs/skills/claims-substantiation-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ claims-substantiation-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/competitor-battlecard.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ competitor-battlecard |
| `recovered-agent-sources/from-hazmat-command/docs/skills/competitor-benchmark.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ competitor-benchmark |
| `recovered-agent-sources/from-hazmat-command/docs/skills/compliance-evidence-matrix-build.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ compliance-evidence-matrix-build |
| `recovered-agent-sources/from-hazmat-command/docs/skills/customer-pain-mining.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ customer-pain-mining |
| `recovered-agent-sources/from-hazmat-command/docs/skills/doc-freshness-reconcile.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ doc-freshness-reconcile |
| `recovered-agent-sources/from-hazmat-command/docs/skills/document-renderer-regression-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ document-renderer-regression-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/dpa-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ dpa-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/erg-source-validation.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ erg-source-validation |
| `recovered-agent-sources/from-hazmat-command/docs/skills/hazmat-market-positioning.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ hazmat-market-positioning |
| `recovered-agent-sources/from-hazmat-command/docs/skills/mobile-capacitor-release-check.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ mobile-capacitor-release-check |
| `recovered-agent-sources/from-hazmat-command/docs/skills/msa-sow-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ msa-sow-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/nda-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ nda-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/negative-test-suite-generation.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ negative-test-suite-generation |
| `recovered-agent-sources/from-hazmat-command/docs/skills/ocr-confidence-provenance-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ ocr-confidence-provenance-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/oss-license-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ oss-license-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/packaging-entitlements-analysis.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ packaging-entitlements-analysis |
| `recovered-agent-sources/from-hazmat-command/docs/skills/pilot-agreement-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ pilot-agreement-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/pilot-readiness-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ pilot-readiness-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/pilot-to-contract-conversion-plan.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ pilot-to-contract-conversion-plan |
| `recovered-agent-sources/from-hazmat-command/docs/skills/placard-threshold-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ placard-threshold-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/privacy-policy-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ privacy-policy-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/prompt-upgrade-synthesis.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ prompt-upgrade-synthesis |
| `recovered-agent-sources/from-hazmat-command/docs/skills/rbac-tenant-isolation-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ rbac-tenant-isolation-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/release-go-no-go-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ release-go-no-go-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/research-dossier-build.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ research-dossier-build |
| `recovered-agent-sources/from-hazmat-command/docs/skills/shipping-paper-compliance-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ shipping-paper-compliance-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/sor-cutover-risk-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ sor-cutover-risk-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/source-contradiction-analysis.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ source-contradiction-analysis |
| `recovered-agent-sources/from-hazmat-command/docs/skills/stub-inventory-audit.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ stub-inventory-audit |
| `recovered-agent-sources/from-hazmat-command/docs/skills/tdg-crossborder-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ tdg-crossborder-review |
| `recovered-agent-sources/from-hazmat-command/docs/skills/terms-of-service-draft.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ terms-of-service-draft |
| `recovered-agent-sources/from-hazmat-command/docs/skills/threat-model-build.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ threat-model-build |
| `recovered-agent-sources/from-hazmat-command/docs/skills/webhook-idempotency-review.md` | hazmat-command (snapshot) | docs/skills/ | SKILL | HIGH | — | #\ Skill\ —\ webhook-idempotency-review |
| `recovered-agent-sources/from-hazmat-command/docs/templates/agent-run-retrospective-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Agent\ Run\ Retrospective\ —\ <run\ slug> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/architecture-decision-record-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ ADR-<NNNN>\ —\ <decision\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/claims-substantiation-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Claims\ Substantiation\ Memo\ —\ <surface> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/codex-task-package-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Codex\ Task\ Packet\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/compliance-evidence-matrix-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Compliance\ Evidence\ Matrix\ —\ <scope> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/decision-memo-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Decision\ Memo\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/evidence-bundle-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Evidence\ Bundle\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/execution-blueprint-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Execution\ Blueprint\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/gtm-brief-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ GTM\ Brief\ —\ <campaign\ /\ launch\ /\ repositioning> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/legal-document-intake-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Legal\ Document\ Intake\ —\ <doc\ type\ /\ counterparty> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/mission-brief-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Mission\ Brief\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/multi-plan-set-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Multi-Plan\ Set\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/pilot-readiness-report-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Pilot\ Readiness\ Report\ —\ <pilot\ /\ demo\ name> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/plan-comparison-matrix-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Plan\ Comparison\ Matrix\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/planbench-evaluation-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ PlanBench\ Evaluation\ —\ <challenge\ name> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/prd-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ PRD\ —\ <feature\ name> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/pricing-study-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Pricing\ Study\ —\ <topic\ /\ change> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/red-team-plan-review-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Red-Team\ Plan\ Review\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/research-dossier-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Research\ Dossier\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/synthesized-master-plan-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Synthesized\ Master\ Plan\ —\ <short\ title> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/threat-model-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Threat\ Model\ Entry\ —\ <surface\ name> |
| `recovered-agent-sources/from-hazmat-command/docs/templates/workflow-router-intake-template.md` | hazmat-command (snapshot) | docs/templates/ | TEMPLATE | HIGH | — | #\ Workflow\ Router\ Intake\ —\ <run\ slug> |
| `recovered-agent-sources/from-hermes-agent/aos-council-director/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | aos-council-director | Director:\ decomposes\ goal,\ dispatches\ AoS\ council,\ decides. |
| `recovered-agent-sources/from-hermes-agent/aos-full-agent-team/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | aos-full-agent-team | Full\ AoS\ council:\ spin\ up\ all\ 16\ specialists\ end-to-end. |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/DESCRIPTION.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | — | Skills\ for\ spawning\ and\ orchestrating\ autonomous\ AI\ coding\ agents\ and\ multi-agen |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/claude-code/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | claude-code | Delegate\ coding\ to\ Claude\ Code\ CLI\ (features,\ PRs). |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/codex/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | codex | Delegate\ coding\ to\ OpenAI\ Codex\ CLI\ (features,\ PRs). |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/hermes-agent/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | hermes-agent | Configure,\ extend,\ or\ contribute\ to\ Hermes\ Agent. |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/kanban-codex-lane/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | kanban-codex-lane | Use\ when\ a\ Hermes\ Kanban\ worker\ wants\ to\ run\ Codex\ CLI\ as\ an\ isolated\ implem |
| `recovered-agent-sources/from-hermes-agent/autonomous-ai-agents/opencode/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | opencode | Delegate\ coding\ to\ OpenCode\ CLI\ (features,\ PR\ review). |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/DESCRIPTION.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | — | Autonomous\ multi-agent\ enterprise\ system\ —\ Orchestrator\ +\ Finance/HR/CustomerServ |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/customer-service/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-customer-service | CS\ leaf:\ ticket\ classification,\ knowledge\ base\ retrieval,\ escalation,\ mass\ commun |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/finance/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-finance | Finance\ leaf:\ invoicing,\ budgeting,\ reporting\ against\ Stripe/NetSuite/QuickBooks. |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/hr/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-hr | HR\ leaf:\ recruitment\ screening,\ policy\ lookup,\ offer\ +\ termination\ workflows. |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/judge/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-judge | Validator\ /\ Judge:\ schema\ +\ policy\ +\ parallel-pass\ cross-checks\ on\ every\ leaf\  |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/monitor/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-monitor | Post-run\ reviewer:\ scans\ the\ audit\ trail,\ proposes\ improvements,\ hands\ them\ to\  |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/operations/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-operations | Operations\ leaf:\ logistics\ planning\ +\ execution,\ compliance\ checks\ +\ filings,\ in |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/orchestrator/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-orchestrator | Decompose\ a\ one-tap\ enterprise\ goal\ into\ autonomous\ tasks\ across\ domain\ agents. |
| `recovered-agent-sources/from-hermes-agent/enterprise-council/sales/SKILL.md` | hermes-agent (snapshot) | skills/ | SKILL | HIGH | enterprise-sales | Sales\ leaf:\ lead\ tracking,\ proposal\ drafting\ +\ sending,\ contract\ execution,\ disc |
| `recovered-agent-sources/from-hazmat-command/HAZMAT-AGENTS.md` | hazmat-command (snapshot) | constitutional/ | GOVERNANCE | HIGH | — | #\ AGENTS.md\ —\ HazMat\ Command\ v2 |
| `recovered-agent-sources/from-hazmat-command/HAZMAT-CLAUDE.md` | hazmat-command (snapshot) | constitutional/ | GOVERNANCE | HIGH | — | #\ CLAUDE.md\ —\ Claude\ Code\ bootstrap\ for\ HazMat\ Command |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/06-execution-blueprint.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Execution\ Blueprint\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/08-implementation-summary.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Implementation\ Summary\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/02-risk-classification.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Risk\ Classification\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/12-release-handoff.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Release\ Handoff\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/04-synthesized-plan.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Synthesized\ Master\ Plan\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/07-codex-task-package.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Codex\ Task\ Packet\ —\ wave-2-smoke-noop |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/01-evidence-bundle.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Evidence\ Bundle\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/11-security-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Security\ Review\ (RC3)\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/13-retrospective.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Retrospective\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/09-review-report.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Review\ Report\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/00-mission-brief.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Mission\ Brief\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/10-test-results.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Test\ Results\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/03-options-or-council-plans.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Options\ /\ Council\ Plans\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-2-dispatch-wiring/05-red-team-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Red-Team\ Review\ —\ Codex\ Wave\ 2\ Dispatch\ Wiring |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/06-execution-blueprint.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Execution\ Blueprint\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/08-implementation-summary.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Implementation\ Summary\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/02-risk-classification.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Risk\ Classification\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/12-release-handoff.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Release\ Handoff\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/04-synthesized-plan.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Synthesized\ Master\ Plan\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/07-codex-task-package.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Codex\ Task\ Packet\ —\ wave-3-live-sdk-rehearsal |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/01-evidence-bundle.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Evidence\ Bundle\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/11-security-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Security\ &\ Compliance\ Review\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/13-retrospective.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Retrospective\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/09-review-report.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Code\ Review\ Report\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/live-rehearsal-attempt-2026-05-18.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Wave\ 3\ Live\ SDK\ Rehearsal\ —\ Attempt\ Diagnostic\ (2026-05-18) |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/00-mission-brief.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Mission\ Brief\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/10-test-results.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Test\ Results\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/03-options-or-council-plans.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Council\ Plans\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-codex-wave-3-live-sdk-readiness/05-red-team-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Red-Team\ Review\ —\ Codex\ Wave\ 3\ Live\ SDK\ Readiness |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/06-execution-blueprint.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 06\ —\ Execution\ blueprint |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/08-implementation-summary.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 08\ —\ Implementation\ summary |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/02-risk-classification.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 02\ —\ Risk\ classification |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/12-release-handoff.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 12\ —\ Release\ handoff |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/04-synthesized-plan.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 04\ —\ Synthesized\ plan |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/07-codex-task-package.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 07\ —\ Codex\ task\ package |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/01-evidence-bundle.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 01\ —\ Evidence\ bundle\ —\ Launch-readiness\ closure\ (2026-05-18) |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/11-security-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 11\ —\ Security\ review |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/13-retrospective.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 13\ —\ Retrospective |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/09-review-report.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 09\ —\ Review\ report |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/00-mission-brief.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 00\ —\ Mission\ brief\ —\ Launch-readiness\ closure\ (2026-05-18) |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/10-test-results.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 10\ —\ Test\ results |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/03-options-or-council-plans.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 03\ —\ Options\ /\ council\ plans |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/05-red-team-review.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ 05\ —\ Red-team\ review |
| `/home/user/hazmat-command/docs/aos/runs/2026-05-18-launch-readiness-closure/release-report-2026-05-18.md` | hazmat-command (live) | docs/aos/runs/ | RECOVERY-ARTIFACT | HIGH | — | #\ Release\ report\ —\ Launch-readiness\ closure\ (2026-05-18) |
