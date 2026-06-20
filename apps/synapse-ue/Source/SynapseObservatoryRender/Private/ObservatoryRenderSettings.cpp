// ObservatoryRenderSettings implementation.
// Copyright A-C-I Software & Development. All rights reserved.

#include "ObservatoryRenderSettings.h"

UObservatoryRenderSettings::UObservatoryRenderSettings()
{
	CategoryName = TEXT("Plugins");
	SectionName = TEXT("MUSE Observatory Render");
}

FName UObservatoryRenderSettings::GetCategoryName() const
{
	return TEXT("Plugins");
}
