// UMuseSseClient implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "MuseSseClient.h"

#include "Async/Async.h"
#include "HttpModule.h"
#include "Interfaces/IHttpResponse.h"
#include "MuseGatewaySettings.h"
#include "SynapseNet.h"

namespace
{
	constexpr float GSseBackoffInitialSeconds = 1.0f;
	constexpr float GSseBackoffCapSeconds = 30.0f;

	FString JoinUrl(const FString& BaseUrl, const FString& Path)
	{
		FString Trimmed = BaseUrl;
		while (Trimmed.EndsWith(TEXT("/")))
		{
			Trimmed.LeftChopInline(1);
		}
		return Path.StartsWith(TEXT("/")) ? Trimmed + Path : Trimmed + TEXT("/") + Path;
	}
}

void UMuseSseClient::Start(const FString& Path)
{
	check(IsInGameThread());

	Stop();

	StreamPath = Path;
	bWantStream = true;
	BackoffSeconds = GSseBackoffInitialSeconds;
	Connect();
}

void UMuseSseClient::Stop()
{
	bWantStream = false;
	CancelReconnect();

	if (ActiveRequest.IsValid())
	{
		// CancelRequest fires the completion handler with bConnected=false;
		// the handler checks bWantStream before reconnecting, so this is a
		// clean stop.
		ActiveRequest->CancelRequest();
		ActiveRequest.Reset();
	}

	PendingBuffer.Reset();
	ParsedChars = 0;
}

void UMuseSseClient::BeginDestroy()
{
	Stop();
	Super::BeginDestroy();
}

void UMuseSseClient::Connect()
{
	if (!bWantStream)
	{
		return;
	}

	const UMuseGatewaySettings* Settings = GetDefault<UMuseGatewaySettings>();

	PendingBuffer.Reset();
	ParsedChars = 0;

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	Request->SetVerb(TEXT("GET"));
	Request->SetURL(JoinUrl(Settings->GatewayBaseUrl, StreamPath));
	Request->SetHeader(TEXT("Accept"), TEXT("text/event-stream"));
	Request->SetHeader(TEXT("Cache-Control"), TEXT("no-cache"));
	// Deliberately NO SetTimeout(): a healthy SSE stream is long-lived. Dead
	// links surface through the completion handler -> backoff reconnect.

	// Streaming routes are bearer-auth on the gateway. Token is read fresh
	// from disk, lives only in the header, and is never logged (TDD §8).
	const FString Token = Settings->ReadBearerToken();
	if (!Token.IsEmpty())
	{
		Request->SetHeader(TEXT("Authorization"), FString::Printf(TEXT("Bearer %s"), *Token));
	}
	else
	{
		UE_LOG(LogSynapseNet, Warning,
			TEXT("SSE %s starting without bearer token (file: %s) — expect 401."),
			*StreamPath, *Settings->ResolveTokenFilePath());
	}

	TWeakObjectPtr<UMuseSseClient> WeakThis(this);

	// Progress fires on an HTTP worker thread as bytes arrive. We snapshot
	// the body-so-far and marshal it; all parsing/state lives game-side.
	Request->OnRequestProgress64().BindLambda(
		[WeakThis](FHttpRequestPtr InRequest, uint64 /*BytesSent*/, uint64 /*BytesReceived*/)
		{
			FHttpResponsePtr Response = InRequest.IsValid() ? InRequest->GetResponse() : nullptr;
			if (!Response.IsValid())
			{
				return;
			}
			const FString ContentSoFar = Response->GetContentAsString();
			AsyncTask(ENamedThreads::GameThread, [WeakThis, ContentSoFar]()
			{
				if (UMuseSseClient* Self = WeakThis.Get())
				{
					Self->ConsumeContent(ContentSoFar);
				}
			});
		});

	Request->OnProcessRequestComplete().BindLambda(
		[WeakThis](FHttpRequestPtr /*InRequest*/, FHttpResponsePtr Response, bool bConnected)
		{
			const int32 Code = (bConnected && Response.IsValid()) ? Response->GetResponseCode() : 0;
			AsyncTask(ENamedThreads::GameThread, [WeakThis, Code]()
			{
				UMuseSseClient* Self = WeakThis.Get();
				if (!Self)
				{
					return;
				}
				Self->ActiveRequest.Reset();
				if (Self->bWantStream)
				{
					UE_LOG(LogSynapseNet, Warning,
						TEXT("SSE %s disconnected (HTTP %d) — reconnecting in %.1fs."),
						*Self->StreamPath, Code, Self->BackoffSeconds);
					Self->ScheduleReconnect();
				}
			});
		});

	ActiveRequest = Request;
	Request->ProcessRequest();

	UE_LOG(LogSynapseNet, Log, TEXT("SSE stream opening: %s"), *StreamPath);
}

void UMuseSseClient::ConsumeContent(const FString& FullContent)
{
	check(IsInGameThread());

	if (!bWantStream || FullContent.Len() <= ParsedChars)
	{
		return;
	}

	PendingBuffer += FullContent.Mid(ParsedChars);
	ParsedChars = FullContent.Len();

	// Normalize CRLF so the frame boundary is always "\n\n". (A CRLF pair
	// split across two deltas is tolerated: the remainder is re-scanned on
	// the next delta.)
	PendingBuffer.ReplaceInline(TEXT("\r\n"), TEXT("\n"));

	int32 BoundaryIndex = INDEX_NONE;
	while ((BoundaryIndex = PendingBuffer.Find(TEXT("\n\n"))) != INDEX_NONE)
	{
		const FString Frame = PendingBuffer.Left(BoundaryIndex);
		PendingBuffer.MidInline(BoundaryIndex + 2);
		if (!Frame.TrimStartAndEnd().IsEmpty())
		{
			DispatchFrame(Frame);
		}
	}
}

void UMuseSseClient::DispatchFrame(const FString& Frame)
{
	FString EventType = TEXT("message");
	TArray<FString> DataLines;

	TArray<FString> Lines;
	Frame.ParseIntoArrayLines(Lines, /*bCullEmpty=*/false);
	for (const FString& Line : Lines)
	{
		if (Line.StartsWith(TEXT(":")))
		{
			continue; // SSE comment / keep-alive.
		}
		if (Line.StartsWith(TEXT("event:")))
		{
			EventType = Line.Mid(6).TrimStartAndEnd();
		}
		else if (Line.StartsWith(TEXT("data:")))
		{
			FString Data = Line.Mid(5);
			Data.RemoveFromStart(TEXT(" "));
			DataLines.Add(MoveTemp(Data));
		}
		// `id:` and `retry:` are accepted but unused in Prompt 0; the
		// Last-Event-ID resume + retry-hint honoring land in Phase 1
		// (TDD §2.2, 10-observatory-spec.md §3.2).
	}

	if (DataLines.Num() == 0 && EventType == TEXT("message"))
	{
		return; // Nothing actionable in this frame.
	}

	// A successfully parsed frame proves the link is healthy: reset backoff.
	BackoffSeconds = GSseBackoffInitialSeconds;

	OnSseEvent.Broadcast(EventType, FString::Join(DataLines, TEXT("\n")));
}

void UMuseSseClient::ScheduleReconnect()
{
	check(IsInGameThread());
	CancelReconnect();

	ReconnectHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateWeakLambda(this, [this](float /*DeltaTime*/)
		{
			ReconnectHandle.Reset();
			Connect();
			return false; // One-shot.
		}),
		BackoffSeconds);

	BackoffSeconds = FMath::Min(BackoffSeconds * 2.0f, GSseBackoffCapSeconds);
}

void UMuseSseClient::CancelReconnect()
{
	if (ReconnectHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(ReconnectHandle);
		ReconnectHandle.Reset();
	}
}
