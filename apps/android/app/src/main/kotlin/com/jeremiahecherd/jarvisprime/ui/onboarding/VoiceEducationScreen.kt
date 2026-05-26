package com.jeremiahecherd.jarvisprime.ui.onboarding

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.data.OnboardingState
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun VoiceEducationScreen(
    state: OnboardingState,
    onMarkOptedIn: () -> Unit,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onSkip: () -> Unit,
) {
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) onMarkOptedIn()
        onNext()
    }

    OnboardingScaffold(
        title = stringResource(R.string.voice_title),
        body = stringResource(R.string.voice_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.VOICE),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        onNext = null,
    ) {
        OptionalNotice()
        Spacer(modifier = Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Button(onClick = { launcher.launch(Manifest.permission.RECORD_AUDIO) }) {
                Text(stringResource(R.string.voice_setup))
            }
            OutlinedButton(onClick = onSkip) { Text(stringResource(R.string.voice_skip)) }
        }
    }
}
