// SynapseNet module implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "SynapseNet.h"

DEFINE_LOG_CATEGORY(LogSynapseNet);

void FSynapseNetModule::StartupModule()
{
	UE_LOG(LogSynapseNet, Log, TEXT("SynapseNet module started."));
}

void FSynapseNetModule::ShutdownModule()
{
	UE_LOG(LogSynapseNet, Log, TEXT("SynapseNet module shut down."));
}

IMPLEMENT_MODULE(FSynapseNetModule, SynapseNet)
