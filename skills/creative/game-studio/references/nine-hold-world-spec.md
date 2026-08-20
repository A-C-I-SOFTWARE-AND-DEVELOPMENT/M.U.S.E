# World spec — `P = (R, C_terrain, C_object)`

Project: Nine-Hold Province (Skyrim-class *plan*, not a shipped world)
Prompt `q`: Skyrim-scale nordic-fantasy province, nine holds, dragons, player starts as a condemned prisoner. Truly dense and beautiful.
Engine: game-ue5
WorldClaw: yes (open-world)

## Intent (extract only)

- Scene type: open-world nordic-fantasy province
- Theme / visual style: nordic; dragons (stated)
- Key regions named in the prompt: nine holds (unnamed)
- Key objects named in the prompt: dragons; prisoner
- Spatial relations stated: none
- User preferences / hard constraints: density ≥ Skyrim; beauty; same or more assets/meshes (interpreted as *placed refs + kits*, not 10k unique hero meshes)
- Explicitly **unspecified** (left for Plan): hold names, biome list, exact km², dungeon list, engine settings

## Plan (studio-director)

### Shared
- Theme: nine-hold nordic province
- Visual style: teal water, emerald pine, amber interiors, cold stone. No purple / indigo / violet
- Material prefs: wet cobble, pine bark, snow crust, peat, basalt, salt crust
- Atmosphere: overcast north, volcanic haze in Ashfen, golden hour on Goldmere

### Regions `R`
| id | function φ | adjacent to | coverage (approx) | notes |
|---|---|---|---|---|
| r_hearth | plains capital | r_pine, r_gold, r_cairn | 4.2 km² | prisoner wake + slice city |
| r_frost | alpine port | r_pine, r_iron | 3.8 km² | cliff stair harbor |
| r_ash | volcanic march | r_salt, r_iron | 4.1 km² | fumaroles, slag fort |
| r_reed | wetland hold | r_hearth, r_gold | 3.6 km² | stilt town |
| r_salt | desert reach | r_ash, r_cairn | 4.4 km² | oasis + salt flats |
| r_pine | taiga frontier | r_hearth, r_frost | 4.8 km² | wilderness slice cell |
| r_cairn | highland barrows | r_hearth, r_salt | 3.9 km² | standing stones + slice dungeon |
| r_gold | lake city | r_hearth, r_reed | 4.0 km² | island keep |
| r_iron | border fortress | r_frost, r_ash | 4.2 km² | gate-city + mines |
| wild | interstitial biomes | all | remainder to 37 km² | PCG only |

### Terrain constraints `C_terrain`
| region | type | landform | surface | terrain assets |
|---|---|---|---|---|
| r_hearth | plains | river terrace | loam / cobble | wheat cards, river rock |
| r_frost | alpine | cliff + fjord | ice / wet stone | snow crust, icicle cards |
| r_ash | volcanic | scoria slope | basalt | fumarole decals |
| r_reed | wetland | peat basin | mud / water | reed cards |
| r_salt | desert | flat + dune edge | salt crust | heat haze (post) |
| r_pine | taiga | rolling | needle duff | pine HISM |
| r_cairn | highland | drumlin | moss / stone | standing-stone pads |
| r_gold | lacustrine | bowl | orchard / dock wood | ferry wake |
| r_iron | march | cut ridge | slag / road | siege yards |

### Object constraints `C_object`
| region | categories | count / density | appearance | object–object / object–terrain |
|---|---|---|---|---|
| capitals (5) | civic kit + market | modular streets | nordic timber/stone | contact-search T_place |
| towns (6) | farm/mine/stilt kits | low | regional | no float >0, sink ≤10cm |
| dungeons 100+ | barrow/mine/cave/fort | authored interiors | kit + 1 hero prop | greybox first |
| wilderness | trees/rocks/clutter | 1e5–1e6 refs | 3+2+1 mesh recipe | PCG / HISM |

### Selected for instance pass `R+`
- Slice first: r_hearth, r_pine (one cell), r_cairn (barrow)
- Why the others stay terrain-only for v1: they are streaming shells until slice gates pass

### Engine numbers (8GB 5070)
- World Partition cell: 128 m → ~2258 cells over 37 km²
- Resident ring: 3–5 cells; HLOD beyond
- `r.Streaming.PoolSize=3000`; Nanite ON; Lumen SW-RT
- Unique hero meshes v1: ≤80. Density is instances.

## Provenance
- I_concept source: none run this pass
- Backend actually used: 8B QLoRA planner (trained). 27B VLM inference base not on disk yet.
- This file is a **plan**. It is not a packaged world.
