// SynapseCore module implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "SynapseCore.h"

DEFINE_LOG_CATEGORY(LogSynapseCore);

void FSynapseCoreModule::StartupModule()
{
	UE_LOG(LogSynapseCore, Log, TEXT("SynapseCore module started."));
}

void FSynapseCoreModule::ShutdownModule()
{
	UE_LOG(LogSynapseCore, Log, TEXT("SynapseCore module shut down."));
}

IMPLEMENT_MODULE(FSynapseCoreModule, SynapseCore)
