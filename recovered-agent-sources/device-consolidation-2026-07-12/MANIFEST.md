# Device Consolidation Recovery Manifest

Recovered on 2026-07-12 during the device-wide M.U.S.E consolidation. This tree is an evidence-preserving source archive, not a second production implementation. Code here may be stale, incomplete, insecure by current standards, or superseded by active modules. Port behavior into active code only through tests and review.

## Recovery inventory

| Subtree | Files | Disposition |
| --- | ---: | --- |
| `aaa-cinema-studio/` | 112 | Complete recovered Next.js production-studio prototype; `.env`, build outputs, and dependencies excluded |
| `avatar-action-pack/` | 24 | Unique Android avatar/action overlay from the authorized-action archive, including its tests and design packets |
| `jarvis-capability-conversation-pack/` | 26 | Capability graph, deterministic selector, conversation shaping, and four architecture documents from a private branch |
| `legacy-omni-source/` | 17 | Earlier web/desktop UX components, two hardware-tuning scripts, and a UE5 scaffold prototype; retained for selective mining |
| `working-tree-overlays/` | 90 | Full copies of uncommitted tracked files from four old worktrees so no local-only edit is lost |
| `design-sync/` | 12 | Early cockpit tokens and component studies |
| `voice-control-prototype/` | 11 | Voice UI and proxy prototype; its permissive proxy backend is not production-approved |
| `n8n-stage1-prototype/` | 4 | Gate-to-n8n bridge, workflow, compose stack, and setup notes; secret `.env` excluded |
| `plans/hermes-10-10/` | 16 | Historical sprint plan recovered from a standalone ZIP |
| `base44/`, `blueprints/`, `research/`, `prompts/`, `visual-references/` | 25 | Architecture, no-mock contract pack, recovered connect-app source, research, legacy build prompt, bridge contract, and visual references |

The recovery pass contains 337 source/evidence files plus this manifest. Active product assets were placed outside this tree in `web/public/`, `demo_assets/1960s_mustang/`, `assets/marketing/muse-2026-legacy/`, `docs/research/`, `scripts/deploy/`, and `supabase/`.

## Source fingerprints

| Source | SHA-256 |
| --- | --- |
| `muse-source.tar.gz` | `5C588C0898F0A3D0A4EC4E3D9A8F394A671261F6CE74A0F31094F44836323E8A` |
| `hermes-agent-full-source.zip` | `4F4BD65677E6C7BB27B0C14E44D9DDBAD9089A7AAE0DE07F34BE6D1A7B93281F` |
| `hermes-agent-full-source-clean.zip` | `03B5183699F688671C31335524F2F8A8D713A6CE69B0304762D406271CFD0469` |
| `hermes-agent-local-authorized-action-avatar-test.zip` | `D5461B38F97BE068011DDFBCE529B1438EA26431DA6CCB44728FDFE7632CF576` |
| `hermes_10_10_plan.zip` | `AD55CB01B213374636F0729D9D3BC1013929BB5D6441CB79B6E6636FC00626ED` |
| `MUSE_Engineering_Blueprint.html` | `F248D8CE83C00D23BEE0732C43810C7456CB9154EB16FC032FD50DC512B8224B` |
| `muse-patch1.md` | `2260E120E50BC6E1AD8A4C28707A810A219712FB5A9FDE65783495DA40EC8E2D` |
| legacy full-build prompt | `A178E584B5B2EFC846A6FDF899638F2DB9FF81DE19674BA6895FA1B7FDCAD48C` |

All three full-source ZIPs export base commit `b8308c86faf59deb5ec668bbb2e3b84560b92ab8`, an ancestor of the active repository. The two base ZIPs differ only by generated dashboard bundles. The authorized-action ZIP adds the recovered overlay listed above.

## Safety decisions

- No source `.env`, API key, private key, token, database, browser profile, or credential store was copied.
- Generated `node_modules`, `.next`, `dist`, `build`, `target`, bytecode, and old full Git histories were excluded.
- The fake key fixture in the recovered avatar test was redacted to avoid false-positive secret scanning.
- `working-tree-overlays/broken-delegate-prototype/` contains a known incomplete branch body and must never be applied wholesale.
- The UE5 prototype assumes 5.7 and contains unverified templates. The active adapter must discover installed engine versions and pass compile/template tests before using any of it.
- The voice prototype launches a broad CLI proxy and enables permissive CORS. Reuse its interaction ideas, not its trust model.
- The n8n bridge assumes a prior AXIOM approval. Active integration must enforce that invariant server-side and test idempotency and retry behavior.
- The recovered OpenClaw Omni preview is a static interaction study, not a second active dashboard.
- The two Ollama scripts hardcode one GPU profile and one contains a malformed persistence example. They are hardware-tuning evidence only.
- A 36,114-entry voxel resource archive and 289 rendered frames were reviewed but not retained because their Minecraft-derived naming, unclear redistribution rights, and stylized rendering conflict with the approved photoreal direction. Only clean-room layout lessons were recorded in `research/voxel-scene-transfer-notes.md`.

## High-value concepts selected for active implementation

1. Source-backed AAA game/film pipeline surfaces and production entities.
2. Capability graph and deterministic route explanations.
3. Mobile/voice response shaping with explicit owner-gate language.
4. Avatar state as truthful execution state, separate from authority.
5. Gate-approved n8n delegation with idempotency and append-only evidence.
6. Unified static dashboard build staging and reproducible local Supabase configuration.
7. Windows path, shell-hook, logging, API-attempt, and post-turn reliability fixes from the Codex overlay.
8. Biome-scale silhouettes, landmark-led navigation, and vertical traversal translated into original PBR environments without retaining third-party voxel assets.
