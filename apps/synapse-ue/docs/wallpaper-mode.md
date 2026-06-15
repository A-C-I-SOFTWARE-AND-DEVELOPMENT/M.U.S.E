# Desktop wallpaper mode (UE5 SynapseObservatory)

Run the native UE5 Neural Observatory as a live **desktop wallpaper** — rendered
behind the desktop icons on the PC flagship — pulsing on every real system action
from the new fused feed `GET /v1/observatory/actions`. This is the native desktop
member of the cross-device "live neural-network wallpaper" program; it shares the
exact gateway data contract with the web (`?wallpaper=1`) and Android renderers.

> Built on the owner's machine in the UE 5.6 editor (this cloud repo cannot
> compile UE). The additive wire type `FObsActionEvent` is already committed in
> `ObservatoryTypes.h`; the subsystem wiring + window mode below are applied
> in-editor.

## 1. Subsystem: consume the actions feed

`UObservatorySubsystem` already streams `/v1/observatory/stream` via a
`UMuseSseClient` and parses frames in `HandleSseEvent`. Add a **second** SSE
consumer for `/v1/observatory/actions`, mirroring the existing `StartStream` /
`SseClient` / `HandleSseEvent` exactly. All broadcasts stay on the game thread
(the SSE client delivers there), matching the module's threading rule.

**`ObservatorySubsystem.h`** — add the delegate, property, methods, and a second client:

```cpp
/** SSE (actions) — one fused action for the live wallpaper. Game thread. */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnObsAction, const FObsActionEvent&, Event);

// … inside UObservatorySubsystem (public):
UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
void StartActionsStream();
UFUNCTION(BlueprintCallable, Category = "MUSE|Observatory")
void StopActionsStream();
UFUNCTION(BlueprintPure, Category = "MUSE|Observatory")
bool IsActionStreaming() const;

/** Fused all-actions feed. Game thread. */
UPROPERTY(BlueprintAssignable, Category = "MUSE|Observatory")
FOnObsAction OnAction;

// … private:
UFUNCTION()
void HandleActionEvent(const FString& EventType, const FString& Data);

UPROPERTY()
TObjectPtr<UMuseSseClient> ActionSseClient;
```

**`ObservatorySubsystem.cpp`** — mirror `StartStream`/`StopStream`/`IsStreaming`
against `/v1/observatory/actions`, and parse in `HandleActionEvent`:

```cpp
void UObservatorySubsystem::StartActionsStream()
{
    if (!ActionSseClient)
    {
        ActionSseClient = NewObject<UMuseSseClient>(this);
        ActionSseClient->OnSseEvent.AddDynamic(this, &UObservatorySubsystem::HandleActionEvent);
    }
    // Same gateway client / bearer plumbing StartStream() uses:
    ActionSseClient->Start(TEXT("/v1/observatory/actions"), ResolveGatewayClient());
}

void UObservatorySubsystem::StopActionsStream()
{
    if (ActionSseClient) { ActionSseClient->Stop(); }
}

bool UObservatorySubsystem::IsActionStreaming() const
{
    return ActionSseClient && ActionSseClient->IsRunning();
}

void UObservatorySubsystem::HandleActionEvent(const FString& EventType, const FString& Data)
{
    if (EventType == TEXT("meta.resync")) { return; } // control only

    TSharedPtr<FJsonObject> Obj;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Data);
    if (!FJsonSerializer::Deserialize(Reader, Obj) || !Obj.IsValid()) { return; } // drop, never invent

    FObsActionEvent Ev;
    Ev.Kind     = Obj->GetStringField(TEXT("kind"));
    Ev.Source   = Obj->GetStringField(TEXT("source"));
    Ev.Label    = Obj->GetStringField(TEXT("label"));
    Ev.Severity = Obj->GetStringField(TEXT("severity"));
    Obj->TryGetNumberField(TEXT("weight"), Ev.Weight);
    if (const TSharedPtr<FJsonObject>* Target; Obj->TryGetObjectField(TEXT("target"), Target))
    {
        (*Target)->TryGetStringField(TEXT("cluster_id"), Ev.ClusterId);
        (*Target)->TryGetStringField(TEXT("job_id"), Ev.JobId);
    }
    OnAction.Broadcast(Ev); // game thread (UMuseSseClient delivers here)
}
```

Match the exact `UMuseSseClient` method names your `HandleSseEvent`/`StartStream`
use (`Start`/`Stop`/`IsRunning`/`OnSseEvent`) — copy them verbatim from the
existing stream path so the actions path is identical bar the route.

## 2. Renderer binding (dressing)

Bind the Observatory map's renderer to `OnAction` and map each `Kind` to a VFX
primitive (same set the Nero theme uses, `docs/nero-theme.md`):

| `Kind` | Primitive |
|---|---|
| `cluster.spark` | pulse the cluster at `ClusterId` (Niagara, intensity ∝ `Weight`) |
| `pipeline.packet` | spawn a packet along the station spline for `JobId` |
| `gate.flare` | gate flare on `JobId` (red when `Severity=="error"`) |
| `ladder.streak` | Brain-Ladder streak (tier from `Label`) |
| `owner/agent/skill/system/audit.*` | ambient bloom keyed to `Severity` |

Honesty: render `OnAction` events only; on `OnSnapshot(bOk=false)` / actions 503,
show the dormant dressing — never fabricated activity (module rule, TDD §2.4).

## 3. Desktop wallpaper window (behind the icons)

Render the Observatory map as the desktop background:

- **Launch** the Observatory map borderless + the actions stream auto-started:
  `Synapse.exe ObservatoryMap -WINDOWED -ResX=<w> -ResY=<h> -ConsoleVariables="muse.AutoStartActions=1"`.
- **Borderless, behind icons (Windows):** after the window exists, reparent its
  `HWND` to the `WorkerW` window that sits behind the desktop icons (the standard
  desktop-background technique): send `0x052C` to `Progman`, enumerate to find the
  `WorkerW` after the `SHELLDLL_DefView`, then `SetParent(UeHwnd, WorkerW)`. Do this
  in a tiny platform helper in `SynapseCore` (Windows-only `#if PLATFORM_WINDOWS`),
  invoked once on map load. On macOS/Linux, fall back to a borderless, always-on-
  bottom, click-through window (Slate `WindowMode=Windowed`, `bIsTopmost=false`,
  desktop-level Z-order via the platform window API).
- **Power:** drop to ~30 fps and pause Niagara when the desktop is occluded
  (no foreground compositor activity); the actions SSE keeps its own backoff.

## 4. Verify (owner rig)

1. Build the editor target; play the Observatory map with the gateway paired and
   `MUSE_OBSERVATORY=1`.
2. Trigger work (orchestrated job, a skill, a gate) and confirm `OnAction` fires
   and the matching VFX plays; confirm dormant dressing when the collector is off.
3. Package, reparent to `WorkerW`, and confirm the map renders behind the desktop
   icons and keeps reacting to live actions.

## Owner gate

The desktop-background reparenting + any always-on render process is an
outward-facing, resource-using surface — it sits under the same owner-gated
native/streaming pivot as the rest of `apps/synapse-ue`
(`docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md`). Land behind a
draft PR; the owner authorizes the merge.
