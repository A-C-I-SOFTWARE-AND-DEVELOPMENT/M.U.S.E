package com.aci.hermes.ui.screens.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.components.JarvisPrimeIcon

/**
 * One-page onboarding shown on first launch. Tap "Get started" to mark the
 * user as onboarded and land on Home.
 */
@Composable
fun OnboardingScreen(
    onFinish: () -> Unit,
    onSkip: () -> Unit = onFinish,
) {
    Box(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            horizontalAlignment = Alignment.Start,
        ) {
            Spacer(Modifier.height(8.dp))
            JarvisPrimeIcon(
                size = 72.dp,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            )
            Text(
                text = stringResource(R.string.onboarding_title),
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = stringResource(R.string.onboarding_subtitle),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )

            OnboardingBullet(
                title = stringResource(R.string.onboarding_bullet_local_title),
                body = stringResource(R.string.onboarding_bullet_local_body),
            )
            OnboardingBullet(
                title = stringResource(R.string.onboarding_bullet_handoff_title),
                body = stringResource(R.string.onboarding_bullet_handoff_body),
            )
            OnboardingBullet(
                title = stringResource(R.string.onboarding_bullet_safety_title),
                body = stringResource(R.string.onboarding_bullet_safety_body),
            )

            Spacer(Modifier.height(8.dp))
            Button(
                onClick = onFinish,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(stringResource(R.string.onboarding_cta)) }
            TextButton(
                onClick = onSkip,
                modifier = Modifier.align(Alignment.End),
            ) { Text(stringResource(R.string.onboarding_skip)) }
        }
    }
}

@Composable
private fun OnboardingBullet(title: String, body: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
