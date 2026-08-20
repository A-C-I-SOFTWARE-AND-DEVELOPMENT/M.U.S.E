# Game development API catalog (2025-2026)

Condensed reference of APIs and services callable programmatically
(REST/SDK/CLI) for a game studio pipeline. Prioritizes AI-era tools
with free tiers. Researched 2026-07-18.

Legend: [F] = free tier, [FC] = free credits on signup, [P] = paid, [OSS] = open source.

## 1. 3D asset generation (AI text/image-to-3D)

| Service | What | Pricing | URL |
|---|---|---|---|
| Meshy | Text/image → mesh + PBR textures; REST API | [F] 20/mo, $20+/mo | https://meshy.ai |
| Tripo3D | Text/image → 3D in seconds; REST + WebSocket | [FC] Pro $10+/mo | https://tripo3d.ai |
| TripoSR | Single image → 3D; open weights | [OSS] Apache 2.0 | https://github.com/VAST-AI-Research/TripoSR |
| CSM | Image/video → mesh, textures, animations | [P] per-credit | https://csm.ai |
| Hyper3D Rodin | High-quality AI mesh generation | [FC] REST API | https://hyper3d.ai |
| Luma Genie | Text-to-3D | [F] Discord/API | https://lumalabs.ai/genie |
| Hunyuan3D-2 | Tencent open 3D model, self-host | [OSS] | https://github.com/Tencent/Hunyuan3D-2 |

**Top pick:** Meshy (best free API tier) + TripoSR (self-host, unlimited).

## 2. Map / world / terrain generation

| Service | What | Pricing | URL |
|---|---|---|---|
| Promethean AI | AI environment creation, SDK | [F] indies | https://prometheanai.com |
| Gaea | Procedural terrain, node-based, Python | [F] indie | https://quadspinner.com |
| World Creator | Real-time terrain gen | [P] | https://www.world-creator.com |
| MapMagic 2 | Unity procedural terrain | [OSS] | https://github.com/denizdincor/MapMagic |
| CityGenAI | AI city/building generation | [P] | https://citygenai.com |

## 3. Animation (AI mocap / rigging)

| Service | What | Pricing | URL |
|---|---|---|---|
| Move.ai | Markerless mocap from video | [FC] REST API | https://move.ai |
| Plask | Browser mocap + rigging | [F] API | https://plask.ai |
| DeepMotion | Video → 3D animation | [FC] | https://deepmotion.com |
| Cascadeur | AI-assisted keyframe animation | [F] | https://cascadeur.com |
| Mixamo | Auto-rigger + animation library | [F] | https://mixamo.com |
| ActorCore | Rigged character library | [P] | https://actorcore.reallusion.com |

## 4. Texturing / materials

| Service | What | Pricing | URL |
|---|---|---|---|
| Polycam | Photogrammetry, PBR capture | [F] API | https://polycam.ai |
| AmbientCG | CC0 PBR textures, direct download | [F/OSS] | https://ambientcg.com |
| Poly Haven | CC0 HDRIs/textures/models | [F/OSS] API | https://polyhaven.com |
| Substance 3D | Adobe procedural materials | [P] SDK | https://substance3d.com |

## 5. Blender automation

| Tool | What | URL |
|---|---|---|
| Blender Python API (bpy) | Full programmatic control | https://docs.blender.org/api |
| blender-mcp | MCP bridge, AI-driven scene creation | https://github.com/ahujasid/blender-mcp |
| Poly Haven addon | One-click CC0 asset import (built into blender-mcp) | — |

See `game-asset-pipeline/references/blender-mcp-setup.md` for full setup.

## 6. Unreal Engine

| Tool | What | URL |
|---|---|---|
| Unreal Engine | Full source, Python + C++ API | https://unrealengine.com |
| unreal-mcp | MCP bridge to UE5 editor | (Hermes local skill) |
| MetaHuman Creator | Photoreal characters | https://metahuman.unrealengine.com |
| UEFN/Verse | Fortnite Creative scripting | https://dev.epicgames.com |

## 7. Unity

| Tool | What | Pricing | URL |
|---|---|---|---|
| Unity Cloud | Game services backend, REST | [F] tier | https://unity.com |
| Unity Muse | AI in-editor generation | [P] | https://unity.com/muse |

## 8. AI NPCs / dialog

| Service | What | Pricing | URL |
|---|---|---|---|
| Inworld AI | AI NPC brains, SDK + REST | [F] tier | https://inworld.ai |
| Convai | Character AI for games | [F] plugin | https://convai.com |
| Replica Studios | AI voice for NPCs | [P] | https://replicastudios.com |

## 9. Voice / audio / music

| Service | What | Pricing | URL |
|---|---|---|---|
| ElevenLabs | TTS + voice cloning, REST | [F] tier | https://elevenlabs.io |
| Hume AI | Emotion-aware voice | [F] | https://hume.ai |
| Suno | Music generation | [F] | https://suno.ai |
| Udio | Music generation | [F] | https://udio.com |

## 10. Physics / simulation

- PhysX (NVIDIA, OSS) — https://github.com/NVIDIA-Omniverse/PhysX
- Jolt Physics (OSS) — https://github.com/jrouwe/JoltPhysics
- Havok (commercial) — https://www.havok.com

## 11. Multiplayer / networking

| Service | What | Pricing | URL |
|---|---|---|---|
| Photon | Realtime multiplayer | [F] tier | https://photonengine.com |
| PlayFab | Microsoft game backend, REST | [F] | https://playfab.com |
| LootLocker | Player management | [F] tier | https://lootlocker.com |
| Mirror / Fish-Networking | Unity OSS networking | [OSS] | https://mirror-networking.com |

## 12. Asset marketplaces (with APIs)

| Service | What | URL |
|---|---|---|
| Sketchfab | 3D model store, REST API | https://sketchfab.com |
| Unity Asset Store | Unity assets | https://assetstore.unity.com |
| Unreal Marketplace | UE assets | https://unrealengine.com/marketplace |
| CGTrader | API for model search | https://cgtrader.com |

## 13. 2D art / pixel art

| Service | What | Pricing | URL |
|---|---|---|---|
| Scenario | Game-ready 2D asset gen | [F] tier API | https://scenario.com |
| Leonardo.ai | Image gen with game art models | [F] | https://leonardo.ai |

## Pipeline recommendation (free-first stack)

- **3D assets:** Meshy (free API) + TripoSR (self-host)
- **World gen:** Gaea (terrain) + Promethean AI (environment)
- **Animation:** Move.ai (mocap) + Mixamo (rigging, free)
- **Audio:** ElevenLabs (voice) + Suno (music)
- **NPCs:** Inworld AI
- **Pipeline control:** Blender MCP + unreal-mcp (both Hermes MCP servers)
- **Textures:** Poly Haven + AmbientCG (both CC0, free)
