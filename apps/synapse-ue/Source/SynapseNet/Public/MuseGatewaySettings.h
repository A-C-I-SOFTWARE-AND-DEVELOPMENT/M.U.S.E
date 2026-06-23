// muse gateway connection settings (UDeveloperSettings, config-backed).
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "museGatewaySettings.generated.h"

/**
 * Connection settings for the paired muse gateway (tier 3 of the brain
 * ladder; TDD §1, §2.2).
 *
 * SECURITY RULE (binding, master plan Prompt 0 + TDD §8):
 *  - The bearer token is NEVER a config/UPROPERTY default, never compiled
 *    into the binary, never serialized into saves, and NEVER logged.
 *  - Prompt 0 reads it from a plain local file (default:
 *    <ProjectSavedDir>/muse_token.txt — outside source control; Saved/ is
 *    gitignored and the filename is belt-and-braces ignored too).
 *  - Phase 1 upgrades this to the DPAPI/Keystore-wrapped encrypted config
 *    (Saved/Config/muse_pairing.bin) populated by the pairing flow
 *    (POST /v1/cockpit/pair/start -> /v1/cockpit/pair/confirm).
 *  - Anything that must mention the token in a log line logs a redaction
 *    marker, never the value (see UmuseGatewayClient).
 */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "muse Gateway"))
class SYNAPSENET_API UmuseGatewaySettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UmuseGatewaySettings()
	{
		CategoryName = TEXT("Project");
		SectionName = TEXT("muse Gateway");
		GatewayBaseUrl = TEXT("http://127.0.0.1:8787");
		TokenFilePath = TEXT("muse_token.txt");
	}

	/** Base URL of the paired muse gateway. Loopback/RFC1918 plain HTTP is
	 *  acceptable for the local pairing case only; remote tiers are TLS-only
	 *  (TDD §8). No trailing slash required. */
	UPROPERTY(Config, EditAnywhere, Category = "Gateway")
	FString GatewayBaseUrl;

	/** Path to the bearer-token file. Relative paths resolve under
	 *  <ProjectSavedDir>. The file holds the raw token (whitespace
	 *  trimmed) and nothing else. The token itself is read at runtime by
	 *  ReadBearerToken() — by design there is NO token UPROPERTY. */
	UPROPERTY(Config, EditAnywhere, Category = "Gateway")
	FString TokenFilePath;

	/** Absolute path the token will be read from. Safe to log. */
	FString ResolveTokenFilePath() const
	{
		if (FPaths::IsRelative(TokenFilePath))
		{
			return FPaths::Combine(FPaths::ProjectSavedDir(), TokenFilePath);
		}
		return TokenFilePath;
	}

	/** Read the bearer token from disk, fresh, at call time. Returns an
	 *  empty string when the file is missing/empty. Callers must never log
	 *  the returned value. */
	FString ReadBearerToken() const
	{
		FString Token;
		if (FFileHelper::LoadFileToString(Token, *ResolveTokenFilePath()))
		{
			Token.TrimStartAndEndInline();
			return Token;
		}
		return FString();
	}
};
