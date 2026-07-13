# M.U.S.E. Desktop — 2026 Product Benchmark and State-of-the-Art Build Brief

Status: implementation source of truth for the desktop polish program  
Product: M.U.S.E. — Multi-Use Synaptic Entity  
Canonical app: `apps/desktop` (Tauri v2 + React 19)  
Brand system: Singularity — one white core in the void, one thin matte spectral ring

## 1. Product intent recovered from M.U.S.E. releases

M.U.S.E. is not positioned as another chatbot. The public release language establishes it as a local-first AI operating partner and native Singularity cockpit:

- Desktop release `muse-desktop-v0.1.10330` describes a Tauri v2 native shell that connects to the owner’s local M.U.S.E. gateway, stores no API keys, and originally required an owner phrase.
- The current Tauri manifest describes “Multi-Use Synaptic Entity — local-first AI operating partner.”
- The app already exposes real operational surfaces: Chat, Jobs, Approvals, Autonomy, Observatory, and Settings.
- The visual identity is explicitly codified as the Singularity: one white core in a black field, one restrained cyan-violet-blue ring, tonal elevation, no ornamental shadows, and spectral color below 20%.
- The desktop shell already supports tray operation, single instance behavior, managed gateway startup, health probing, persistent window state, PWA assets, and a global Ask M.U.S.E. dock.

Sources:

- Repository: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E
- Desktop release: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases/tag/muse-desktop-v0.1.10330
- Latest release stream: https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/releases
- Local design contract: `skills/singularity-design-system` and `design-system/tokens.json`

## 2. Competitive benchmark

The benchmark prioritizes durable interaction patterns rather than copying a competitor’s visual skin.

### ChatGPT desktop

What users are being trained to expect:

- A global shortcut that summons the assistant over the current task.
- Screenshot, file, image, and clipboard context without setup friction.
- Voice as a first-class input/output mode.
- Conversation continuity and searchable history.
- A calm, single-composer interaction model.

Product source: https://openai.com/chatgpt/desktop/

### Claude desktop

What matters:

- A focused, low-noise conversation surface.
- Native desktop installation and fast return to recent work.
- Local tool/data connection through MCP-style integrations.
- Strong artifact/document handling and visible attachment context.

Product/download source: https://claude.ai/download  
Help source: https://support.anthropic.com/en/articles/10065433-installing-claude-desktop

### Raycast AI

What users love:

- Near-zero launch latency and keyboard-first invocation.
- Commands, search, clipboard history, snippets, automation, and AI in one summonable surface.
- Actionable results rather than a conversation-only dead end.
- Small, composable extensions and clear shortcut hints.

Product source: https://www.raycast.com/ai

### Cursor

What users love:

- Agent state is legible: plans, edits, terminal work, checkpoints, review, and completion.
- Context is explicit and editable.
- Background/parallel agents do not block the primary workspace.
- The product makes high-agency execution feel controllable rather than mysterious.

Product source: https://www.cursor.com/features  
Changelog: https://www.cursor.com/changelog

### LM Studio

What users love:

- Local/private operation is visible and understandable.
- Models can be searched, loaded, unloaded, and inspected.
- Hardware/runtime status is concrete rather than hidden behind generic “online” language.
- The app works as both a consumer UI and a local API/runtime control center.

Product source: https://lmstudio.ai/  
Docs: https://lmstudio.ai/docs

### Perplexity / Comet

Durable pattern:

- Research is organized around sources and follow-up exploration.
- Browser/page context becomes an input without manual copy/paste.
- Citation provenance is part of the result presentation.

Product source: https://www.perplexity.ai/comet

### OpenClaw / always-on agent products

Durable pattern:

- Persistent gateway/tray operation.
- Device/channel pairing and remote access.
- Background tasks, scheduled work, approvals, and operational visibility.
- The security boundary must remain obvious when moving beyond the local device.

Product source: https://docs.openclaw.ai/

## 3. What users consistently love

Across categories, the strongest repeated signals are:

1. Instant access — summon from anywhere and focus the composer immediately.
2. Continuity — recent conversations and tasks survive restarts.
3. Context without ceremony — files, clipboard, screen, selected text, and current workspace.
4. Visible agency — show what the agent is doing, what it changed, what is waiting, and how to interrupt it.
5. Fast perceived performance — optimistic UI, streaming, progressive status, skeletons, and no blank waiting states.
6. Keyboard quality — global shortcut, command palette, predictable Enter/Escape behavior, discoverable shortcut hints.
7. Trust — local/private state, explicit external actions, approvals, logs, and reversible operations.
8. Personalization — model/voice/profile selection and remembered working preferences.
9. Native behavior — tray, notifications, deep links, update flow, window restoration, offline states, and OS-consistent controls.
10. Restraint — fewer competing panels, less dashboard chrome, and one obvious next action.

## 4. 2026 desktop table stakes

A state-of-the-art M.U.S.E. desktop release must include:

- One primary chat surface with persistent sessions, markdown/code rendering, copy/retry/stop, and attachments.
- Global summon shortcut and command palette.
- Voice input/output entry points with clear listening/speaking/interruption state.
- Search across conversations, jobs, approvals, and memory.
- Live agent activity with phase, elapsed time, tool/action summaries, and interruption controls.
- Notification center for completed jobs, failed work, and approval requests.
- File/screenshot/clipboard context capture.
- First-run flow that takes the user from install to first useful result in under one minute.
- Secure zero-touch local pairing on the same Windows account/device.
- Explicit owner authorization for LAN, remote, QR, or second-device pairing.
- Managed gateway lifecycle and repair UX.
- Auto-update with visible release notes and rollback-safe behavior.
- Accessibility: focus order, focus-visible, semantic labels, reduced motion, high contrast, 44px targets where practical.
- Honest empty/loading/error/offline states using real data only.

## 5. Current M.U.S.E. strengths

Preserve and amplify:

- Distinctive Singularity/Sacred Geometry identity.
- Local-first operating-partner positioning.
- Real Jobs, Approvals, Autonomy, and Observatory surfaces.
- Native Tauri tray and managed-brain architecture.
- Restrained spectral palette and tonal elevation.
- Existing streaming gateway client.
- Existing secure auto-pairing foundation for native loopback.
- Floating Ask M.U.S.E. dock and keyboard commands.

## 6. Current experience gaps

### Information architecture

- Home still contains prototype milestone copy and duplicates chat.
- Chat exists both as a full route and as a Home card, fragmenting state and hierarchy.
- Text-only nav provides weak scanability and no status/badge affordance.
- Jobs, approvals, and autonomy are destinations, but the shell does not summarize what needs attention now.

### Chat quality

- Conversation state is only component-local and disappears on navigation/restart.
- No session list, search, markdown rendering, code actions, attachments, stop/regenerate, model identity, or voice controls.
- Streaming uses a placeholder bubble but does not expose execution phases.
- Empty states are generic rather than task-oriented.

### Pairing/onboarding

- Secure local auto-pairing exists, but manual owner-phrase controls remain visually dominant while automatic pairing is pending.
- The first-run experience explains infrastructure instead of delivering a first success.
- Pairing state, gateway startup, and readiness are split across Home and Settings.

### Native product finish

- Updater public key is empty.
- The release describes unsigned builds.
- The backend is managed only when an installed `muse` CLI is already present; the installer is not yet a complete one-binary product.
- No dedicated desktop visual regression/E2E suite is present.

## 7. Target product model

### Core promise

“M.U.S.E. is ready when you are. Ask, delegate, or step away—your work stays visible, private, and under your control.”

### Primary navigation

1. Chat — the default landing surface and conversation home.
2. Work — jobs, plans, background agents, and execution history.
3. Approvals — only present as a primary destination when attention is required; otherwise represented by a badge/notification center.
4. Observatory — health, models, tools, memory, gateway, and audit signals.
5. Settings — identity, voice, models, privacy, devices, updates, and advanced gateway controls.

Autonomy becomes a mode/control within Work and Settings rather than a competing top-level concept unless research shows users repeatedly need it as a destination.

### Home replacement

Replace the generic dashboard Home with a calm “Today” layer inside Chat:

- Personalized greeting and readiness state.
- One prominent composer.
- Suggested actions based on real capabilities.
- Continue recent conversation/work.
- Compact “Needs you” strip for approvals/failures.
- Compact active-work strip for running jobs.

No duplicate full chat card and no static prototype phase rail.

## 8. Secure zero-touch pairing design

The owner phrase must disappear for the installed app on its own machine without becoming a general authentication bypass.

### Trusted local auto-pair eligibility

All conditions must hold:

- Request enters through the native Tauri command, not arbitrary web JavaScript.
- Gateway base resolves to loopback only (`127.0.0.1`, `::1`, or localhost after strict normalization).
- Native shell and gateway run under the same OS user context.
- Request includes a short-lived, single-use bootstrap secret created at install/first launch and stored using OS-protected credentials or a user-only file with restrictive permissions.
- Token is minted for this installation/device identity and stored through the native secure store, not plain browser localStorage.
- Bootstrap route is disabled after success except for an explicit local “repair connection” flow.
- Attempts are rate-limited and audited.

### Remote pairing

Owner authorization remains mandatory for:

- LAN or non-loopback gateways.
- Additional PCs, phones, browsers, and messaging channels.
- QR/deep-link pairing initiated outside the installed shell.
- Any request where native identity or same-user proof cannot be established.

### User experience

- First launch shows “Starting M.U.S.E.” with three truthful steps: Brain, Secure connection, Ready.
- No owner phrase field appears during normal local installation.
- If local auto-pair fails, present one primary “Repair connection” action and hide advanced manual pairing behind “Connect another device.”
- Settings → Devices lists this PC as “This device · trusted locally,” with revoke and reconnect controls.

## 9. Visual and interaction direction

### Preserve

- Void background, white core, matte spectral ring.
- Tonal elevation and hairline edges.
- Sacred Geometry as ambient identity, not decoration.
- Restricted spectral usage.

### Upgrade

- Increase spatial confidence: larger content frame, fewer nested cards, more breathing room.
- Make Chat the visual core; operational surfaces use denser, calm data layouts.
- Add icon + label navigation, badges, tooltips, and collapsed-rail behavior.
- Introduce a command palette and global search overlay using the same matte-ring focus treatment.
- Replace inline styles with named component classes and tokens.
- Add polished skeleton, progress, success, empty, error, and offline states.
- Use motion to explain state transitions only; never animate every surface.
- Add native titlebar drag regions/window controls where platform-appropriate.

## 10. Implementation program

### Phase A — shell and first run

- Chat-first route/default.
- New icon navigation and status/notification affordances.
- First-run readiness overlay.
- Local zero-touch pairing with secure native token storage.
- Consolidated connection repair UX.

### Phase B — state-of-the-art chat

- Persistent conversations and history rail.
- Markdown/code rendering and actions.
- Attachments, screenshot, clipboard, and voice controls.
- Stop/regenerate/edit/resend.
- Model/fusion state bar and execution activity.

### Phase C — operational intelligence

- Unified Work surface for running/queued/completed jobs.
- Approval inbox with urgency and clear consequence copy.
- Observatory health cards and audit timeline.
- Native notifications and deep links.

### Phase D — production release quality

- Bundle or bootstrap the required M.U.S.E. runtime.
- Signed Windows installer and updater keys.
- Auto-update UX and release notes.
- Accessibility audit.
- Playwright visual/E2E coverage plus Rust tests.
- Installer smoke test on a clean Windows profile.

## 11. Acceptance criteria

The polish program is complete only when:

- A clean installation reaches a ready, paired Chat screen without an owner phrase.
- Remote/additional-device pairing still requires explicit owner authorization.
- Chat is default and persists conversations across restarts.
- Every primary route has real loading, empty, error, offline, and success states.
- Keyboard-only operation covers navigation, composer, command palette, dialogs, approvals, and interruption.
- No prototype copy, duplicate chat, mock data, dead control, terminal panel, or iframe remains.
- UI build/typecheck, Tauri build, automated tests, accessibility checks, and clean-install smoke tests pass.
- A signed installer and updater manifest are produced for release.
