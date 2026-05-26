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
import com.jeremiahecherd.jarvisprime.permissions.PermissionHelpers

@Composable
fun NotificationEducationScreen(
    state: OnboardingState,
    onMarkOptedIn: () -> Unit,
    onBack: () -> Unit,
    onNext: () -> Unit,
    onSkip: () -> Unit,
) {
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        // Persist the user's opt-in regardless of the system answer so we
        // know they made the choice — re-prompting later is handled in
        // settings, never silently here.
        if (granted) onMarkOptedIn()
        onNext()
    }

    OnboardingScaffold(
        title = stringResource(R.string.notif_title),
        body = stringResource(R.string.notif_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.NOTIFICATION),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        // Footer Next is omitted — the row below carries Enable / Not now.
        onNext = null,
    ) {
        OptionalNotice()
        Spacer(modifier = Modifier.height(16.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Button(
                onClick = {
                    if (PermissionHelpers.notificationRuntimePromptRequired()) {
                        launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        // Pre-Tiramisu devices: notifications work without a
                        // runtime prompt, so the opt-in tap is enough.
                        onMarkOptedIn()
                        onNext()
                    }
                },
            ) { Text(stringResource(R.string.notif_enable)) }
            OutlinedButton(onClick = onSkip) { Text(stringResource(R.string.notif_skip)) }
        }
    }
}
