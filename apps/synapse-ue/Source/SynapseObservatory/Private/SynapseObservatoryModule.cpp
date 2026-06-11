// SynapseObservatory module implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "SynapseObservatory.h"

DEFINE_LOG_CATEGORY(LogSynapseObservatory);

void FSynapseObservatoryModule::StartupModule()
{
	UE_LOG(LogSynapseObservatory, Log, TEXT("SynapseObservatory module started."));
}

void FSynapseObservatoryModule::ShutdownModule()
{
	UE_LOG(LogSynapseObservatory, Log, TEXT("SynapseObservatory module shut down."));
}

IMPLEMENT_MODULE(FSynapseObservatoryModule, SynapseObservatory)
