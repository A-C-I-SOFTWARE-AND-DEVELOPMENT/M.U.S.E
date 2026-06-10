// SynapseCore — project-wide types, save/settings/consent home (TDD §2.1).
// House rule: our modules compile with warnings-as-errors (master plan
// Prompt 0 constraint). We are a game module (not an engine module), so
// bWarningsAsErrors applies cleanly; CppStandard stays at the 5.6 default.

using UnrealBuildTool;

public class SynapseCore : ModuleRules
{
	public SynapseCore(ReadOnlyTargetRules Target) : base(Target)
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
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });
	}
}
