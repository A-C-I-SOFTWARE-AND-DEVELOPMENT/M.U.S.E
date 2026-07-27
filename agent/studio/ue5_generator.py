"""UE5 source generation with World Partition, PCG, Nanite, Lumen, and scalability."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from agent.studio.manifests import WorldManifest
from agent.studio.quality_profiles import QualityProfile


def _slug(title: str) -> str:
    parts = re.sub(r"[^a-zA-Z0-9]+", " ", title).split()
    mod = "".join(p[:1].upper() + p[1:] for p in parts) if parts else "Game"
    mod = re.sub(r"[^A-Za-z0-9]", "", mod)
    if mod and mod[0].isdigit():
        mod = "G" + mod
    return mod or "Game"


def _default_engine_ini(mod: str, profile: QualityProfile) -> str:
    lighting = profile.lighting
    streaming = profile.streaming
    lines = [
        "[/Script/EngineSettings.GameMapsSettings]",
        "GameDefaultMap=/Game/Maps/L_OpenWorld",
        "EditorStartupMap=/Game/Maps/L_OpenWorld",
        f"GlobalDefaultGameMode=/Script/{mod}.{mod}GameMode",
        "",
        "[/Script/Engine.RendererSettings]",
        "r.AllowStaticLighting=False",
        f"r.Nanite.ProjectEnabled={'True' if profile.material.require_nanite_fallback else 'False'}",
        f"r.Lumen.Enabled={'True' if lighting.lumen_enabled else 'False'}",
        f"r.Shadow.Virtual.Enable={'1' if lighting.virtual_shadow_maps else '0'}",
        "r.GenerateMeshDistanceFields=True",
        "r.DynamicGlobalIlluminationMethod=1" if lighting.lumen_enabled else "r.DynamicGlobalIlluminationMethod=0",
        "r.ReflectionMethod=1" if lighting.reflection_quality == "lumen" else "r.ReflectionMethod=0",
        f"r.VolumetricFog={'1' if lighting.volumetric_fog else '0'}",
        "r.ScreenPercentage=100",
        "r.MaxAnisotropy=16",
        "",
        "[/Script/Engine.WorldPartitionSettings]",
        f"bEnableWorldPartition={'True' if streaming.world_partition_enabled else 'False'}",
        "",
        "[/Script/NavigationSystem.NavigationSystemV1]",
        "bAllowClientSideNavigation=True",
        "bAutoCreateNavigationData=True",
        "",
        "[/Script/WindowsTargetPlatform.WindowsTargetSettings]",
        "DefaultGraphicsRHI=DefaultGraphicsRHI_DX12",
        "+D3D12TargetedShaderFormats=PCD3D_SM6",
        "",
        "[/Script/Engine.StreamingSettings]",
        f"s.AsyncLoadingTimeLimit=5.0",
        f"s.LevelStreamingActorsUpdateTimeLimit=5.0",
        f"s.PriorityLevelStreamingActorsUpdateExtraTime=5.0",
    ]
    return "\n".join(lines) + "\n"


def _default_scalability_ini(profile: QualityProfile) -> str:
    tier = profile.name
    return f"""[ScalabilityGroups]
sg.ResolutionQuality=100
sg.ViewDistanceQuality=3
sg.AntiAliasingQuality=3
sg.ShadowQuality=3
sg.GlobalIlluminationQuality={'3' if profile.lighting.lumen_enabled else '1'}
sg.ReflectionQuality={'3' if profile.lighting.reflection_quality == 'lumen' else '1'}
sg.PostProcessQuality=3
sg.TextureQuality=3
sg.EffectsQuality=3
sg.FoliageQuality=3
sg.ShadingQuality=3
sg.LandscapeQuality=3

[ProfileName]
Name={tier}
TargetFrameMs={profile.performance.target_frame_ms}
MaxDrawCalls={profile.polygon.max_draw_calls_per_frame}
MaxGpuMemoryMB={profile.performance.gpu_memory_mb}
"""


def _world_partition_ini(manifest: WorldManifest) -> str:
    wp = manifest.world_partition
    return f"""[/Script/Engine.WorldPartitionEditor]
GridSize={int(wp.get('cell_size_meters', 256))}
LoadingRange={int(wp.get('loading_range_meters', 2048))}
HLODLayerCount={int(wp.get('hlod_levels', 4))}
DataLayerCount={int(wp.get('data_layer_count', 16))}
"""


def _pcg_config(manifest: WorldManifest, profile: QualityProfile) -> dict[str, Any]:
    graphs = []
    for zone in manifest.zones:
        for graph in zone.pcg_graphs:
            graphs.append({
                "graph_name": graph,
                "zone_id": zone.zone_id,
                "biome_id": zone.biome_id,
                "density": zone.bounds_km2,
            })
    return {
        "version": "1.0",
        "engine": "UE5",
        "pcg_graphs": graphs,
        "foliage_scatter": {
            "instances_per_km2": profile.density.foliage_instances_per_km2,
            "max_instances": profile.polygon.foliage_instance_budget,
            "cull_distance_m": profile.streaming.loading_range_meters,
        },
        "rock_formation": {
            "cluster_size": (3, 8),
            "elevation_bias": 0.6,
        },
        "prop_placement": {
            "density_per_km2": profile.density.props_per_km2,
            "avoid_water": True,
        },
    }


def _build_cs(mod: str) -> str:
    return f"""using UnrealBuildTool;

public class {mod} : ModuleRules
{{
    public {mod}(ReadOnlyTargetRules Target) : base(Target)
    {{
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {{
            "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
            "AIModule", "NavigationSystem", "GameplayTasks", "PCG", "Niagara"
        }});
        PrivateDependencyModuleNames.AddRange(new string[] {{
            "Slate", "SlateCore", "UMG", "WorldPartitionEditor"
        }});
    }}
}}
"""


def _game_mode_h(mod: str) -> str:
    return f"""#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "{mod}GameMode.generated.h"

UCLASS()
class {mod.upper()}_API A{mod}GameMode : public AGameModeBase
{{
    GENERATED_BODY()
public:
    A{mod}GameMode();
}};
"""


def _game_mode_cpp(mod: str) -> str:
    return f"""#include "{mod}GameMode.h"
#include "{mod}Character.h"
#include "{mod}PlayerController.h"

A{mod}GameMode::A{mod}GameMode()
{{
    DefaultPawnClass = A{mod}Character::StaticClass();
    PlayerControllerClass = A{mod}PlayerController::StaticClass();
}}
"""


def _character_h(mod: str) -> str:
    return f"""#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputActionValue.h"
#include "{mod}Character.generated.h"

UCLASS()
class {mod.upper()}_API A{mod}Character : public ACharacter
{{
    GENERATED_BODY()
public:
    A{mod}Character();
protected:
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
    class USpringArmComponent* CameraBoom;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
    class UCameraComponent* FollowCamera;
}};
"""


def _character_cpp(mod: str) -> str:
    return f"""#include "{mod}Character.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Components/CapsuleComponent.h"

A{mod}Character::A{mod}Character()
{{
    GetCapsuleComponent()->InitCapsuleSize(42.f, 96.0f);
    bUseControllerRotationPitch = false;
    bUseControllerRotationYaw = false;
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 400.0f;
    CameraBoom->bUsePawnControlRotation = true;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;
}}

void A{mod}Character::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
}}
"""


def _player_controller_h(mod: str) -> str:
    return f"""#pragma once
#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "{mod}PlayerController.generated.h"

UCLASS()
class {mod.upper()}_API A{mod}PlayerController : public APlayerController
{{
    GENERATED_BODY()
}};
"""


def _creature_ai_h(mod: str) -> str:
    return f"""#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "{mod}CreatureBase.generated.h"

UCLASS()
class {mod.upper()}_API A{mod}CreatureBase : public ACharacter
{{
    GENERATED_BODY()
public:
    A{mod}CreatureBase();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
    float PerceptionRangeM = 50.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "AI")
    float AggroRangeM = 30.f;
protected:
    virtual void BeginPlay() override;
}};
"""


def _creature_ai_cpp(mod: str) -> str:
    return f"""#include "{mod}CreatureBase.h"
#include "AIController.h"

A{mod}CreatureBase::A{mod}CreatureBase()
{{
    AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
}}

void A{mod}CreatureBase::BeginPlay()
{{
    Super::BeginPlay();
}}
"""


def _game_target(mod: str, engine_version: str) -> str:
    include = f"EngineIncludeOrderVersion.Unreal5_{engine_version.replace('.', '_')[:3]}"
    return f"""using UnrealBuildTool;
using System.Collections.Generic;

public class {mod}Target : TargetRules
{{
    public {mod}Target(TargetInfo Target) : base(Target)
    {{
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = {include};
        ExtraModuleNames.Add("{mod}");
    }}
}}
"""


def _editor_target(mod: str, engine_version: str) -> str:
    include = f"EngineIncludeOrderVersion.Unreal5_{engine_version.replace('.', '_')[:3]}"
    return f"""using UnrealBuildTool;
using System.Collections.Generic;

public class {mod}EditorTarget : TargetRules
{{
    public {mod}EditorTarget(TargetInfo Target) : base(Target)
    {{
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        IncludeOrderVersion = {include};
        ExtraModuleNames.Add("{mod}");
    }}
}}
"""


def generate_ue5_project(
    project_root: Path,
    *,
    title: str,
    engine_version: str,
    profile: QualityProfile,
    world_manifest: WorldManifest | None = None,
) -> list[str]:
    """Materialize a substantive UE5 source tree. Returns list of written paths."""

    mod = _slug(title)
    project_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def write(rel: str, content: str) -> None:
        path = project_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path))

    plugins = [
        "ModelingToolsEditorMode", "PCG", "Water", "Niagara",
        "EnhancedInput", "WorldPartition", "AnimationWarping",
    ]
    uproject = {
        "FileVersion": 3,
        "EngineAssociation": engine_version,
        "Category": "Games",
        "Description": title,
        "Modules": [{"Name": mod, "Type": "Runtime", "LoadingPhase": "Default"}],
        "Plugins": [{"Name": p, "Enabled": True} for p in plugins],
    }
    write(f"{mod}.uproject", json.dumps(uproject, indent=2))

    source = f"Source/{mod}"
    write(f"{source}/{mod}.Build.cs", _build_cs(mod))
    write(f"{source}/{mod}.cpp", f'#include "Modules/ModuleManager.h"\nIMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {mod}, "{mod}");\n')
    write(f"{source}/{mod}.h", "#pragma once\n#include \"CoreMinimal.h\"\n")
    write(f"{source}/{mod}GameMode.h", _game_mode_h(mod))
    write(f"{source}/{mod}GameMode.cpp", _game_mode_cpp(mod))
    write(f"{source}/{mod}Character.h", _character_h(mod))
    write(f"{source}/{mod}Character.cpp", _character_cpp(mod))
    write(f"{source}/{mod}PlayerController.h", _player_controller_h(mod))
    write(f"{source}/{mod}PlayerController.cpp", f'#include "{mod}PlayerController.h"\n')
    write(f"{source}/{mod}CreatureBase.h", _creature_ai_h(mod))
    write(f"{source}/{mod}CreatureBase.cpp", _creature_ai_cpp(mod))
    write(f"Source/{mod}Target.cs", _game_target(mod, engine_version))
    write(f"Source/{mod}EditorTarget.cs", _editor_target(mod, engine_version))

    write("Config/DefaultEngine.ini", _default_engine_ini(mod, profile))
    write("Config/DefaultGame.ini", f"""[/Script/EngineSettings.GeneralProjectSettings]
ProjectName={title}
ProjectVersion=1.0.0
CompanyName=MUSE Studio
Description={title} — generated by MUSE AAA pipeline
""")
    write("Config/DefaultInput.ini", """[/Script/Engine.InputSettings]
DefaultViewportMouseCaptureMode=CapturePermanently_IncludingInitialMouseDown
DefaultViewportMouseLockMode=LockOnCapture
""")
    write("Config/DefaultScalability.ini", _default_scalability_ini(profile))

    if world_manifest:
        write("Config/WorldPartition.ini", _world_partition_ini(world_manifest))
        write(
            "Config/PCGGraphs.json",
            json.dumps(_pcg_config(world_manifest, profile), indent=2),
        )
        for zone in world_manifest.zones:
            write(
                f"Content/World/{zone.zone_id}/zone_manifest.json",
                json.dumps(asdict(zone), indent=2),
            )
        for biome in world_manifest.biomes:
            write(
                f"Content/World/{biome.biome_id}/biome_manifest.json",
                json.dumps(asdict(biome), indent=2),
            )

    write("Content/Maps/L_OpenWorld.umap.placeholder", "UE5 map placeholder — import via editor\n")
    write("Content/Navigation/NavMeshConfig.json", json.dumps({
        "agent_radius_cm": 42.0,
        "agent_height_cm": 192.0,
        "cell_size_cm": 19.0,
        "max_slope_degrees": 45.0,
    }, indent=2))
    write("Content/Collision/collision_profiles.json", json.dumps({
        "profiles": ["BlockAll", "OverlapAll", "Creature", "Projectile", "Interactable"],
        "complex_per_poly": True,
    }, indent=2))
    write("README.md", f"""# {title}

Generated by MUSE AAA pipeline.

## Engine configuration
- Unreal Engine {engine_version}
- Quality profile: {profile.name}
- World Partition: {profile.streaming.world_partition_enabled}
- Nanite: {profile.material.require_nanite_fallback}
- Lumen: {profile.lighting.lumen_enabled}
- Virtual Shadow Maps: {profile.lighting.virtual_shadow_maps}

## Build (requires local UE5 install)
```
"<UE5>/Engine/Build/BatchFiles/Build.bat" {mod}Editor Win64 Development -Project="{mod}.uproject"
```

No visual equivalence to any commercial title is claimed without measured UE render evidence.
""")
    return written


__all__ = ["generate_ue5_project", "_slug"]
