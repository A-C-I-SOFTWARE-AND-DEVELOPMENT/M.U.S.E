// SynapseNet — the ONLY module in the project that talks to a MUSE gateway
// (TDD §2.2). HTTP/SSE client over the frozen cockpit wire contract
// (docs/contracts/cockpit-wire-contract.md in the M.U.S.E repo).

using UnrealBuildTool;

public class SynapseNet : ModuleRules
{
	public SynapseNet(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Quality bar: zero warnings tolerated in Synapse* modules.
		bWarningsAsErrors = true;

		// Keep the engine defaults explicit: no C++ exceptions in game code.
		bEnableExceptions = false;

		// HTTP + DeveloperSettings are PUBLIC because our public headers
		// (MuseGatewayClient.h / MuseSseClient.h / MuseGatewaySettings.h)
		// expose FHttpRequestPtr members and a UDeveloperSettings base —
		// downstream modules (SynapseObservatory, …) include those headers.
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"SynapseCore",
			"HTTP",
			"DeveloperSettings",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Json",
			"JsonUtilities",
		});
	}
}
