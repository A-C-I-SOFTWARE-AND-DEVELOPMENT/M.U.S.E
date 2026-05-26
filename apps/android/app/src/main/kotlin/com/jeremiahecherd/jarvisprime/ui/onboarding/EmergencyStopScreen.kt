package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun EmergencyStopScreen(onBack: () -> Unit, onNext: () -> Unit) {
    OnboardingScaffold(
        title = stringResource(R.string.estop_title),
        body = stringResource(R.string.estop_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.EMERGENCY_STOP),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        onNext = onNext,
    )
}
