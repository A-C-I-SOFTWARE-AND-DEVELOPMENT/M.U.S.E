// SynapseObservatory module interface — the Neural Observatory map module.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/** Log category for everything in SynapseObservatory. */
SYNAPSEOBSERVATORY_API DECLARE_LOG_CATEGORY_EXTERN(LogSynapseObservatory, Log, All);

/**
 * SynapseObservatory — the Neural Observatory map module (TDD §2.4,
 * 10-observatory-spec.md). This drop ships the data plane only:
 * the typed /v1/observatory/* client (UObservatorySubsystem +
 * ObservatoryTypes.h). The galaxy ISM renderer, station-spline Niagara
 * packets, Brain Ladder strata, and the owner-edit interaction grammar
 * are Phase 3 work that binds to this subsystem's delegates.
 *
 * Module position in the dependency chain (TDD §2):
 *   SynapseUI -> {SynapseObservatory, FoundryClient, Agents} -> SynapseNet -> SynapseCore
 */
class FSynapseObservatoryModule : public IModuleInterface
{
public:
	//~ Begin IModuleInterface
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	//~ End IModuleInterface
};
