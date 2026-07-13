// SynapseUniverse — authoritative M.U.S.E. universe projection client and
// metric Atlas Crown / agent-vessel runtime. Policy remains server-side.

using UnrealBuildTool;

public class SynapseUniverse : ModuleRules
{
	public SynapseUniverse(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bWarningsAsErrors = true;
		bEnableExceptions = false;
		CppStandard = CppStandardVersion.Cpp17;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"DeveloperSettings",
			"SynapseCore",
			"SynapseNet",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"HTTP",
			"Json",
			"JsonUtilities",
		});
	}
}
