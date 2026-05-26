package com.aci.hermes.ui.screens.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.HermesGold
import com.aci.hermes.ui.theme.JarvisBranding
import com.aci.hermes.ui.theme.LocalMotion
import com.aci.hermes.ui.theme.LocalSpacing
import kotlinx.coroutines.delay

@Composable
fun SplashScreen(onReady: () -> Unit) {
    val currentOnReady by rememberUpdatedState(onReady)
    val motion = LocalMotion.current
    val spacing = LocalSpacing.current

    val glyphScale = remember { Animatable(if (motion.reduced) 1f else 0.85f) }
    val glyphAlpha = remember { Animatable(if (motion.reduced) 1f else 0f) }

    LaunchedEffect(Unit) {
        if (!motion.reduced) {
            glyphAlpha.animateTo(1f, tween(durationMillis = 320, easing = LinearOutSlowInEasing))
            glyphScale.animateTo(1f, tween(durationMillis = 420, easing = LinearOutSlowInEasing))
        }
        delay(if (motion.reduced) 350 else 600)
        currentOnReady()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .testTag("splash_root")
            .semantics {
                contentDescription =
                    "${JarvisBranding.PRODUCT}, ${JarvisBranding.PERSONA}. ${JarvisBranding.TAGLINE}."
            },
        contentAlignment = Alignment.Center,
    ) {
        Column(
            verticalArrangement = Arrangement.spacedBy(spacing.lg),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = JarvisBranding.HERO_GLYPH,
                style = MaterialTheme.typography.displayLarge,
                color = HermesGold,
                modifier = Modifier
                    .graphicsLayer { alpha = glyphAlpha.value }
                    .scale(glyphScale.value),
            )
            Text(
                text = JarvisBranding.PRODUCT,
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                text = JarvisBranding.PERSONA,
                style = MaterialTheme.typography.titleSmall,
                color = HermesGold,
            )
            Text(
                text = JarvisBranding.TAGLINE,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onBackground,
            )
            CircularProgressIndicator(
                color = HermesGold,
                strokeWidth = 3.dp,
                modifier = Modifier.padding(top = spacing.sm),
            )
        }
    }
}
