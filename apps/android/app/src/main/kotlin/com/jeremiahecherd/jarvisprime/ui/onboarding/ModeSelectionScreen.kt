package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jeremiahecherd.jarvisprime.R
import com.jeremiahecherd.jarvisprime.data.JarvisMode
import com.jeremiahecherd.jarvisprime.data.OnboardingState
import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes

@Composable
fun ModeSelectionScreen(
    state: OnboardingState,
    onModeSelected: (JarvisMode) -> Unit,
    onBack: () -> Unit,
    onNext: () -> Unit,
) {
    OnboardingScaffold(
        title = stringResource(R.string.mode_title),
        body = stringResource(R.string.mode_body),
        stepIndex = ONBOARDING_ROUTES.indexOf(Routes.MODE),
        stepCount = ONBOARDING_ROUTES.size,
        onBack = onBack,
        onNext = onNext,
    ) {
        ModeCard(
            mode = JarvisMode.MOCK,
            title = stringResource(R.string.mode_mock_title),
            body = stringResource(R.string.mode_mock_body),
            selected = state.mode == JarvisMode.MOCK,
            onSelected = onModeSelected,
        )
        Spacer(modifier = Modifier.height(12.dp))
        ModeCard(
            mode = JarvisMode.GATEWAY,
            title = stringResource(R.string.mode_gateway_title),
            body = stringResource(R.string.mode_gateway_body),
            selected = state.mode == JarvisMode.GATEWAY,
            onSelected = onModeSelected,
        )
        Spacer(modifier = Modifier.height(12.dp))
        ModeCard(
            mode = JarvisMode.TERMUX,
            title = stringResource(R.string.mode_termux_title),
            body = stringResource(R.string.mode_termux_body),
            selected = state.mode == JarvisMode.TERMUX,
            onSelected = onModeSelected,
        )
    }
}

@Composable
private fun ModeCard(
    mode: JarvisMode,
    title: String,
    body: String,
    selected: Boolean,
    onSelected: (JarvisMode) -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .selectable(selected = selected, onClick = { onSelected(mode) }),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            RadioButton(selected = selected, onClick = { onSelected(mode) })
            Text(text = title, style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = body,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
