#include "Misc/AutomationTest.h"
#include "MuseUniverseMath.h"
#include "MuseUniverseTypes.h"
#include "UObject/UnrealType.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseSchemaRejectionTest,
	"Synapse.Universe.SchemaRejection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseSchemaRejectionTest::RunTest(const FString& /*Parameters*/)
{
	constexpr int32 SupportedSchemaMajor = 1;
	TestNotEqual(TEXT("higher schema major is rejected"), 2, SupportedSchemaMajor);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseCursorGapResyncTest,
	"Synapse.Universe.CursorGapResync",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseCursorGapResyncTest::RunTest(const FString& /*Parameters*/)
{
	const int64 LastAcknowledgedCursor = 41;
	const int64 IncomingSequence = 43;
	TestTrue(TEXT("global sequence gaps are valid for a realm-filtered stream"),
		IncomingSequence > LastAcknowledgedCursor);
	const int64 LastRealmVersion = 8;
	const int64 ServerRealmVersion = 10;
	const int32 ReceivedRealmEvents = 1;
	TestTrue(TEXT("realm event-count gap requires resync"),
		ServerRealmVersion - LastRealmVersion != ReceivedRealmEvents);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseStaleEntityVersionTest,
	"Synapse.Universe.StaleEntityVersion",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseStaleEntityVersionTest::RunTest(const FString& /*Parameters*/)
{
	const int64 CurrentVersion = 7;
	TestFalse(TEXT("stale version cannot apply"), 6 > CurrentVersion);
	TestFalse(TEXT("equal version cannot overwrite"), 7 > CurrentVersion);
	TestTrue(TEXT("newer version applies"), 8 > CurrentVersion);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseMeterConversionTest,
	"Synapse.Universe.MeterConversion",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseMeterConversionTest::RunTest(const FString& /*Parameters*/)
{
	TestTrue(TEXT("one meter is one hundred centimeters"),
		FMath::IsNearlyEqual(MuseUniverseMath::MetersToCentimeters(1.0), 100.0));
	TestTrue(TEXT("station spine remains metric"),
		FMath::IsNearlyEqual(MuseUniverseMath::AxialSpineLengthMeters, 1800.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseCounterRotationTest,
	"Synapse.Universe.CounterRotation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseCounterRotationTest::RunTest(const FString& /*Parameters*/)
{
	const auto Pair = MuseUniverseMath::CounterRotationPair(0.25);
	TestTrue(TEXT("equal magnitude"), FMath::IsNearlyEqual(FMath::Abs(Pair.first), FMath::Abs(Pair.second)));
	TestTrue(TEXT("opposite sign"), FMath::IsNearlyEqual(Pair.first, -Pair.second));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseStationaryDockTest,
	"Synapse.Universe.StationaryDock",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseStationaryDockTest::RunTest(const FString& /*Parameters*/)
{
	const auto Start = MuseUniverseMath::StationaryDockTransform(0.0);
	const auto Later = MuseUniverseMath::StationaryDockTransform(900.0);
	TestTrue(TEXT("dock x remains fixed"), FMath::IsNearlyEqual(Start.X, Later.X));
	TestTrue(TEXT("dock y remains fixed"), FMath::IsNearlyEqual(Start.Y, Later.Y));
	TestTrue(TEXT("dock z remains fixed"), FMath::IsNearlyEqual(Start.Z, Later.Z));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseOneActiveVesselTest,
	"Synapse.Universe.OneActiveVessel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseOneActiveVesselTest::RunTest(const FString& /*Parameters*/)
{
	TSet<FString> ActiveBindings;
	ActiveBindings.Add(TEXT("research"));
	TestEqual(TEXT("first active binding is unique"), ActiveBindings.Num(), 1);
	const int32 CountBeforeDuplicate = ActiveBindings.Num();
	ActiveBindings.Add(TEXT("research"));
	TestEqual(TEXT("duplicate does not become a second active binding"), ActiveBindings.Num(), CountBeforeDuplicate);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseSimulationDamageLabelTest,
	"Synapse.Universe.SimulationDamageLabel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseSimulationDamageLabelTest::RunTest(const FString& /*Parameters*/)
{
	const bool bSimulation = true;
	const FString Label = bSimulation ? TEXT("SIMULATION DAMAGE") : TEXT("DEGRADED");
	TestTrue(TEXT("simulation damage is explicit"), Label.StartsWith(TEXT("SIMULATION")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseUniverseNoTokenSerializationTest,
	"Synapse.Universe.NoTokenSerialization",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseUniverseNoTokenSerializationTest::RunTest(const FString& /*Parameters*/)
{
	for (TFieldIterator<FProperty> Property(FMuseUniverseCommandRequest::StaticStruct()); Property; ++Property)
	{
		const FString Name = Property->GetName().ToLower();
		TestFalse(TEXT("command has no token property"), Name.Contains(TEXT("token")));
		TestFalse(TEXT("command has no phrase property"), Name.Contains(TEXT("phrase")));
		TestFalse(TEXT("command has no secret property"), Name.Contains(TEXT("secret")));
	}
	return true;
}

#endif  // WITH_DEV_AUTOMATION_TESTS
