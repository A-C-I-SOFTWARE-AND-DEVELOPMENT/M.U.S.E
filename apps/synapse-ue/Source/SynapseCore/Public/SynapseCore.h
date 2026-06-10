// SynapseCore module interface — project-wide foundation module.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/** Log category for everything in SynapseCore. */
SYNAPSECORE_API DECLARE_LOG_CATEGORY_EXTERN(LogSynapseCore, Log, All);

/**
 * SynapseCore — the bottom of the module dependency chain
 * (SynapseUI -> {Observatory, FoundryClient, Agents} -> Net -> Core,
 * per docs/synapse/design/11-technical-design.md §2).
 *
 * Future homes (Phase 1+): USynapseSaveSubsystem, USynapseSettings,
 * USynapseConsentSubsystem, FSynapseVersion, currency/zone/domain types.
 * Prompt 0 ships only the module boilerplate.
 */
class FSynapseCoreModule : public IModuleInterface
{
public:
	//~ Begin IModuleInterface
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	//~ End IModuleInterface
};
