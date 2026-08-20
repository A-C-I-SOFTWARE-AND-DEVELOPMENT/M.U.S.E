# World spec — `P = (R, C_terrain, C_object)`

Project: <title>
Prompt `q`: <verbatim user brief>
Engine: game-godot | game-ue5 | game-unity
WorldClaw: yes (open-world) | no (linear / indoor — skip 2.6 / 3.5 / 4.5)

## Intent (game-designer only — extract, do not invent)

- Scene type:
- Theme / visual style (only if stated):
- Key regions named in the prompt:
- Key objects named in the prompt:
- Spatial relations stated:
- User preferences / hard constraints:
- Explicitly **unspecified** (leave for Plan):

## Plan (studio-director — complete the schema, preserve Intent)

### Shared
- Theme:
- Visual style (no purple / indigo / violet):
- Material prefs:
- Atmosphere / time of day / weather:

### Regions `R`
| id | function φ | adjacent to | coverage (approx) | notes |
|---|---|---|---|---|
| r0 | | | | |

### Terrain constraints `C_terrain`
| region | type | landform | surface | terrain assets |
|---|---|---|---|---|
| r0 | | peak/dune/terrace/erosion/flat | | rocks / veg / none |

### Object constraints `C_object`
| region | categories | count / density | appearance | object–object / object–terrain |
|---|---|---|---|---|
| r0 | | | | |

### Selected for instance pass `R+`
- Regions: 
- Why the others stay terrain-only:

## Provenance
- I_concept source (World Vision path / ComfyUI / none):
- Backend actually used (do not list paper models that did not run):
