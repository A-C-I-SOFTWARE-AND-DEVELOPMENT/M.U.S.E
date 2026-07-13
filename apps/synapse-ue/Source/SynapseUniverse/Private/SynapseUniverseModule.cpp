#include "SynapseUniverse.h"

DEFINE_LOG_CATEGORY(LogSynapseUniverse);

void FSynapseUniverseModule::StartupModule()
{
	UE_LOG(LogSynapseUniverse, Log,
		TEXT("SynapseUniverse ready (muse-universe schema major 1, metric source units)."));
}

void FSynapseUniverseModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FSynapseUniverseModule, SynapseUniverse)

