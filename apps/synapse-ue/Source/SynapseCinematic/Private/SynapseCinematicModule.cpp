#include "SynapseCinematic.h"

DEFINE_LOG_CATEGORY(LogSynapseCinematic);

void FSynapseCinematicModule::StartupModule()
{
	UE_LOG(LogSynapseCinematic, Log,
		TEXT("SynapseCinematic ready (native stereo source contract, ACES EXR manifests)."));
}

void FSynapseCinematicModule::ShutdownModule()
{
}

IMPLEMENT_MODULE(FSynapseCinematicModule, SynapseCinematic)

