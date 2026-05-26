package com.aci.hermes.ui.screens.onboarding

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.icon.InteractiveIcon

@Composable
fun OnboardingScreen(
    viewModel: OnboardingViewModel,
    onFinished: () -> Unit,
) {
    val state by viewModel.state.collectAsState()

    val notifLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { granted ->
        viewModel.onNotificationPermissionResult(granted)
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                InteractiveIcon(sizeDp = 120, contentDescription = null)

                when (state.step) {
                    OnboardingStep.Welcome -> StepCopy(
                        titleRes = R.string.onboarding_welcome_title,
                        bodyRes = R.string.onboarding_welcome_body,
                    )
                    OnboardingStep.Safety -> StepCopy(
                        titleRes = R.string.onboarding_safety_title,
                        bodyRes = R.string.onboarding_safety_body,
                    )
                    OnboardingStep.Voice -> StepCopy(
                        titleRes = R.string.onboarding_voice_title,
                        bodyRes = R.string.onboarding_voice_body,
                    )
                    OnboardingStep.Notifications -> StepCopy(
                        titleRes = R.string.onboarding_notifications_title,
                        bodyRes = R.string.onboarding_notifications_body,
                    )
                }

                StepDots(
                    total = OnboardingStep.entries.size,
                    current = state.step.ordinal,
                )
            }

            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                when (state.step) {
                    OnboardingStep.Notifications -> {
                        Button(
                            onClick = {
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                    notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                                } else {
                                    viewModel.onNotificationPermissionResult(true)
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.onboarding_notifications_allow))
                        }
                        OutlinedButton(
                            onClick = {
                                viewModel.skipNotifications()
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.onboarding_notifications_skip))
                        }
                        Button(
                            onClick = {
                                viewModel.complete()
                                onFinished()
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                            ),
                        ) {
                            Text(stringResource(R.string.onboarding_done))
                        }
                    }
                    else -> {
                        Button(
                            onClick = viewModel::next,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.onboarding_next))
                        }
                        if (state.step != OnboardingStep.Welcome) {
                            TextButton(onClick = viewModel::back, modifier = Modifier.fillMaxWidth()) {
                                Text(stringResource(R.string.onboarding_back))
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StepCopy(titleRes: Int, bodyRes: Int) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = stringResource(titleRes),
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
        )
        Text(
            text = stringResource(bodyRes),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(horizontal = 4.dp),
        )
    }
}

@Composable
private fun StepDots(total: Int, current: Int) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        repeat(total) { idx ->
            val active = idx == current
            Surface(
                color = if (active) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.18f),
                shape = CircleShape,
                modifier = Modifier.size(if (active) 10.dp else 8.dp),
            ) { Spacer(Modifier.size(10.dp)) }
            if (idx < total - 1) Spacer(modifier = Modifier.width(0.dp))
        }
    }
    Spacer(modifier = Modifier.padding(PaddingValues()))
}
