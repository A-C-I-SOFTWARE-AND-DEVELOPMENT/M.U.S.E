// SYNAPSE — editor target (UE 5.6 pinned).
// Copyright A-C-I Software & Development. All rights reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class SynapseEditorTarget : TargetRules
{
	public SynapseEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
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
