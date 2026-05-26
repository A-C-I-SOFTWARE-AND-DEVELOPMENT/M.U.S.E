package com.jeremiahecherd.jarvisprime.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.jeremiahecherd.jarvisprime.R

@Composable
fun OnboardingScaffold(
    title: String,
    body: String,
    stepIndex: Int,
    stepCount: Int,
    onBack: (() -> Unit)? = null,
    onNext: (() -> Unit)? = null,
    nextLabel: String = stringResource(id = R.string.onboarding_next),
    backLabel: String = stringResource(id = R.string.onboarding_back),
    extras: @Composable () -> Unit = {},
) {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            StepIndicator(stepIndex = stepIndex, stepCount = stepCount)
            Spacer(modifier = Modifier.height(32.dp))
            Text(text = title, style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = body,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(modifier = Modifier.height(24.dp))
            extras()
            Spacer(modifier = Modifier.height(32.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (onBack != null) {
                    TextButton(onClick = onBack) { Text(text = backLabel) }
                } else {
                    Spacer(modifier = Modifier.size(1.dp))
                }
                if (onNext != null) {
                    Button(onClick = onNext) { Text(text = nextLabel) }
                }
            }
        }
    }
}

@Composable
private fun StepIndicator(stepIndex: Int, stepCount: Int) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        repeat(stepCount) { i ->
            val color = if (i <= stepIndex) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            }
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(color = color, shape = CircleShape),
            )
            if (i < stepCount - 1) Spacer(modifier = Modifier.size(6.dp))
        }
        Spacer(modifier = Modifier.size(12.dp))
        Text(
            text = "${stepIndex + 1} / $stepCount",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun OptionalNotice() {
    Text(
        text = stringResource(id = R.string.onboarding_optional),
        color = Color(0xFFB0BACB),
        style = MaterialTheme.typography.labelLarge,
    )
}
