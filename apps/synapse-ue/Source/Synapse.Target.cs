// SYNAPSE — game target (Win64 first; UE 5.6 pinned).
// Copyright A-C-I Software & Development. All rights reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class SynapseTarget : TargetRules
{
	public SynapseTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.AddRange(new string[]
		{
			"SynapseCore",
			"SynapseNet",
			"SynapseObservatory",
			"SynapseObservatoryRender",
		});
	}
}
