package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun WhatJarvisDoesScreen(onBack: () -> Unit, onNext: () -> Unit) {
    OnboardingScaffold(
        title = stringResource(R.string.what_title),
        body = stringResource(R.string.what_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.WHAT),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        onNext = onNext,
    )
}
