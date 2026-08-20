# Game Studio — agent roster

Single-domain agent roster for the `game-studio` skill. The skill's routing
table dispatches to these via `delegate_task`; each `<role>.md` is the
sub-agent's system prompt. These are **standalone** game-studio agents (not AOS
council registry entries) — broad AOS registry mutation is itself owner-gated,
and this roster is cohesive to one domain.

| Role | Authority | Produces | Does NOT |
|---|---|---|---|
| `studio-director` | L3 | Scope, engine, stage plan, WorldClaw `P` Plan, domains, gates | Build; spawn; publish |
| `game-designer` | L1 | GDD, systems spec, slice def, WorldClaw Intent | Implement; pick engine |
| `level-designer` | L1 | Greybox **or** WorldClaw terrain `T` + region plans | Final art; gameplay code |
| `gameplay-engineer` | L2 | Player controller + systems code | Assets; self-merge; spawn |
| `graphics-tech-artist` | L2 | Lighting, materials, WorldClaw refine renders | Gameplay logic; spawn |
| `3d-asset-artist` | L1 | Hero meshes + WorldClaw instances `O` | Approve spend/licensing |
| `audio-designer` | L1 | Music/SFX + cue list | Ship without QA; approve spend |
| `qa-playtest` | L2 | Playtest + WorldClaw contact/float gate | Fix code it reviews; publish |
| `build-release-engineer` | L3 | Headless export, artifact + log | Publish; set spawn grant |

**Maker-checker:** builders (`gameplay-engineer`, `3d-asset-artist`,
`audio-designer`) are reviewed by `qa-playtest` / an independent reviewer named
by `studio-director`. No role approves its own work.

**Owner gates:** engine spawn (`MUSE_GAME_ALLOW_SPAWN`), paid 3D/GPU spend,
asset licensing, and build publishing — all require `Yes, with authorization.`
