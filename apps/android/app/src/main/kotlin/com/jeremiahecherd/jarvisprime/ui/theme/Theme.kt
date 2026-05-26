package com.jeremiahecherd.jarvisprime.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val JarvisColors = darkColorScheme(
    primary = JarvisAccent,
    onPrimary = JarvisBackground,
    secondary = JarvisAccentMuted,
    background = JarvisBackground,
    onBackground = JarvisOnSurface,
    surface = JarvisSurface,
    onSurface = JarvisOnSurface,
    surfaceVariant = JarvisSurfaceVariant,
    onSurfaceVariant = JarvisOnSurfaceMuted,
    error = JarvisDanger,
)

@Composable
fun JarvisPrimeTheme(
    @Suppress("UNUSED_PARAMETER") darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = JarvisColors,
        typography = JarvisTypography,
        content = content,
    )
}
