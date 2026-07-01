# Engine profiles

The Game Studio treats game engines as pluggable **worker profiles**
(`hermes_cli/profiles.py`), so `/orchestrate` and `kanban_decompose` route work
to them by name. Profiles are **user config** — adding them changes nothing in
the default runtime until you opt in by creating them.

## Reference `~/.hermes/config.yaml` snippet

```yaml
profiles:
  game-godot:                       # the headless-verifiable path
    model: anthropic:claude-opus
    enabled_toolsets: [terminal, files, image_gen, video_gen, asset3d_gen]
    preloaded_skills: [game-studio, comfyui]
    environment: local
    environment_config:
      gpu: false                    # Godot exports headless on CPU
      image: ""                     # local godot binary or a godot-headless image

  game-ue5:                         # documented SOTA-graphics path
    model: anthropic:claude-opus
    enabled_toolsets: [terminal, files, image_gen, video_gen, asset3d_gen]
    preloaded_skills: [game-studio, ue5-render, comfyui]
    environment: local
    environment_config:
      gpu: true                     # MRQ renders need a GPU
      image: ""                     # owner-provided UE5 host

  game-unity:                       # documented profile only
    model: anthropic:claude-opus
    enabled_toolsets: [terminal, files, image_gen, asset3d_gen]
    preloaded_skills: [game-studio]
    environment: local
    environment_config:
      gpu: true
```

## Bootstrap (one command)

Instead of hand-editing config, run the gated installer (dry-run by default):

```bash
# Show exactly what it would add:
python skills/creative/game-studio/scripts/install_profiles.py
# Merge the missing game-* profiles into $HERMES_HOME/config.yaml (backs up first):
python skills/creative/game-studio/scripts/install_profiles.py --apply
```

It only adds profiles that are missing (idempotent), writes a `.bak` backup
before touching the file, and never overwrites your existing profiles unless you
pass `--force`.

## Constraint

Only **`game-godot`** builds + runs **headlessly** in this environment / CI
(`godot --headless --export`). `game-ue5` and `game-unity` are documented
profiles that require an owner-provided licensed engine + GPU host — UE5 is the
genuine state-of-the-art-graphics path (Nanite, Lumen, MetaHuman), driven via
the `ue5-render` skill.

## Selecting an engine per job

```
/orchestrator route game-dev game-godot   # route the game-dev lane to Godot
/orchestrate build a vertical slice of a first-person exploration game
```

The chosen profile is recorded in the job's decision ledger.
