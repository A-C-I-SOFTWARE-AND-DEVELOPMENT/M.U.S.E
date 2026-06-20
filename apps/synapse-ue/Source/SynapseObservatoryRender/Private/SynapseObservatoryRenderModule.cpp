// SynapseObservatoryRender module implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "SynapseObservatoryRender.h"

DEFINE_LOG_CATEGORY(LogSynapseObservatoryRender);

void FSynapseObservatoryRenderModule::StartupModule()
{
	UE_LOG(LogSynapseObservatoryRender, Log, TEXT("SynapseObservatoryRender module started."));
}

void FSynapseObservatoryRenderModule::ShutdownModule()
{
	UE_LOG(LogSynapseObservatoryRender, Log, TEXT("SynapseObservatoryRender module shut down."));
}

IMPLEMENT_MODULE(FSynapseObservatoryRenderModule, SynapseObservatoryRender)
