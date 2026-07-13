// UmuseGatewayClient implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "museGatewayClient.h"

#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "museGatewaySettings.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "SynapseNet.h"

namespace
{
	constexpr float GmuseRequestTimeoutSeconds = 15.0f;

	/** Marker used in place of any token material in log output. */
	const TCHAR* GRedacted = TEXT("<redacted>");

	/** True when the body parses as JSON and carries `"ok": true`
	 *  (the /v1/health shape per cockpit-wire-contract.md). A body that
	 *  is not parseable JSON does not veto an HTTP 2xx. */
	bool BodyReportsOk(const FString& Body)
	{
		TSharedPtr<FJsonObject> Json;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Body);
		if (FJsonSerializer::Deserialize(Reader, Json) && Json.IsValid())
		{
			bool bOkField = false;
			if (Json->TryGetBoolField(TEXT("ok"), bOkField))
			{
				return bOkField;
			}
		}
		return true;
	}
}

void UmuseGatewayClient::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	const UmuseGatewaySettings* Settings = GetDefault<UmuseGatewaySettings>();
	UE_LOG(LogSynapseNet, Log,
		TEXT("museGatewayClient ready. Gateway=%s TokenFile=%s Token=%s"),
		*Settings->GatewayBaseUrl,
		*Settings->ResolveTokenFilePath(),
		GRedacted);
}

void UmuseGatewayClient::Deinitialize()
{
	OnGatewayHealth.Clear();
	OnCapabilities.Clear();
	Super::Deinitialize();
}

FString UmuseGatewayClient::BuildUrl(const FString& BaseUrl, const FString& Path)
{
	FString Trimmed = BaseUrl;
	while (Trimmed.EndsWith(TEXT("/")))
	{
		Trimmed.LeftChopInline(1);
	}
	return Path.StartsWith(TEXT("/")) ? Trimmed + Path : Trimmed + TEXT("/") + Path;
}

TSharedRef<IHttpRequest, ESPMode::ThreadSafe> UmuseGatewayClient::MakeGetRequest(const FString& Path, bool bWithAuth) const
{
	const UmuseGatewaySettings* Settings = GetDefault<UmuseGatewaySettings>();

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetVerb(TEXT("GET"));
	Request->SetURL(BuildUrl(Settings->GatewayBaseUrl, Path));
	Request->SetTimeout(GmuseRequestTimeoutSeconds);
	Request->SetHeader(TEXT("Accept"), TEXT("application/json"));

	if (bWithAuth)
	{
		// Token is read fresh from disk at call time and lives only in the
		// request header. NEVER log the value (TDD §8 / Prompt 0 rule).
		const FString Token = Settings->ReadBearerToken();
		if (Token.IsEmpty())
		{
			UE_LOG(LogSynapseNet, Warning,
				TEXT("No bearer token found at %s — %s will be sent unauthenticated and should 401."),
				*Settings->ResolveTokenFilePath(), *Path);
		}
		else
		{
			Request->SetHeader(TEXT("Authorization"), FString::Printf(TEXT("Bearer %s"), *Token));
			UE_LOG(LogSynapseNet, Verbose, TEXT("Authorization: Bearer %s attached for %s"), GRedacted, *Path);
		}
	}

	return Request;
}

TSharedRef<IHttpRequest, ESPMode::ThreadSafe> UmuseGatewayClient::CreateAuthorizedGetRequest(const FString& Path) const
{
	// Thin public wrapper over the private factory: one place builds
	// authorized requests; consumers never touch the token file themselves.
	return CreateAuthorizedJsonRequest(Path, TEXT("GET"));
}

TSharedRef<IHttpRequest, ESPMode::ThreadSafe> UmuseGatewayClient::CreateAuthorizedJsonRequest(
	const FString& Path,
	const FString& Verb,
	const FString& Body) const
{
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
		MakeGetRequest(Path, /*bWithAuth=*/true);
	Request->SetVerb(Verb.IsEmpty() ? TEXT("GET") : Verb.ToUpper());
	Request->SetHeader(TEXT("Accept"), TEXT("application/json"));
	if (!Body.IsEmpty())
	{
		Request->SetHeader(TEXT("Content-Type"), TEXT("application/json; charset=utf-8"));
		Request->SetContentAsString(Body);
	}
	return Request;
}

void UmuseGatewayClient::CheckHealth()
{
	// Contract route: GET /v1/health — open (no bearer), liveness + version.
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = MakeGetRequest(TEXT("/v1/health"), /*bWithAuth=*/false);

	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis = TWeakObjectPtr<UmuseGatewayClient>(this)](FHttpRequestPtr /*Req*/, FHttpResponsePtr Response, bool bConnected)
		{
			// Completion arrives on an HTTP worker thread — compute here,
			// broadcast on the game thread.
			const int32 Code = (bConnected && Response.IsValid()) ? Response->GetResponseCode() : 0;
			const FString Body = (bConnected && Response.IsValid()) ? Response->GetContentAsString() : FString();
			const bool bOk = EHttpResponseCodes::IsOk(Code) && BodyReportsOk(Body);

			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Body]()
			{
				if (UmuseGatewayClient* Self = WeakThis.Get())
				{
					UE_LOG(LogSynapseNet, Log, TEXT("/v1/health -> HTTP %d ok=%s"), Code, bOk ? TEXT("true") : TEXT("false"));
					Self->OnGatewayHealth.Broadcast(bOk, Body);
				}
			});
		});

	Request->ProcessRequest();
}

void UmuseGatewayClient::FetchCapabilities()
{
	// Contract route: GET /v1/cockpit/capabilities — bearer auth required.
	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = MakeGetRequest(TEXT("/v1/cockpit/capabilities"), /*bWithAuth=*/true);

	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis = TWeakObjectPtr<UmuseGatewayClient>(this)](FHttpRequestPtr /*Req*/, FHttpResponsePtr Response, bool bConnected)
		{
			const int32 Code = (bConnected && Response.IsValid()) ? Response->GetResponseCode() : 0;
			const FString Body = (bConnected && Response.IsValid()) ? Response->GetContentAsString() : FString();
			const bool bOk = EHttpResponseCodes::IsOk(Code);

			AsyncTask(ENamedThreads::GameThread, [WeakThis, bOk, Code, Body]()
			{
				UmuseGatewayClient* Self = WeakThis.Get();
				if (!Self)
				{
					return;
				}
				if (bOk)
				{
					UE_LOG(LogSynapseNet, Log, TEXT("/v1/cockpit/capabilities -> HTTP %d (%d bytes)"), Code, Body.Len());
					Self->OnCapabilities.Broadcast(Body);
				}
				else
				{
					// 401 here means: not paired / token file missing or stale.
					UE_LOG(LogSynapseNet, Warning, TEXT("/v1/cockpit/capabilities -> HTTP %d. Check pairing + token file."), Code);
					Self->OnGatewayHealth.Broadcast(false, Body);
				}
			});
		});

	Request->ProcessRequest();
}
