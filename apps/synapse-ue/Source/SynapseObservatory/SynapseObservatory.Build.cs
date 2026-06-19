// SynapseObservatory — the Neural Observatory map module (TDD §2.4):
// typed client surface for the additive read-only /v1/observatory/* route
// family (10-observatory-spec.md §3). Holds NO policy logic — every number
// rendered arrives fully formed from the gateway. All gateway traffic goes
// through SynapseNet (the only module that talks to a muse gateway).

using UnrealBuildTool;

public class SynapseObservatory : ModuleRules
{
	public SynapseObservatory(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Quality bar: zero warnings tolerated in Synapse* modules.
		bWarningsAsErrors = true;

		// Keep the engine defaults explicit: no C++ exceptions in game code.
		bEnableExceptions = false;

		// SynapseNet is PUBLIC: ObservatorySubsystem.h forward-declares
		// UmuseSseClient, and consumers of this module (SynapseUI, the
		// future galaxy renderer) reach the gateway through us.
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"SynapseCore",
			"SynapseNet",
		});

		// HTTP/Json stay PRIVATE: no public header of this module exposes
		// FHttpRequestPtr or FJsonObject — parsing is an implementation
		// detail of ObservatorySubsystem.cpp.
		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"HTTP",
			"Json",
			"JsonUtilities",
		});
	}
}
