<p align="center">
  <img src="assets/banner.png" alt="muse" width="100%">
</p>

# muse — 多用途突触实体 ◉

<p align="center">
  <a href="https://hermes-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/Docs-hermes--agent.nousresearch.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/NousResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://nousresearch.com"><img src="https://img.shields.io/badge/Built%20by-Nous%20Research-blueviolet?style=for-the-badge" alt="Built by Nous Research"></a>
  <a href="https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT"><img src="https://img.shields.io/badge/Developed%20by-A--C--I%20Software%20%26%20Development-0A7BBB?style=for-the-badge" alt="Developed by A-C-I Software and Development"></a>
  <a href="README.md"><img src="https://img.shields.io/badge/Lang-English-lightgrey?style=for-the-badge" alt="English"></a>
</p>

**由 [Nous Research](https://nousresearch.com) 构建的自进化 AI 代理。** 它是唯一内置学习闭环的智能代理——从经验中创建技能，在使用中改进技能，主动持久化知识，搜索过往对话，并在跨会话中逐步构建对你的深度理解。可以在 $5 的 VPS 上运行，也可以在 GPU 集群上运行，或者使用几乎零成本的 Serverless 基础设施。它不绑定你的笔记本——你可以在 Telegram 上与它对话，而它在云端 VM 上工作。由 [A-C-I Software and Development](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT) 开发与维护。

支持任意模型——[Nous Portal](https://portal.nousresearch.com)、[OpenRouter](https://openrouter.ai)（200+ 模型）、[NVIDIA NIM](https://build.nvidia.com)（Nemotron）、[小米 MiMo](https://platform.xiaomimimo.com)、[z.ai/GLM](https://z.ai)、[Kimi/Moonshot](https://platform.moonshot.ai)、[MiniMax](https://www.minimax.io)、[Hugging Face](https://huggingface.co)、OpenAI，或自定义端点。使用 `muse model` 即可切换——无需改代码，无锁定。

<table>
<tr><td><b>真正的终端界面</b></td><td>完整的 TUI，支持多行编辑、斜杠命令自动补全、对话历史、中断重定向和流式工具输出。</td></tr>
<tr><td><b>随你所在</b></td><td>Telegram、Discord、Slack、WhatsApp、Signal 和 CLI——全部从单个网关进程运行。语音备忘录转写、跨平台对话连续性。</td></tr>
<tr><td><b>闭环学习</b></td><td>代理管理记忆并定期自我提醒。复杂任务后自动创建技能。技能在使用中自我改进。FTS5 会话搜索配合 LLM 摘要实现跨会话回溯。<a href="https://github.com/plastic-labs/honcho">Honcho</a> 辩证式用户建模。兼容 <a href="https://agentskills.io">agentskills.io</a> 开放标准。</td></tr>
<tr><td><b>定时自动化</b></td><td>内置 cron 调度器，支持向任何平台投递。日报、夜间备份、周审计——全部用自然语言描述，无人值守运行。</td></tr>
<tr><td><b>委派与并行</b></td><td>生成隔离子代理处理并行工作流。编写 Python 脚本通过 RPC 调用工具，将多步管道压缩为零上下文开销的轮次。</td></tr>
<tr><td><b>随处运行</b></td><td>六种终端后端——本地、Docker、SSH、Daytona、Singularity 和 Modal。Daytona 和 Modal 提供 Serverless 持久化——代理环境空闲时休眠、按需唤醒，空闲期间几乎零成本。$5 VPS 或 GPU 集群都能跑。</td></tr>
<tr><td><b>研究就绪</b></td><td>批量轨迹生成、轨迹压缩——用于训练下一代工具调用模型。</td></tr>
<tr><td><b>完整的操作层，而非聊天机器人</b></td><td>muse 以运行时形式交付（<code>hermes_cli/jarvis_prime/</code>）：六种模式（Companion、Strategy、Critic、Operator、Builder、Mobile Voice）、意图/模式分类器、运行时人格注入、八道验证关卡、所有者授权和紧急停止。用 <code>/jarvis</code> 调用。</td></tr>
<tr><td><b>从目标到 PR 的编排</b></td><td>将单个目标分解为经校验的任务图——Job → 专职 Worker → 按任务的模型路由 → 校验关卡 → 防篡改决策账本。可在 TUI、网关私信或 Android 驾驶舱用 <code>/orchestrate</code> 驱动。</td></tr>
<tr><td><b>可检视的知识图谱</b></td><td>GraphRAG 将仓库代码、文档、Research Vault、Memory Tree 与各类账本统一为一张带类型、可溯源的图（仓库约 28k 个节点），支持 local、global、coding 三种查询模式——让工作复用既有实现，而非重造。</td></tr>
<tr><td><b>自治企业议会</b></td><td>AOS Enterprise Council——233 个顶层代理 + 108 个子代理，覆盖 18 个领域（架构、安全、合规、QA、发布、产品、心理、HazMat Command 等），用于审计、上线就绪评估和多视角评审。</td></tr>
<tr><td><b>原生 Android 驾驶舱</b></td><td>Kotlin + Compose 应用（<code>apps/android/</code>），与 muse 网关配对：流式对话、设备端语音录入、作业控制、锁屏式所有者审批、证据/记忆/图谱视图，以及紧急停止。手机上不保存任何模型提供商密钥。</td></tr>
</table>

---

## A-C-I Software and Development 构建的内容

muse 是开放底座。在其之上，**[A-C-I Software and Development](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT)** 构建了将其转变为受治理、本地优先 AI 操作伙伴的层——**muse**。以下每一项都是本仓库中真实、经测试的代码，而非路线图。

- **muse 操作层** — 位于 [`hermes_cli/jarvis_prime/`](hermes_cli/jarvis_prime/) 的运行时（约 100 个模块）：六种模式、意图/模式分类器、运行时人格注入、需精确口令的所有者授权、紧急停止，以及带每日所有者简报的只读监视器。见 [`docs/jarvis-prime-operating-system.md`](docs/jarvis-prime-operating-system.md)。
- **可溯源优先的认知层** — Memory Tree（工作/会话/持久记忆，带来源引用、置信度下限、矛盾报告、取代关系，且绝不静默覆写）、Research Vault、证据引擎（BM25 + 记忆混合检索，带引用校验），以及 TokenJuice——一个确定性、按 token 预算的上下文编译器，会筛除密钥。
- **GraphRAG 知识图谱** — [`hermes_cli/jarvis_prime/graphrag/`](hermes_cli/jarvis_prime/graphrag/) 将代码、文档、Research Vault、Memory Tree 与各类账本统一为一张带类型、可溯源的图（仓库约 28k 节点 / 52k 边），支持 local/global/coding 查询。见 [`docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md`](docs/jarvis_architecture/GRAPHRAG_KNOWLEDGE_GRAPH.md)。
- **从目标到 PR 的编排** — 五个原语（Job、Worker、模型路由、校验关卡、决策账本）将目标分解为经校验的任务图并发布结果，每个决策都记入防篡改账本。见 [`docs/orchestration/`](docs/orchestration/)。
- **AOS Enterprise Council** — 233 个顶层代理 + 108 个子代理，覆盖 18 个领域，用于审计、加固、上线就绪评估与多视角评审。见 [`skills/aos-enterprise-council/`](skills/aos-enterprise-council/)。
- **八道验证关卡 + 可验证护栏** — Planning、Build、Review、Test、Security、Release、Owner Approval、Rollback——由哈希链式、防篡改的证据账本（`verify_chain()`）支撑。见 [`docs/jarvis-verification-gates.md`](docs/jarvis-verification-gates.md)。
- **版本化 Constitution + 自审层** — 一份只追加的行为准则（条款 `C1…Cn`，带严重度分级）作为评分基准，外加奖励作弊 / Goodhart 检测和能力带壁垒。见 [`docs/jarvis-constitution.md`](docs/jarvis-constitution.md)。
- **以构造保障的所有者控制** — 所有者门控动作（花钱、部署、发布、OAuth、凭据变更、包发布、受监管声明）会延后，直到你精确回复 `Yes, with authorization.`；工作区范围的高自治编码模式仅自动批准本地摩擦，绝不削弱这些门控；每次自我更新都是可评审的提案，绝非静默改写。
- **免费优先的模型路由 + 闭环学习** — 路由顺序为本地 OSS → 托管免费 → 官方 Claude Code / Codex worker 通道 → 付费（仅按需开启），并依据实测记分卡按任务类别选择；一条经所有者批准的流水线（SFT → ORPO/DPO → GRPO）只有在留出基准壁垒上胜过现任时才晋升模型。见 [`docs/ai-intelligence/`](docs/ai-intelligence/)。
- **原生 Android 驾驶舱 + 语音优先** — Kotlin/Compose 应用（[`apps/android/`](apps/android/)）与驾驶舱网关配对：流式对话、设备端语音录入、作业控制、所有者审批、证据/记忆/图谱视图、自治控制和紧急停止——未配对时回退到剪贴板交接。模型提供商密钥绝不离开网关。
- **在你所在之处运行** — 原生 Windows 支持（[`scripts/install.ps1`](scripts/install.ps1)、带受限回退的计划任务服务、便携式 Git、无需管理员权限），与 Linux/macOS/WSL2 及 Termux 路径并行。

---

## 快速安装

```bash
curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/main/scripts/install.sh | bash
```

支持 Linux、macOS、WSL2 和 Android (Termux)。安装程序会自动处理平台特定的配置。

> **Android / Termux：** 已测试的手动安装路径请参考 [Termux 指南](https://hermes-agent.nousresearch.com/docs/getting-started/termux)。在 Termux 上，muse 会安装精选的 `.[termux]` 扩展，因为完整的 `.[all]` 扩展会拉取 Android 不兼容的语音依赖。
>
> **Windows：** 原生 Windows 不受支持。请安装 [WSL2](https://learn.microsoft.com/zh-cn/windows/wsl/install) 并运行上述命令。

安装后：

```bash
source ~/.bashrc    # 重新加载 shell（或: source ~/.zshrc）
muse              # 开始对话！
```

---

## 快速入门

```bash
muse              # 交互式 CLI — 开始对话
muse model        # 选择 LLM 提供商和模型
muse tools        # 配置启用的工具
muse config set   # 设置单个配置项
muse gateway      # 启动消息网关（Telegram、Discord 等）
muse setup        # 运行完整设置向导（一次性配置所有内容）
muse claw migrate # 从 OpenClaw 迁移（如果来自 OpenClaw）
muse update       # 更新到最新版本
muse doctor       # 诊断问题
```

📖 **[完整文档 →](https://hermes-agent.nousresearch.com/docs/)**

## CLI 与消息平台 快速对照

muse 有两种入口：用 `muse` 启动终端 UI，或运行网关从 Telegram、Discord、Slack、WhatsApp、Signal 或 Email 与之对话。进入对话后，许多斜杠命令在两种界面中通用。

| 操作 | CLI | 消息平台 |
|------|-----|----------|
| 开始对话 | `muse` | 运行 `muse gateway setup` + `muse gateway start`，然后给机器人发消息 |
| 开始新对话 | `/new` 或 `/reset` | `/new` 或 `/reset` |
| 更换模型 | `/model [provider:model]` | `/model [provider:model]` |
| 设置人格 | `/personality [name]` | `/personality [name]` |
| 重试或撤销上一轮 | `/retry`、`/undo` | `/retry`、`/undo` |
| 压缩上下文 / 查看用量 | `/compress`、`/usage`、`/insights [--days N]` | `/compress`、`/usage`、`/insights [days]` |
| 浏览技能 | `/skills` 或 `/<skill-name>` | `/skills` 或 `/<skill-name>` |
| 中断当前工作 | `Ctrl+C` 或发送新消息 | `/stop` 或发送新消息 |
| 平台特定状态 | `/platforms` | `/status`、`/sethome` |

完整命令列表请参阅 [CLI 指南](https://hermes-agent.nousresearch.com/docs/user-guide/cli) 和 [消息网关指南](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)。

---

## 文档

所有文档位于 **[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)**：

| 章节 | 内容 |
|------|------|
| [快速开始](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) | 安装 → 设置 → 2 分钟内开始首次对话 |
| [CLI 使用](https://hermes-agent.nousresearch.com/docs/user-guide/cli) | 命令、快捷键、人格、会话 |
| [配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) | 配置文件、提供商、模型、所有选项 |
| [消息网关](https://hermes-agent.nousresearch.com/docs/user-guide/messaging) | Telegram、Discord、Slack、WhatsApp、Signal、Home Assistant |
| [安全](https://hermes-agent.nousresearch.com/docs/user-guide/security) | 命令审批、DM 配对、容器隔离 |
| [工具与工具集](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools) | 40+ 工具、工具集系统、终端后端 |
| [技能系统](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | 过程记忆、技能中心、创建技能 |
| [记忆](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory) | 持久记忆、用户画像、最佳实践 |
| [MCP 集成](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | 连接任意 MCP 服务器扩展能力 |
| [定时调度](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) | 定时任务与平台投递 |
| [上下文文件](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files) | 影响每次对话的项目上下文 |
| [架构](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture) | 项目结构、代理循环、关键类 |
| [贡献](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) | 开发设置、PR 流程、代码风格 |
| [CLI 参考](https://hermes-agent.nousresearch.com/docs/reference/cli-commands) | 所有命令和标志 |
| [环境变量](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) | 完整环境变量参考 |

---

## 从 OpenClaw 迁移

如果你来自 OpenClaw，muse 可以自动导入你的设置、记忆、技能和 API 密钥。

**首次安装时：** 安装向导（`muse setup`）会自动检测 `~/.openclaw` 并在配置开始前提供迁移选项。

**安装后任意时间：**

```bash
muse claw migrate              # 交互式迁移（完整预设）
muse claw migrate --dry-run    # 预览将要迁移的内容
muse claw migrate --preset user-data   # 仅迁移用户数据，不含密钥
muse claw migrate --overwrite  # 覆盖已有冲突
```

导入内容：
- **SOUL.md** — 人格文件
- **记忆** — MEMORY.md 和 USER.md 条目
- **技能** — 用户创建的技能 → `~/.hermes/skills/openclaw-imports/`
- **命令白名单** — 审批模式
- **消息设置** — 平台配置、允许用户、工作目录
- **API 密钥** — 白名单中的密钥（Telegram、OpenRouter、OpenAI、Anthropic、ElevenLabs）
- **TTS 资产** — 工作区音频文件
- **工作区指令** — AGENTS.md（使用 `--workspace-target`）

使用 `muse claw migrate --help` 查看所有选项，或使用 `openclaw-migration` 技能进行交互式代理引导迁移（含干运行预览）。

---

## 贡献

欢迎贡献！请参阅 [贡献指南](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) 了解开发设置、代码风格和 PR 流程。

贡献者快速开始——克隆并使用 `setup-hermes.sh`：

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/musegit
cd hermes-agent
./setup-hermes.sh     # 安装 uv、创建 venv、安装 .[all]、创建符号链接 ~/.local/bin/hermes
./hermes              # 自动检测 venv，无需先 source
```

手动安装（等效于上述命令）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"
python -m pytest tests/ -q
```

---

## 社区

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [技能中心](https://agentskills.io)
- 🐛 [问题反馈](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/issues)
- 💡 [讨论区](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/muse/discussions)
- 🔌 [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — 社区微信桥接：在同一微信账号上运行 muse 和 OpenClaw。

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

由 [Nous Research](https://nousresearch.com) 构建。由 [A-C-I Software and Development](https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT) 开发与维护。
