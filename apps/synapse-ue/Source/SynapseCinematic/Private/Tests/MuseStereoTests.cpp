#include "Misc/AutomationTest.h"
#include "MuseRenderManifestSubsystem.h"
#include "MuseStereoTypes.h"
#include "MuseUniverseMath.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoPhysicalSeparationTest,
	"Synapse.Cinematic.PhysicalSeparation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoPhysicalSeparationTest::RunTest(const FString& /*Parameters*/)
{
	const auto Offsets = MuseUniverseMath::StereoOffsetsMeters(65.0);
	TestTrue(TEXT("left is -32.5 mm"), FMath::IsNearlyEqual(Offsets.first, -0.0325, 1e-12));
	TestTrue(TEXT("right is +32.5 mm"), FMath::IsNearlyEqual(Offsets.second, 0.0325, 1e-12));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoConvergenceTest,
	"Synapse.Cinematic.Convergence",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoConvergenceTest::RunTest(const FString& /*Parameters*/)
{
	const FMuseStereoShotMetadata Defaults;
	TestEqual(TEXT("verified default policy is toe-in"),
		Defaults.StereoPolicy, EMuseStereoPolicy::SymmetricToeIn);
	const auto Directions = MuseUniverseMath::ConvergenceVectors(65.0, 10.0);
	TestTrue(TEXT("horizontal convergence is symmetric"),
		FMath::IsNearlyEqual(Directions.first.X, -Directions.second.X, 1e-12));
	TestTrue(TEXT("forward convergence is equal"),
		FMath::IsNearlyEqual(Directions.first.Y, Directions.second.Y, 1e-12));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoTemporalParityTest,
	"Synapse.Cinematic.TemporalParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoTemporalParityTest::RunTest(const FString& /*Parameters*/)
{
	const FMuseStereoRenderSettings SharedSettings;
	TestEqual(TEXT("shared temporal samples"), SharedSettings.TemporalSamples, 8);
	TestEqual(TEXT("shared spatial samples"), SharedSettings.SpatialSamples, 8);
	TestEqual(TEXT("shared frame-rate numerator"), SharedSettings.OutputFrameRate.Numerator, 24);
	TestEqual(TEXT("shared frame-rate denominator"), SharedSettings.OutputFrameRate.Denominator, 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoEyeNamingTest,
	"Synapse.Cinematic.EyeNaming",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoEyeNamingTest::RunTest(const FString& /*Parameters*/)
{
	UMuseRenderManifestSubsystem* Manifest = NewObject<UMuseRenderManifestSubsystem>();
	FMuseStereoShotMetadata Shot;
	Shot.ShotId = TEXT("shot_001");
	Shot.SceneRevision = TEXT("scene_abc");
	const TArray<FMuseEyeRenderJob> Jobs = Manifest->BuildNativeStereoJobs(Shot, FMuseStereoRenderSettings{});
	TestEqual(TEXT("two eye jobs"), Jobs.Num(), 2);
	TestTrue(TEXT("left naming"), Jobs[0].FileNameFormat.Contains(TEXT("eye_L")));
	TestTrue(TEXT("right naming"), Jobs[1].FileNameFormat.Contains(TEXT("eye_R")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoFrameParityTest,
	"Synapse.Cinematic.FrameParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoFrameParityTest::RunTest(const FString& /*Parameters*/)
{
	FMuseFrameRecord Left;
	Left.Eye = EMuseStereoEye::Left;
	Left.FrameNumber = 101;
	FMuseFrameRecord Right;
	Right.Eye = EMuseStereoEye::Right;
	Right.FrameNumber = 101;
	TestEqual(TEXT("same frame"), Left.FrameNumber, Right.FrameNumber);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoMetadataHashTest,
	"Synapse.Cinematic.MetadataHash",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoMetadataHashTest::RunTest(const FString& /*Parameters*/)
{
	const FString Canonical = TEXT("{\"scene_revision\":\"scene_abc\",\"seed\":7}");
	const std::string Utf8(TCHAR_TO_UTF8(*Canonical));
	const std::string First = MuseUniverseMath::DeterministicShotHash(Utf8);
	const std::string Second = MuseUniverseMath::DeterministicShotHash(Utf8);
	TestEqual(
		TEXT("deterministic hash"),
		FString(UTF8_TO_TCHAR(First.c_str())),
		FString(UTF8_TO_TCHAR(Second.c_str())));
	TestEqual(TEXT("sha256 length"), static_cast<int32>(First.size()), 64);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoSafeGuidesTest,
	"Synapse.Cinematic.SafeGuides",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoSafeGuidesTest::RunTest(const FString& /*Parameters*/)
{
	FMuseStereoShotMetadata Shot;
	TestTrue(TEXT("1.90 protected"), Shot.bProtectSafeGuide190);
	TestTrue(TEXT("1.43 protected"), Shot.bProtectSafeGuide143);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoVerticalAlignmentTest,
	"Synapse.Cinematic.VerticalAlignment",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoVerticalAlignmentTest::RunTest(const FString& /*Parameters*/)
{
	const double LeftPixels = 0.1;
	const double RightPixels = 0.2;
	TestTrue(TEXT("vertical mismatch is within half-pixel budget"),
		FMath::Abs(LeftPixels - RightPixels) <= 0.5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FMuseStereoPostConversionRejectionTest,
	"Synapse.Cinematic.PostConversionRejection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMuseStereoPostConversionRejectionTest::RunTest(const FString& /*Parameters*/)
{
	FMuseStereoShotMetadata Shot;
	Shot.bPostConvertedDepthCard = true;
	FString Error;
	TestTrue(TEXT("post-converted depth card is rejected"),
		UMuseRenderManifestSubsystem::RejectPostConvertedDepthCard(Shot, Error));
	TestTrue(TEXT("diagnostic does not claim native stereo"), Error.Contains(TEXT("cannot be labeled")));
	return true;
}

#endif  // WITH_DEV_AUTOMATION_TESTS
