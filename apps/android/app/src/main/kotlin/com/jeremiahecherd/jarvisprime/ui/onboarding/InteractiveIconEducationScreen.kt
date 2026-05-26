package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun InteractiveIconEducationScreen(onBack: () -> Unit, onNext: () -> Unit) {
    OnboardingScaffold(
        title = stringResource(R.string.icon_title),
        body = stringResource(R.string.icon_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.ICON),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        onNext = onNext,
    )
}
