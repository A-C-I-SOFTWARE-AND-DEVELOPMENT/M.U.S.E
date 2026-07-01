# Game Studio — agent roster

Single-domain agent roster for the `game-studio` skill. The skill's routing
table dispatches to these via `delegate_task`; each `<role>.md` is the
sub-agent's system prompt. These are **standalone** game-studio agents (not AOS
council registry entries) — broad AOS registry mutation is itself owner-gated,
and this roster is cohesive to one domain.

| Role | Authority | Produces | Does NOT |
|---|---|---|---|
| `studio-director` | L3 | Scope, engine choice, stage plan, disjoint domains, gate checklist | Build anything; spawn; publish |
| `game-designer` | L1 | GDD, core loop, systems spec, slice definition | Implement; pick engine |
| `level-designer` | L1 | Greybox layout + scene-graph plan | Final art; gameplay code |
| `gameplay-engineer` | L2 | Player controller + systems code | Assets; self-merge; spawn |
| `graphics-tech-artist` | L2 | Lighting, materials, post, SOTA render path | Gameplay logic; spawn |
| `3d-asset-artist` | L1 | Meshes (`asset3d_generate`) + textures (`comfyui`) | Approve spend/licensing |
| `audio-designer` | L1 | Music/SFX + cue list | Ship without QA; approve spend |
| `qa-playtest` | L2 | Playtest report + gate verdict + evidence | Fix code it reviews; publish |
| `build-release-engineer` | L3 | Headless export, artifact + log | Publish; set spawn grant |

**Maker-checker:** builders (`gameplay-engineer`, `3d-asset-artist`,
`audio-designer`) are reviewed by `qa-playtest` / an independent reviewer named
by `studio-director`. No role approves its own work.

**Owner gates:** engine spawn (`MUSE_GAME_ALLOW_SPAWN`), paid 3D/GPU spend,
asset licensing, and build publishing — all require `Yes, with authorization.`
