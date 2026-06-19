// SynapseObservatoryRender module interface — the Phase-3 galaxy render layer.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/** Log category for everything in SynapseObservatoryRender. */
SYNAPSEOBSERVATORYRENDER_API DECLARE_LOG_CATEGORY_EXTERN(LogSynapseObservatoryRender, Log, All);

/**
 * SynapseObservatoryRender — the galaxy ISM renderer + sacred-geometry layouts
 * that bind to UObservatorySubsystem (data plane). No network, no policy beyond
 * rendering; positions come from the gateway and/or the closed-form generators
 * in SynapseCore's MuseSacredGeometry.
 */
class FSynapseObservatoryRenderModule : public IModuleInterface
{
public:
	//~ Begin IModuleInterface
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	//~ End IModuleInterface
};
