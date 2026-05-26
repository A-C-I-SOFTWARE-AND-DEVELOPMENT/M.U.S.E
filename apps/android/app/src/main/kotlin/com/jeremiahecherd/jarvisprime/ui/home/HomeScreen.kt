package com.jeremiahecherd.jarvisprime.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.data.JarvisMode
import com.jeremiahecherd.jarvisprime.data.OnboardingState

@Composable
fun HomeScreen(
    state: OnboardingState,
    onToggleEmergencyStop: (Boolean) -> Unit,
    onReplayOnboarding: () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
        ) {
            Text(text = stringResource(R.string.home_title), style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(24.dp))

            StatusCard(
                label = stringResource(R.string.home_mode_label),
                value = state.mode.label(),
            )
            Spacer(modifier = Modifier.height(12.dp))
            StatusCard(
                label = stringResource(R.string.home_notif_state),
                value = onOff(state.notificationOptIn),
            )
            Spacer(modifier = Modifier.height(12.dp))
            StatusCard(
                label = stringResource(R.string.home_voice_state),
                value = onOff(state.voiceOptIn),
            )

            Spacer(modifier = Modifier.height(24.dp))
            EmergencyStopCard(
                engaged = state.emergencyStopEngaged,
                onToggle = onToggleEmergencyStop,
            )

            Spacer(modifier = Modifier.height(24.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onReplayOnboarding) {
                    Text(text = stringResource(R.string.home_replay_onboarding))
                }
            }
        }
    }
}

@Composable
private fun StatusCard(label: String, value: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(text = label, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text = value, style = MaterialTheme.typography.titleLarge)
        }
    }
}

@Composable
private fun EmergencyStopCard(engaged: Boolean, onToggle: (Boolean) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (engaged) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = stringResource(R.string.home_estop), style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = if (engaged) stringResource(R.string.state_engaged) else stringResource(R.string.state_clear),
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(modifier = Modifier.height(12.dp))
            Button(
                onClick = { onToggle(!engaged) },
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (engaged) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.error,
                ),
            ) {
                Text(
                    text = if (engaged) {
                        stringResource(R.string.home_estop_release)
                    } else {
                        stringResource(R.string.home_estop_engage)
                    },
                )
            }
        }
    }
}

@Composable
private fun onOff(value: Boolean): String = if (value) {
    stringResource(R.string.state_on)
} else {
    stringResource(R.string.state_off)
}

private fun JarvisMode.label(): String = when (this) {
    JarvisMode.MOCK -> "Mock"
    JarvisMode.GATEWAY -> "Gateway"
    JarvisMode.TERMUX -> "Termux"
}
