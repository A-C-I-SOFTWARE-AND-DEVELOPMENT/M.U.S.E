// UmuseGatewayClient — the gateway handshake client (GameInstance subsystem).
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Interfaces/IHttpRequest.h"
#include "museGatewayClient.generated.h"

/**
 * Broadcast on the game thread after GET /v1/health completes.
 * bOk = transport succeeded AND HTTP 2xx AND (when parseable) "ok": true.
 * RawJson = the verbatim response body (empty on transport failure).
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnGatewayHealth, bool, bOk, const FString&, RawJson);

/**
 * Broadcast on the game thread after GET /v1/cockpit/capabilities completes
 * with HTTP 2xx. RawJson = the verbatim capabilities document
 * ({api_version, gateway_version, subsystems, available_workers,
 *   detected_clis, execute_allowed, owner_gate_required, generated_at}
 * per cockpit-wire-contract.md). The client negotiates against this,
 * it never assumes (TDD §2.2).
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCapabilities, const FString&, RawJson);

/**
 * The only code in the project that talks to a muse gateway (TDD §2.2).
 *
 * Prompt 0 scope: the Phase 0 handshake —
 *   GET /v1/health                   (open route; liveness + version)
 *   GET /v1/cockpit/capabilities     (bearer route; feature negotiation)
 *
 * Contract routes implemented (greppable per TDD §2.2):
 *   GET /v1/health                 — cockpit-wire-contract.md, auth: open
 *   GET /v1/cockpit/capabilities   — cockpit-wire-contract.md, auth: bearer
 *
 * Threading: requests are issued via FHttpModule (completion arrives on a
 * worker thread); ALL delegate broadcasts are marshaled to the game thread
 * via AsyncTask(ENamedThreads::GameThread, …). No network work ever runs
 * on the game thread.
 *
 * Security: the bearer token is read from the token file at call time
 * (UmuseGatewaySettings::ReadBearerToken) and set straight into the
 * Authorization header. It is never stored on this object, never logged —
 * log lines that reference auth state use a redaction marker.
 */
UCLASS()
class SYNAPSENET_API UmuseGatewayClient : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	//~ Begin USubsystem
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	//~ End USubsystem

	/** GET /v1/health (open route). Broadcasts OnGatewayHealth on the game
	 *  thread. Safe to call before pairing — no token required. */
	UFUNCTION(BlueprintCallable, Category = "muse|Gateway")
	void CheckHealth();

	/** GET /v1/cockpit/capabilities with `Authorization: Bearer <token>`.
	 *  Broadcasts OnCapabilities (2xx) or OnGatewayHealth(false, body) on
	 *  auth/transport failure, on the game thread. */
	UFUNCTION(BlueprintCallable, Category = "muse|Gateway")
	void FetchCapabilities();

	/** Build a bearer-authorized GET request for <GatewayBaseUrl><Path>,
	 *  using the exact same config/token handling as the handshake calls
	 *  (token read fresh from the token file at call time, never stored,
	 *  never logged). Additive accessor for downstream consumers
	 *  (SynapseObservatory's /v1/observatory/* fetches) so token handling
	 *  stays in exactly one module (TDD §2.2/§8). The caller binds
	 *  OnProcessRequestComplete (which fires on an HTTP WORKER thread —
	 *  marshal to the game thread before broadcasting) and calls
	 *  ProcessRequest(). C++-only; not a UFUNCTION. */
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> CreateAuthorizedGetRequest(const FString& Path) const;

	/** Build a bearer-authorized JSON request while keeping token access inside
	 *  SynapseNet. Body is never logged. Downstream authoritative clients use
	 *  this for POST/PUT/PATCH without reading or storing credential material. */
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> CreateAuthorizedJsonRequest(
		const FString& Path,
		const FString& Verb,
		const FString& Body = FString()) const;

	/** Fired for health results (and capabilities failures). Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Gateway")
	FOnGatewayHealth OnGatewayHealth;

	/** Fired with the raw capabilities JSON on success. Game thread. */
	UPROPERTY(BlueprintAssignable, Category = "muse|Gateway")
	FOnCapabilities OnCapabilities;

private:
	/** Build a GET request for <GatewayBaseUrl><Path>, with timeout and,
	 *  when bWithAuth, the Authorization header (token read fresh from the
	 *  token file; never logged). */
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> MakeGetRequest(const FString& Path, bool bWithAuth) const;

	/** Join base URL + path without double slashes. */
	static FString BuildUrl(const FString& BaseUrl, const FString& Path);
};
