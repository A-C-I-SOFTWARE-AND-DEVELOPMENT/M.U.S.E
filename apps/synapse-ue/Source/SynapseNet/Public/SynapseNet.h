// SynapseNet module interface.
// Copyright A-C-I Software & Development. All rights reserved.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/** Log category for the gateway client / SSE consumer. Token values are
 *  NEVER written to this (or any) log — see museGatewaySettings.h. */
SYNAPSENET_API DECLARE_LOG_CATEGORY_EXTERN(LogSynapseNet, Log, All);

/** SynapseNet — HTTP/SSE wire-contract client module (TDD §2.2). */
class FSynapseNetModule : public IModuleInterface
{
public:
	//~ Begin IModuleInterface
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
	//~ End IModuleInterface
};
