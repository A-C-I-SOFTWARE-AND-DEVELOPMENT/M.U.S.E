package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun WelcomeScreen(onNext: () -> Unit) {
    OnboardingScaffold(
        title = stringResource(R.string.welcome_title),
        body = stringResource(R.string.welcome_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.WELCOME),
        stepCount = ONBOARDING_ROUTES.size,
        onNext = onNext,
    )
}
