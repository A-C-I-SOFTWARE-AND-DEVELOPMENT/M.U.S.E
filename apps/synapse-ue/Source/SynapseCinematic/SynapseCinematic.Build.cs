// SynapseCinematic — native two-camera stereo and deterministic MRQ manifests.

using UnrealBuildTool;

public class SynapseCinematic : ModuleRules
{
	public SynapseCinematic(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bWarningsAsErrors = true;
		bEnableExceptions = false;
		CppStandard = CppStandardVersion.Cpp20;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"CinematicCamera",
			"LevelSequence",
			"MovieScene",
			"SynapseUniverse",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Json",
			"JsonUtilities",
			"MovieRenderPipelineCore",
		});
	}
}

