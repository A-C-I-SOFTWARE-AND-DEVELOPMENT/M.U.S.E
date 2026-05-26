package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun FinishScreen(onFinish: () -> Unit) {
    OnboardingScaffold(
        title = stringResource(R.string.finish_title),
        body = stringResource(R.string.finish_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.FINISH),
        stepCount = ONBOARDING_ROUTES.size,
        onNext = onFinish,
        nextLabel = stringResource(R.string.onboarding_finish),
    )
}
