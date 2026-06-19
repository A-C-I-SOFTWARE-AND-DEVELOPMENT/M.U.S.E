// UmuseSseClient — minimal Server-Sent Events consumer over FHttpModule.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "Containers/Ticker.h"
#include "CoreMinimal.h"
#include "Interfaces/IHttpRequest.h"
#include "UObject/Object.h"
#include "museSseClient.generated.h"

/**
 * Broadcast on the game thread for every complete SSE frame.
 * EventType = the `event:` field (defaults to "message" when absent).
 * Data      = the joined `data:` lines (newline-separated when multi-line).
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnSseEvent, const FString&, EventType, const FString&, Data);

/**
 * Minimal SSE consumer for the gateway's streaming routes
 * (`GET /v1/cockpit/events/stream`, `GET /v1/cockpit/jobs/stream`, and the
 * future additive `/v1/observatory/stream` family).
 *
 * CONSUMER NOTE: SynapseObservatory consumes this client at Phase 3 for the
 * live galaxy/pipeline deltas (TDD §2.4, 10-observatory-spec.md §3.2). It
 * stays here in SynapseNet because this module is the only gateway talker.
 *
 * Mechanics:
 *  - Starts a streamed FHttpRequest with `Accept: text/event-stream` and
 *    bearer auth (token read fresh from the settings token file).
 *  - Accumulates OnRequestProgress64 deltas, splits the byte stream on
 *    blank lines ("\n\n" frame boundary), parses `event:` / `data:` lines
 *    (`:` comments ignored; `id:`/`retry:` accepted and currently ignored —
 *    Last-Event-ID resume is Phase 1 work).
 *  - Broadcasts FOnSseEvent on the GAME THREAD only; progress callbacks
 *    arrive on HTTP worker threads and are marshaled via AsyncTask.
 *  - Reconnects with exponential backoff 1s -> 2s -> 4s -> … capped at 30s
 *    (Prompt 0 scope; the full TDD §2.2 policy adds jitter + 60s cap),
 *    reset to 1s once a frame is successfully received.
 *  - Stop() cancels the in-flight request and any pending reconnect.
 */
UCLASS(BlueprintType)
class SYNAPSENET_API UmuseSseClient : public UObject
{
	GENERATED_BODY()

public:
	/** Begin streaming <GatewayBaseUrl><Path> (e.g. "/v1/observatory/stream").
	 *  Idempotent: a second Start() restarts on the new path. */
	UFUNCTION(BlueprintCallable, Category = "muse|SSE")
	void Start(const FString& Path);

	/** Stop streaming: cancels the request and pending reconnects. */
	UFUNCTION(BlueprintCallable, Category = "muse|SSE")
	void Stop();

	/** True between Start() and Stop() (regardless of connection health). */
	UFUNCTION(BlueprintPure, Category = "muse|SSE")
	bool IsStreaming() const { return bWantStream; }

	/** Per-frame SSE events. Always broadcast on the game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|SSE")
	FOnSseEvent OnSseEvent;

	//~ Begin UObject
	virtual void BeginDestroy() override;
	//~ End UObject

private:
	/** Open (or re-open) the streamed request. Game thread. */
	void Connect();

	/** Game thread: consume the not-yet-parsed tail of the body, split into
	 *  frames, dispatch. */
	void ConsumeContent(const FString& FullContent);

	/** Parse one frame's `event:`/`data:` lines and broadcast. Game thread. */
	void DispatchFrame(const FString& Frame);

	/** Schedule a Connect() after the current backoff delay. Game thread. */
	void ScheduleReconnect();

	/** Cancel any scheduled reconnect tick. */
	void CancelReconnect();

	/** The in-flight streamed request (game-thread owned). */
	FHttpRequestPtr ActiveRequest;

	/** Path on the configured gateway being streamed. */
	FString StreamPath;

	/** Unparsed remainder after the last complete frame. */
	FString PendingBuffer;

	/** Characters of the response body already consumed. */
	int32 ParsedChars = 0;

	/** Current reconnect delay; doubles per failure, capped. */
	float BackoffSeconds = 1.0f;

	/** Owner intent: true between Start() and Stop(). */
	bool bWantStream = false;

	/** Pending reconnect ticker (core ticker runs on the game thread). */
	FTSTicker::FDelegateHandle ReconnectHandle;
};
