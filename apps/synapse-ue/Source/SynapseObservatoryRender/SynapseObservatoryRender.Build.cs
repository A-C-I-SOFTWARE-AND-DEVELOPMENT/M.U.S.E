// SynapseObservatoryRender — the Phase-3 galaxy render layer (TDD §2.4): binds
// to UObservatorySubsystem's delegates and arranges the gateway-supplied
// clusters/members onto closed-form sacred-geometry frameworks (MuseSacredGeometry
// in SynapseCore). Holds the *render* policy the data-plane module deliberately
// does not: ISM node field, spline/Niagara flows, gate-verdict visuals. It runs
// no network and no force-directed physics — only closed-form placement + a
// per-tick 4D rotation for polytope frameworks.

using UnrealBuildTool;

public class SynapseObservatoryRender : ModuleRules
{
	public SynapseObservatoryRender(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Quality bar: zero warnings tolerated in Synapse* modules.
		bWarningsAsErrors = true;

		// Keep the engine defaults explicit: no C++ exceptions in game code.
		bEnableExceptions = false;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"SynapseCore",          // MuseSacredGeometry generators
			"SynapseObservatory",   // ObservatoryTypes + UObservatorySubsystem
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"DeveloperSettings",    // UObservatoryRenderSettings (Project Settings)
			"Niagara",              // flow particles (assets owner-authored, optional)
		});
	}
}
