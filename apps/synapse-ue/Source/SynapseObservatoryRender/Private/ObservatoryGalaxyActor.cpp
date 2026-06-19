// ObservatoryGalaxyActor implementation — see ObservatoryGalaxyActor.h.
// Copyright A-C-I Software & Development. All rights reserved.

#include "ObservatoryGalaxyActor.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "ObservatoryRenderSettings.h"
#include "ObservatorySubsystem.h"
#include "ObservatoryTypes.h"
#include "SynapseObservatoryRender.h"

namespace
{
	// Live overrides for PIE tuning; -1 / negative => "use the actor value".
	TAutoConsoleVariable<int32> CVarLayoutMode(
		TEXT("muse.Observatory.LayoutMode"), -1,
		TEXT("Galaxy layout: 0 Gateway, 1 Phyllotaxis, 2 FibonacciSphere, 3 Platonic, 4 Polytope4D (-1 = actor value)."),
		ECVF_Default);

	TAutoConsoleVariable<float> CVarGeometryBlend(
		TEXT("muse.Observatory.GeometryBlend"), -1.0f,
		TEXT("Galaxy gateway<->geometry morph 0..1 (negative = actor value)."),
		ECVF_Default);

	TAutoConsoleVariable<int32> CVarPolytope(
		TEXT("muse.Observatory.Polytope"), -1,
		TEXT("4-polytope: 0 5-cell, 1 16-cell, 2 tesseract, 3 24-cell, 4 600-cell, 5 120-cell (-1 = actor value)."),
		ECVF_Default);

	TAutoConsoleVariable<int32> CVarRotationPlane(
		TEXT("muse.Observatory.RotationPlane"), -1,
		TEXT("4D rotation plane: 0 XY,1 XZ,2 XW,3 YZ,4 YW,5 ZW (-1 = actor value)."),
		ECVF_Default);

	FVector4 NormalizeVec4(const FVector4& P)
	{
		const double Len = FMath::Sqrt(P.X * P.X + P.Y * P.Y + P.Z * P.Z + P.W * P.W);
		if (Len <= 1e-9)
		{
			return P;
		}
		return FVector4(P.X / Len, P.Y / Len, P.Z / Len, P.W / Len);
	}
}  // namespace

AObservatoryGalaxyActor::AObservatoryGalaxyActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	ClusterMesh = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("ClusterMesh"));
	SetRootComponent(ClusterMesh);
	ClusterMesh->SetMobility(EComponentMobility::Movable);
	ClusterMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	MemberMesh = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("MemberMesh"));
	MemberMesh->SetupAttachment(ClusterMesh);
	MemberMesh->SetMobility(EComponentMobility::Movable);
	MemberMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AObservatoryGalaxyActor::BeginPlay()
{
	Super::BeginPlay();

	if (bUseProjectSettings)
	{
		if (const UObservatoryRenderSettings* S = GetDefault<UObservatoryRenderSettings>())
		{
			LayoutMode = S->LayoutMode;
			GeometryBlend = S->GeometryBlend;
			Platonic = S->Platonic;
			Polytope = S->Polytope;
			RotationPlane = S->RotationPlane;
			SecondRotationPlane = S->SecondRotationPlane;
			bDoubleRotation = S->bDoubleRotation;
			RotationSpeed = S->RotationSpeed;
			Projection = S->Projection;
			WorldScale = S->WorldScale;
		}
	}

	if (NodeMesh)
	{
		ClusterMesh->SetStaticMesh(NodeMesh);
		MemberMesh->SetStaticMesh(NodeMesh);
	}

	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnSnapshot.AddDynamic(this, &AObservatoryGalaxyActor::HandleSnapshot);
		Sub->OnLayout.AddDynamic(this, &AObservatoryGalaxyActor::HandleLayout);
		if (bAutoFetchOnBeginPlay)
		{
			Sub->FetchSnapshot();
		}
	}
	else
	{
		UE_LOG(LogSynapseObservatoryRender, Warning,
			TEXT("ObservatorySubsystem unavailable; galaxy stays idle."));
	}
}

void AObservatoryGalaxyActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->OnSnapshot.RemoveDynamic(this, &AObservatoryGalaxyActor::HandleSnapshot);
		Sub->OnLayout.RemoveDynamic(this, &AObservatoryGalaxyActor::HandleLayout);
	}
	Super::EndPlay(EndPlayReason);
}

void AObservatoryGalaxyActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bHaveSnapshot || LayoutMode != EMuseLayoutMode::Polytope4D)
	{
		return;
	}
	RotationAngle += static_cast<double>(RotationSpeed) * static_cast<double>(DeltaSeconds);
	RefreshClusterTransforms();
}

UObservatorySubsystem* AObservatoryGalaxyActor::ResolveSubsystem() const
{
	if (const UWorld* W = GetWorld())
	{
		if (UGameInstance* GI = W->GetGameInstance())
		{
			return GI->GetSubsystem<UObservatorySubsystem>();
		}
	}
	return nullptr;
}

void AObservatoryGalaxyActor::ApplyConsoleOverrides()
{
	const int32 LM = CVarLayoutMode.GetValueOnGameThread();
	if (LM >= 0 && LM <= static_cast<int32>(EMuseLayoutMode::Polytope4D))
	{
		LayoutMode = static_cast<EMuseLayoutMode>(LM);
	}
	const float GB = CVarGeometryBlend.GetValueOnGameThread();
	if (GB >= 0.0f)
	{
		GeometryBlend = FMath::Clamp(GB, 0.0f, 1.0f);
	}
	const int32 PV = CVarPolytope.GetValueOnGameThread();
	if (PV >= 0 && PV <= static_cast<int32>(EMusePolytope::Cell120))
	{
		Polytope = static_cast<EMusePolytope>(PV);
	}
	const int32 RP = CVarRotationPlane.GetValueOnGameThread();
	if (RP >= 0 && RP <= static_cast<int32>(EMuseRotationPlane::ZW))
	{
		RotationPlane = static_cast<EMuseRotationPlane>(RP);
	}
}

void AObservatoryGalaxyActor::HandleSnapshot(bool bOk, const FObsSnapshot& Snapshot)
{
	ClusterIds.Reset();
	GatewayPositions.Reset();
	HasGatewayPosition.Reset();
	bHaveSnapshot = false;

	if (!bOk || !Snapshot.bGraphAvailable)
	{
		ClusterMesh->ClearInstances();
		MemberMesh->ClearInstances();
		UE_LOG(LogSynapseObservatoryRender, Verbose,
			TEXT("snapshot unavailable (ok=%d available=%d); galaxy dormant."),
			bOk ? 1 : 0, Snapshot.bGraphAvailable ? 1 : 0);
		return;
	}

	for (const FObsCluster& C : Snapshot.Clusters)
	{
		ClusterIds.Add(C.Id);
		GatewayPositions.Add(C.bHasPos ? C.Pos : FVector::ZeroVector);
		HasGatewayPosition.Add(C.bHasPos);
	}

	bHaveSnapshot = true;
	RebuildClusters();

	UE_LOG(LogSynapseObservatoryRender, Log,
		TEXT("galaxy rebuilt: %d clusters, mode=%d, blend=%.2f."),
		GatewayPositions.Num(), static_cast<int32>(LayoutMode), GeometryBlend);
}

void AObservatoryGalaxyActor::HandleLayout(bool bOk, const FObsClusterLayout& Layout)
{
	MemberMesh->ClearInstances();
	if (!bOk || !Layout.bGraphAvailable || Layout.Nodes.Num() == 0)
	{
		return;
	}

	const FVector* Found = ClusterWorldById.Find(Layout.Cluster);
	const FVector Center = Found ? *Found : FVector::ZeroVector;
	const TArray<FVector> LocalAnchors = MuseGeometry::FibonacciSphere(Layout.Nodes.Num());
	const double LocalRadius = static_cast<double>(WorldScale) * 0.25;

	for (int32 i = 0; i < Layout.Nodes.Num(); ++i)
	{
		const FObsLayoutNode& Node = Layout.Nodes[i];
		const FVector Anchor = Center + LocalAnchors[i] * LocalRadius;
		// Node.Pos is LOCAL to the cluster center (spec §3.4).
		const FVector Gateway = Center + Node.Pos;
		const FVector Final = Node.bHasPos ? FMath::Lerp(Gateway, Anchor, GeometryBlend) : Anchor;
		MemberMesh->AddInstance(
			FTransform(FQuat::Identity, Final, FVector(NodeScale * 0.5f)), /*bWorldSpace=*/false);
	}
}

TArray<FVector> AObservatoryGalaxyActor::BuildAnchors(int32 Count) const
{
	TArray<FVector> Out;
	Out.Reserve(FMath::Max(0, Count));

	switch (LayoutMode)
	{
		case EMuseLayoutMode::Phyllotaxis:
		{
			const TArray<FVector2D> Pts = MuseGeometry::VogelPhyllotaxis(Count);
			const double MaxR = (Count > 1) ? FMath::Sqrt(static_cast<double>(Count - 1)) : 1.0;
			const double Scale = (MaxR > 1e-9) ? (static_cast<double>(WorldScale) / MaxR) : WorldScale;
			for (const FVector2D& P : Pts)
			{
				Out.Add(FVector(P.X * Scale, P.Y * Scale, 0.0));
			}
			break;
		}
		case EMuseLayoutMode::FibonacciSphere:
		{
			const TArray<FVector> Pts = MuseGeometry::FibonacciSphere(Count);
			for (const FVector& P : Pts)
			{
				Out.Add(P * WorldScale);
			}
			break;
		}
		case EMuseLayoutMode::Platonic:
		{
			const TArray<FVector> Verts = MuseGeometry::PlatonicVertices(Platonic, /*bNormalize=*/true);
			const int32 N = FMath::Max(1, Verts.Num());
			for (int32 i = 0; i < Count; ++i)
			{
				const FVector Dir = Verts[i % N];
				const double Shell = 1.0 + static_cast<double>(i / N) * 0.15;
				Out.Add(Dir * WorldScale * Shell);
			}
			break;
		}
		case EMuseLayoutMode::Gateway:
		default:
		{
			for (int32 i = 0; i < Count; ++i)
			{
				Out.Add(GatewayPositions.IsValidIndex(i) ? GatewayPositions[i] : FVector::ZeroVector);
			}
			break;
		}
	}
	return Out;
}

TArray<FVector4> AObservatoryGalaxyActor::BuildSource4D(int32 Count) const
{
	TArray<FVector4> Out;
	Out.Reserve(FMath::Max(0, Count));
	const TArray<FVector4> Verts = MuseGeometry::PolytopeVertices(Polytope);
	const int32 N = FMath::Max(1, Verts.Num());
	for (int32 i = 0; i < Count; ++i)
	{
		Out.Add(NormalizeVec4(Verts[i % N]));
	}
	return Out;
}

FVector AObservatoryGalaxyActor::ProjectedAnchor(int32 Index) const
{
	if (!Source4D.IsValidIndex(Index))
	{
		return FVector::ZeroVector;
	}
	FVector4 V = MuseGeometry::Rotate4D(Source4D[Index], RotationPlane, RotationAngle);
	if (bDoubleRotation)
	{
		V = MuseGeometry::Rotate4D(V, SecondRotationPlane, RotationAngle);
	}
	const FVector P = MuseGeometry::Project4DTo3D(V, Projection, 2.5);
	return P * WorldScale;
}

void AObservatoryGalaxyActor::RebuildClusters()
{
	ApplyConsoleOverrides();
	ClusterMesh->ClearInstances();
	ClusterWorldById.Reset();
	StaticAnchors.Reset();
	Source4D.Reset();

	const int32 Count = GatewayPositions.Num();
	if (Count == 0)
	{
		return;
	}

	if (LayoutMode == EMuseLayoutMode::Polytope4D)
	{
		Source4D = BuildSource4D(Count);
	}
	else
	{
		StaticAnchors = BuildAnchors(Count);
	}

	for (int32 i = 0; i < Count; ++i)
	{
		const FVector Anchor =
			(LayoutMode == EMuseLayoutMode::Polytope4D) ? ProjectedAnchor(i) : StaticAnchors[i];
		const FVector Gateway = GatewayPositions[i];
		const FVector Final =
			HasGatewayPosition[i] ? FMath::Lerp(Gateway, Anchor, GeometryBlend) : Anchor;
		ClusterMesh->AddInstance(
			FTransform(FQuat::Identity, Final, FVector(NodeScale)), /*bWorldSpace=*/false);
		if (ClusterIds.IsValidIndex(i))
		{
			ClusterWorldById.Add(ClusterIds[i], Final);
		}
	}
}

void AObservatoryGalaxyActor::RefreshClusterTransforms()
{
	const int32 Count = ClusterMesh->GetInstanceCount();
	if (Count == 0 || Source4D.Num() != Count)
	{
		return;
	}

	TArray<FTransform> Transforms;
	Transforms.Reserve(Count);
	for (int32 i = 0; i < Count; ++i)
	{
		const FVector Anchor = ProjectedAnchor(i);
		const FVector Gateway = GatewayPositions[i];
		const FVector Final =
			HasGatewayPosition[i] ? FMath::Lerp(Gateway, Anchor, GeometryBlend) : Anchor;
		Transforms.Add(FTransform(FQuat::Identity, Final, FVector(NodeScale)));
	}

	ClusterMesh->BatchUpdateInstancesTransforms(
		0, Transforms, /*bWorldSpace=*/false, /*bMarkRenderStateDirty=*/true, /*bTeleport=*/true);
}

void AObservatoryGalaxyActor::SetLayoutMode(EMuseLayoutMode NewMode)
{
	LayoutMode = NewMode;
	if (bHaveSnapshot)
	{
		RebuildClusters();
	}
}

void AObservatoryGalaxyActor::SetGeometryBlend(float NewBlend)
{
	GeometryBlend = FMath::Clamp(NewBlend, 0.0f, 1.0f);
	if (bHaveSnapshot)
	{
		RebuildClusters();
	}
}

void AObservatoryGalaxyActor::Refresh()
{
	if (UObservatorySubsystem* Sub = ResolveSubsystem())
	{
		Sub->FetchSnapshot();
	}
}
