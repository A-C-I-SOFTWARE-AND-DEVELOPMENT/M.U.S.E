"""Source-complete Unreal Engine 5.8 vertical-slice generator."""
from __future__ import annotations

import json
import math
import struct
import wave
from dataclasses import asdict
from pathlib import Path

from .prompt_spec import write_vertical_slice_spec
from .types import VerticalSliceSpec


def _render(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template.lstrip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_tone(path: Path, *, seed: int, seconds: float = 8.0) -> None:
    """Write deterministic stereo ambience without a hosted audio provider."""

    sample_rate = 22_050
    frames = int(sample_rate * seconds)
    phase = (seed % 360) * math.pi / 180
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        payload = bytearray()
        for index in range(frames):
            t = index / sample_rate
            envelope = min(1.0, t * 2.0, (seconds - t) * 2.0)
            sample = (
                math.sin(2 * math.pi * 73 * t + phase) * 0.20
                + math.sin(2 * math.pi * 109 * t) * 0.12
                + math.sin(2 * math.pi * 181 * t + phase / 2) * 0.05
            )
            value = int(max(-1, min(1, sample * envelope)) * 32767)
            payload.extend(struct.pack("<hh", value, value))
        wav.writeframes(bytes(payload))


_BUILD_CS = r"""
using UnrealBuildTool;

public class {{MODULE}} : ModuleRules
{
    public {{MODULE}}(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
            "UMG", "Slate", "SlateCore", "AIModule", "NavigationSystem"
        });
    }
}
"""

_TARGET_CS = r"""
using UnrealBuildTool;
using System.Collections.Generic;

public class {{MODULE}}Target : TargetRules
{
    public {{MODULE}}Target(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("{{MODULE}}");
    }
}
"""

_EDITOR_TARGET_CS = r"""
using UnrealBuildTool;
using System.Collections.Generic;

public class {{MODULE}}EditorTarget : TargetRules
{
    public {{MODULE}}EditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("{{MODULE}}");
    }
}
"""

_MODULE_CPP = r"""
#include "Modules/ModuleManager.h"
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {{MODULE}}, "{{MODULE}}");
"""

_CHARACTER_H = r"""
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "{{MODULE}}Character.generated.h"

class USpringArmComponent;
class UCameraComponent;

UCLASS()
class {{API}} A{{MODULE}}Character : public ACharacter
{
    GENERATED_BODY()

public:
    A{{MODULE}}Character();
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual float TakeDamage(float Damage, FDamageEvent const& Event,
        AController* DamageInstigator, AActor* DamageCauser) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    USpringArmComponent* CameraBoom;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
    UCameraComponent* FollowCamera;

    UPROPERTY(BlueprintReadOnly)
    float Health = 100.0f;

private:
    void MoveForward(float Value);
    void MoveRight(float Value);
    void Attack();
    void Interact();
    void TogglePause();
    void SaveGame();
    void LoadGame();
};
"""

_CHARACTER_CPP = r"""
#include "{{MODULE}}Character.h"
#include "{{MODULE}}GameMode.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "Kismet/GameplayStatics.h"

A{{MODULE}}Character::A{{MODULE}}Character()
{
    PrimaryActorTick.bCanEverTick = true;
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 420.0f;
    CameraBoom->bUsePawnControlRotation = true;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->bUsePawnControlRotation = false;
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0, 540, 0);
}

void A{{MODULE}}Character::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis("MoveForward", this, &A{{MODULE}}Character::MoveForward);
    Input->BindAxis("MoveRight", this, &A{{MODULE}}Character::MoveRight);
    Input->BindAxis("Turn", this, &APawn::AddControllerYawInput);
    Input->BindAxis("LookUp", this, &APawn::AddControllerPitchInput);
    Input->BindAction("Jump", IE_Pressed, this, &ACharacter::Jump);
    Input->BindAction("Jump", IE_Released, this, &ACharacter::StopJumping);
    Input->BindAction("Attack", IE_Pressed, this, &A{{MODULE}}Character::Attack);
    Input->BindAction("Interact", IE_Pressed, this, &A{{MODULE}}Character::Interact);
    Input->BindAction("Pause", IE_Pressed, this, &A{{MODULE}}Character::TogglePause);
    Input->BindAction("Save", IE_Pressed, this, &A{{MODULE}}Character::SaveGame);
    Input->BindAction("Load", IE_Pressed, this, &A{{MODULE}}Character::LoadGame);
}

void A{{MODULE}}Character::MoveForward(float Value)
{
    if (Controller && Value != 0.0f)
        AddMovementInput(FRotationMatrix(Controller->GetControlRotation()).GetUnitAxis(EAxis::X), Value);
}

void A{{MODULE}}Character::MoveRight(float Value)
{
    if (Controller && Value != 0.0f)
        AddMovementInput(FRotationMatrix(Controller->GetControlRotation()).GetUnitAxis(EAxis::Y), Value);
}

void A{{MODULE}}Character::Attack()
{
    FVector Start = FollowCamera->GetComponentLocation();
    FVector End = Start + FollowCamera->GetForwardVector() * 700.0f;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(MuseAttack), false, this);
    if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params) && Hit.GetActor())
        UGameplayStatics::ApplyDamage(Hit.GetActor(), 34.0f, GetController(), this, nullptr);
}

void A{{MODULE}}Character::Interact()
{
    if (A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>())
        GM->TryActivateBeacon(this);
}

void A{{MODULE}}Character::TogglePause()
{
    if (APlayerController* PC = Cast<APlayerController>(Controller))
        PC->SetPause(!UGameplayStatics::IsGamePaused(this));
}

void A{{MODULE}}Character::SaveGame()
{
    if (A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>())
        GM->SaveProgress(this);
}

void A{{MODULE}}Character::LoadGame()
{
    if (A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>())
        GM->LoadProgress(this);
}

float A{{MODULE}}Character::TakeDamage(float Damage, FDamageEvent const& Event,
    AController* DamageInstigator, AActor* DamageCauser)
{
    Health = FMath::Max(0.0f, Health - Damage);
    if (Health <= 0.0f)
    {
        Health = 100.0f;
        SetActorLocation(FVector(0, 0, 150));
    }
    return Damage;
}
"""

_ACTORS_H = r"""
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "{{MODULE}}Actors.generated.h"

class UStaticMeshComponent;
class USphereComponent;

UCLASS()
class {{API}} A{{MODULE}}Collectible : public AActor
{
    GENERATED_BODY()
public:
    A{{MODULE}}Collectible();
protected:
    UFUNCTION()
    void OnOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
        UPrimitiveComponent* OtherComponent, int32 OtherBodyIndex,
        bool bFromSweep, const FHitResult& SweepResult);
    UPROPERTY(VisibleAnywhere) USphereComponent* Trigger;
    UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Visual;
};

UCLASS()
class {{API}} A{{MODULE}}Enemy : public ACharacter
{
    GENERATED_BODY()
public:
    A{{MODULE}}Enemy();
    virtual void Tick(float DeltaSeconds) override;
    virtual float TakeDamage(float Damage, FDamageEvent const&, AController*, AActor*) override;
private:
    UPROPERTY() UStaticMeshComponent* Visual;
    float Health = 100.0f;
    float AttackCooldown = 0.0f;
};

UCLASS()
class {{API}} A{{MODULE}}Beacon : public AActor
{
    GENERATED_BODY()
public:
    A{{MODULE}}Beacon();
    UPROPERTY(VisibleAnywhere) UStaticMeshComponent* Visual;
};
"""

_ACTORS_CPP = r"""
#include "{{MODULE}}Actors.h"
#include "{{MODULE}}Character.h"
#include "{{MODULE}}GameMode.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

A{{MODULE}}Collectible::A{{MODULE}}Collectible()
{
    Trigger = CreateDefaultSubobject<USphereComponent>(TEXT("Trigger"));
    RootComponent = Trigger;
    Trigger->InitSphereRadius(90.0f);
    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
    Visual->SetupAttachment(Trigger);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    Visual->SetStaticMesh(Sphere.Object);
    Visual->SetWorldScale3D(FVector(0.45f));
    Trigger->OnComponentBeginOverlap.AddDynamic(this, &A{{MODULE}}Collectible::OnOverlap);
}

void A{{MODULE}}Collectible::OnOverlap(UPrimitiveComponent*, AActor* Other,
    UPrimitiveComponent*, int32, bool, const FHitResult&)
{
    if (Cast<A{{MODULE}}Character>(Other))
    {
        if (USoundBase* Pickup = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Pickup.Pickup")))
            UGameplayStatics::PlaySoundAtLocation(this, Pickup, GetActorLocation());
        if (A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>())
            GM->RegisterRelic();
        Destroy();
    }
}

A{{MODULE}}Enemy::A{{MODULE}}Enemy()
{
    PrimaryActorTick.bCanEverTick = true;
    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
    Visual->SetupAttachment(RootComponent);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    Visual->SetStaticMesh(Cube.Object);
    Visual->SetRelativeScale3D(FVector(0.7f, 0.7f, 1.6f));
}

void A{{MODULE}}Enemy::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    AttackCooldown -= DeltaSeconds;
    ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0);
    if (!Player) return;
    FVector Delta = Player->GetActorLocation() - GetActorLocation();
    Delta.Z = 0;
    if (Delta.Size() > 145.0f)
        AddMovementInput(Delta.GetSafeNormal(), 0.65f);
    else if (AttackCooldown <= 0.0f)
    {
        UGameplayStatics::ApplyDamage(Player, 12.0f, GetController(), this, nullptr);
        AttackCooldown = 1.2f;
    }
}

float A{{MODULE}}Enemy::TakeDamage(float Damage, FDamageEvent const&, AController*, AActor*)
{
    Health -= Damage;
    if (Health <= 0.0f)
    {
        if (USoundBase* Defeat = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Defeat.Defeat")))
            UGameplayStatics::PlaySoundAtLocation(this, Defeat, GetActorLocation());
        if (A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>())
            GM->RegisterEnemyDefeated();
        Destroy();
    }
    return Damage;
}

A{{MODULE}}Beacon::A{{MODULE}}Beacon()
{
    Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
    RootComponent = Visual;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    Visual->SetStaticMesh(Cylinder.Object);
    Visual->SetWorldScale3D(FVector(1.5f, 1.5f, 4.0f));
}
"""

_SAVE_H = r"""
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "{{MODULE}}SaveGame.generated.h"

UCLASS()
class {{API}} U{{MODULE}}SaveGame : public USaveGame
{
    GENERATED_BODY()
public:
    UPROPERTY() int32 SchemaVersion = 1;
    UPROPERTY() int32 Relics = 0;
    UPROPERTY() int32 EnemiesDefeated = 0;
    UPROPERTY() FVector PlayerLocation = FVector::ZeroVector;
};
"""

_HUD_H = r"""
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "{{MODULE}}HUD.generated.h"

UCLASS()
class {{API}} A{{MODULE}}HUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
"""

_HUD_CPP = r"""
#include "{{MODULE}}HUD.h"
#include "{{MODULE}}Character.h"
#include "{{MODULE}}GameMode.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Kismet/GameplayStatics.h"

void A{{MODULE}}HUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas) return;
    A{{MODULE}}GameMode* GM = GetWorld()->GetAuthGameMode<A{{MODULE}}GameMode>();
    A{{MODULE}}Character* Player = Cast<A{{MODULE}}Character>(UGameplayStatics::GetPlayerCharacter(this, 0));
    const FString Status = GM
        ? FString::Printf(TEXT("Relics %d/3   Guardians %d/3   Health %.0f"),
            GM->Relics, GM->EnemiesDefeated, Player ? Player->Health : 0.0f)
        : TEXT("Loading...");
    DrawText(Status, FLinearColor::White, 40, 35, GEngine->GetLargeFont(), 1.0f);
    DrawText(TEXT("WASD move | Mouse look | LMB attack | E activate | F5 save | F9 load | Esc pause"),
        FLinearColor(0.65f, 0.85f, 1.0f), 40, Canvas->SizeY - 55);
    if (UGameplayStatics::IsGamePaused(this))
        DrawText(TEXT("PAUSED / SETTINGS\\nEsc resume | +/- master volume"),
            FLinearColor::White, Canvas->SizeX * 0.38f, Canvas->SizeY * 0.42f,
            GEngine->GetLargeFont(), 1.2f);
    if (GM && GM->bWon)
        DrawText(TEXT("BEACON RESTORED — VERTICAL SLICE COMPLETE"),
            FLinearColor::Yellow, Canvas->SizeX * 0.25f, Canvas->SizeY * 0.45f,
            GEngine->GetLargeFont(), 1.2f);
}
"""

_GAMEMODE_H = r"""
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "{{MODULE}}GameMode.generated.h"

class A{{MODULE}}Character;

UCLASS()
class {{API}} A{{MODULE}}GameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    A{{MODULE}}GameMode();
    virtual void BeginPlay() override;
    UPROPERTY(BlueprintReadOnly) int32 Relics = 0;
    UPROPERTY(BlueprintReadOnly) int32 EnemiesDefeated = 0;
    UPROPERTY(BlueprintReadOnly) bool bWon = false;
    void RegisterRelic();
    void RegisterEnemyDefeated();
    void TryActivateBeacon(A{{MODULE}}Character* Player);
    void SaveProgress(A{{MODULE}}Character* Player);
    void LoadProgress(A{{MODULE}}Character* Player);
private:
    void SpawnSlice();
    void SpawnBlock(const FVector& Location, const FVector& Scale);
};
"""

_GAMEMODE_CPP = r"""
#include "{{MODULE}}GameMode.h"
#include "{{MODULE}}Actors.h"
#include "{{MODULE}}Character.h"
#include "{{MODULE}}HUD.h"
#include "{{MODULE}}SaveGame.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

A{{MODULE}}GameMode::A{{MODULE}}GameMode()
{
    DefaultPawnClass = A{{MODULE}}Character::StaticClass();
    HUDClass = A{{MODULE}}HUD::StaticClass();
}

void A{{MODULE}}GameMode::BeginPlay()
{
    Super::BeginPlay();
    SpawnSlice();
    if (USoundBase* Ambience = LoadObject<USoundBase>(nullptr, TEXT("/Game/Audio/Ambience.Ambience")))
        UGameplayStatics::SpawnSound2D(this, Ambience, 0.35f);
}

void A{{MODULE}}GameMode::SpawnBlock(const FVector& Location, const FVector& Scale)
{
    AStaticMeshActor* Block = GetWorld()->SpawnActor<AStaticMeshActor>(Location, FRotator::ZeroRotator);
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    Block->GetStaticMeshComponent()->SetStaticMesh(Cube);
    Block->SetActorScale3D(Scale);
    Block->GetStaticMeshComponent()->SetMobility(EComponentMobility::Static);
}

void A{{MODULE}}GameMode::SpawnSlice()
{
    SpawnBlock(FVector(3000, 0, -100), FVector(65, 18, 1));
    for (int32 Zone = 0; Zone < 3; ++Zone)
    {
        const float X = Zone * 2600.0f + 900.0f;
        SpawnBlock(FVector(X, -950, 250), FVector(2, 1, 7));
        SpawnBlock(FVector(X, 950, 250), FVector(2, 1, 7));
        GetWorld()->SpawnActor<A{{MODULE}}Collectible>(FVector(X, 0, 150), FRotator::ZeroRotator);
        GetWorld()->SpawnActor<A{{MODULE}}Enemy>(FVector(X + 550, 250, 150), FRotator::ZeroRotator);
    }
    GetWorld()->SpawnActor<A{{MODULE}}Beacon>(FVector(7800, 0, 200), FRotator::ZeroRotator);
    GetWorld()->SpawnActor<ADirectionalLight>(FVector(0, 0, 1200), FRotator(-45, -30, 0));
}

void A{{MODULE}}GameMode::RegisterRelic() { Relics = FMath::Min(3, Relics + 1); }
void A{{MODULE}}GameMode::RegisterEnemyDefeated() { EnemiesDefeated = FMath::Min(3, EnemiesDefeated + 1); }

void A{{MODULE}}GameMode::TryActivateBeacon(A{{MODULE}}Character* Player)
{
    if (!Player || Relics < 3 || EnemiesDefeated < 3) return;
    TArray<AActor*> Beacons;
    UGameplayStatics::GetAllActorsOfClass(this, A{{MODULE}}Beacon::StaticClass(), Beacons);
    if (Beacons.Num() && FVector::Dist(Player->GetActorLocation(), Beacons[0]->GetActorLocation()) < 500.0f)
        bWon = true;
}

void A{{MODULE}}GameMode::SaveProgress(A{{MODULE}}Character* Player)
{
    U{{MODULE}}SaveGame* Save = Cast<U{{MODULE}}SaveGame>(
        UGameplayStatics::CreateSaveGameObject(U{{MODULE}}SaveGame::StaticClass()));
    Save->Relics = Relics;
    Save->EnemiesDefeated = EnemiesDefeated;
    Save->PlayerLocation = Player ? Player->GetActorLocation() : FVector::ZeroVector;
    UGameplayStatics::SaveGameToSlot(Save, TEXT("MuseSlice"), 0);
}

void A{{MODULE}}GameMode::LoadProgress(A{{MODULE}}Character* Player)
{
    U{{MODULE}}SaveGame* Save = Cast<U{{MODULE}}SaveGame>(
        UGameplayStatics::LoadGameFromSlot(TEXT("MuseSlice"), 0));
    if (!Save || Save->SchemaVersion != 1) return;
    Relics = Save->Relics;
    EnemiesDefeated = Save->EnemiesDefeated;
    if (Player) Player->SetActorLocation(Save->PlayerLocation);
}
"""

_AUTOMATION_CPP = r"""
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "{{MODULE}}GameMode.h"
#include "{{MODULE}}Character.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMuseSliceSourceTest,
    "{{MODULE}}.VerticalSlice.SourceContract",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FMuseSliceSourceTest::RunTest(const FString&)
{
    TestNotNull(TEXT("Game mode class exists"), A{{MODULE}}GameMode::StaticClass());
    TestNotNull(TEXT("Character class exists"), A{{MODULE}}Character::StaticClass());
    return true;
}
#endif
"""

_DEFAULT_ENGINE = r"""
[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Game/Maps/MuseSlice
EditorStartupMap=/Game/Maps/MuseSlice
GlobalDefaultGameMode=/Script/{{MODULE}}.{{MODULE}}GameMode

[/Script/Engine.Engine]
+ActiveGameNameRedirects=(OldGameName="/Script/TP_ThirdPerson",NewGameName="/Script/{{MODULE}}")

[/Script/WindowsTargetPlatform.WindowsTargetSettings]
DefaultGraphicsRHI=DefaultGraphicsRHI_DX12
"""

_DEFAULT_GAME = r"""
[/Script/EngineSettings.GeneralProjectSettings]
ProjectID={{PROJECT_GUID}}
ProjectName={{TITLE}}
Description={{DESCRIPTION}}
ProjectVersion=0.1.0
CopyrightNotice=Generated by Muse Game Studio

[/Script/UnrealEd.ProjectPackagingSettings]
+DirectoriesToAlwaysCook=(Path="/Game/Audio")
"""

_DEFAULT_INPUT = r"""
[/Script/Engine.InputSettings]
+AxisMappings=(AxisName="MoveForward",Scale=1.000000,Key=W)
+AxisMappings=(AxisName="MoveForward",Scale=-1.000000,Key=S)
+AxisMappings=(AxisName="MoveRight",Scale=1.000000,Key=D)
+AxisMappings=(AxisName="MoveRight",Scale=-1.000000,Key=A)
+AxisMappings=(AxisName="Turn",Scale=1.000000,Key=MouseX)
+AxisMappings=(AxisName="LookUp",Scale=-1.000000,Key=MouseY)
+ActionMappings=(ActionName="Jump",Key=SpaceBar)
+ActionMappings=(ActionName="Attack",Key=LeftMouseButton)
+ActionMappings=(ActionName="Interact",Key=E)
+ActionMappings=(ActionName="Pause",Key=Escape)
+ActionMappings=(ActionName="Save",Key=F5)
+ActionMappings=(ActionName="Load",Key=F9)
bCaptureMouseOnLaunch=True
DefaultViewportMouseCaptureMode=CapturePermanently_IncludingInitialMouseDown
"""

_MAP_SCRIPT = r"""
import json
import pathlib
import unreal

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "game-spec.json").read_text(encoding="utf-8"))
LEVEL = "/Game/Maps/MuseSlice"

subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not subsystem.new_level(LEVEL):
    raise RuntimeError("could not create MuseSlice map")

world = unreal.EditorLevelLibrary.get_editor_world()
settings = world.get_world_settings()
settings.set_editor_property("kill_z", -2500.0)
unreal.EditorLevelLibrary.spawn_actor_from_class(
    unreal.PlayerStart, unreal.Vector(0.0, 0.0, 150.0)
)
unreal.EditorAssetLibrary.save_asset(LEVEL, only_if_is_dirty=False)

audio_tasks = []
for name in ("Ambience", "Pickup", "Defeat"):
    task = unreal.AssetImportTask()
    task.filename = str(ROOT / "Generated" / "Audio" / f"{name}.wav")
    task.destination_path = "/Game/Audio"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    audio_tasks.append(task)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(audio_tasks)

if not unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
    raise RuntimeError("map was not saved")
print("MUSE_MAP_BUILT", LEVEL, SPEC["title"])
"""

_AUDIT_SCRIPT = r"""
import json
import pathlib
import unreal

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "game-spec.json").read_text(encoding="utf-8"))
required = [
    "/Game/Maps/MuseSlice",
    "/Game/Audio/Ambience",
    "/Game/Audio/Pickup",
    "/Game/Audio/Defeat",
]
missing = [asset for asset in required if not unreal.EditorAssetLibrary.does_asset_exist(asset)]
if missing:
    raise RuntimeError("missing required assets: " + ", ".join(missing))
if len(SPEC["zones"]) != 3:
    raise RuntimeError("vertical slice requires exactly three zones")
actors = unreal.EditorLevelLibrary.get_all_level_actors()
if not any(actor.get_class().get_name() == "PlayerStart" for actor in actors):
    raise RuntimeError("map is missing PlayerStart")
print("MUSE_AUDIT_PASS", SPEC["project_id"], len(SPEC["zones"]))
"""


def generate_ue5_vertical_slice(root: str | Path, spec: VerticalSliceSpec) -> Path:
    """Materialize a fresh, reviewable UE 5.8 C++ project."""

    project_root = Path(root)
    module = spec.project_id
    api = f"{module.upper()}_API"
    source = project_root / "Source" / module
    guid_hex = f"{spec.seed:032X}"[-32:]
    # UE config's FGuid parser expects 32 hexadecimal digits (no hyphens).
    project_guid = guid_hex
    values = {"MODULE": module, "API": api}

    project = {
        "FileVersion": 3,
        "EngineAssociation": "5.8",
        "Category": "Games",
        "Description": spec.title,
        "Modules": [{"Name": module, "Type": "Runtime", "LoadingPhase": "Default"}],
        "Plugins": [
            {"Name": "PythonScriptPlugin", "Enabled": True},
            {"Name": "EditorScriptingUtilities", "Enabled": True},
        ],
    }
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / f"{module}.uproject").write_text(
        json.dumps(project, indent=2), encoding="utf-8"
    )
    write_vertical_slice_spec(spec, project_root / "game-spec.json")
    _write(source / f"{module}.Build.cs", _render(_BUILD_CS, **values))
    _write(project_root / "Source" / f"{module}.Target.cs", _render(_TARGET_CS, **values))
    _write(
        project_root / "Source" / f"{module}Editor.Target.cs",
        _render(_EDITOR_TARGET_CS, **values),
    )
    _write(source / f"{module}.cpp", _render(_MODULE_CPP, **values))
    for name, template in (
        (f"{module}Character.h", _CHARACTER_H),
        (f"{module}Character.cpp", _CHARACTER_CPP),
        (f"{module}Actors.h", _ACTORS_H),
        (f"{module}Actors.cpp", _ACTORS_CPP),
        (f"{module}SaveGame.h", _SAVE_H),
        (f"{module}HUD.h", _HUD_H),
        (f"{module}HUD.cpp", _HUD_CPP),
        (f"{module}GameMode.h", _GAMEMODE_H),
        (f"{module}GameMode.cpp", _GAMEMODE_CPP),
        (f"{module}Automation.cpp", _AUTOMATION_CPP),
    ):
        _write(source / name, _render(template, **values))

    _write(
        project_root / "Config" / "DefaultEngine.ini",
        _render(_DEFAULT_ENGINE, MODULE=module),
    )
    _write(
        project_root / "Config" / "DefaultGame.ini",
        _render(
            _DEFAULT_GAME,
            PROJECT_GUID=project_guid,
            TITLE=spec.title,
            DESCRIPTION=spec.objective,
        ),
    )
    _write(project_root / "Config" / "DefaultInput.ini", _DEFAULT_INPUT.lstrip())
    _write(project_root / "Content" / "Python" / "build_slice.py", _MAP_SCRIPT.lstrip())
    _write(project_root / "Content" / "Python" / "audit_slice.py", _AUDIT_SCRIPT.lstrip())
    _write_tone(
        project_root / "Generated" / "Audio" / "Ambience.wav",
        seed=spec.seed,
    )
    _write_tone(
        project_root / "Generated" / "Audio" / "Pickup.wav",
        seed=spec.seed + 17,
        seconds=0.35,
    )
    _write_tone(
        project_root / "Generated" / "Audio" / "Defeat.wav",
        seed=spec.seed + 31,
        seconds=0.65,
    )
    _write(
        project_root / "README.md",
        f"# {spec.title}\n\nGenerated UE 5.8 vertical slice.\n\n"
        f"Objective: {spec.objective}\n\n"
        "Controls: WASD, mouse, Space, LMB, E, F5, F9, Esc.\n",
    )
    return project_root


__all__ = ["generate_ue5_vertical_slice"]
