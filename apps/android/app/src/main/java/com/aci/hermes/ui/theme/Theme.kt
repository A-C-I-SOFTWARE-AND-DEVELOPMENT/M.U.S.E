package com.aci.hermes.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.aci.hermes.data.preferences.ThemeMode

private val JarvisDarkColors = darkColorScheme(
    primary = JarvisGold,
    onPrimary = JarvisInk,
    primaryContainer = JarvisGoldDeep,
    onPrimaryContainer = JarvisInk,
    secondary = JarvisCyan,
    onSecondary = JarvisInk,
    secondaryContainer = JarvisCyanDeep,
    onSecondaryContainer = JarvisFog,
    tertiary = JarvisGreen,
    onTertiary = JarvisInk,
    background = JarvisInk,
    onBackground = JarvisFog,
    surface = JarvisNavy,
    onSurface = JarvisFog,
    surfaceVariant = JarvisNavyElevated,
    onSurfaceVariant = JarvisFogDim,
    outline = JarvisNavyMuted,
    outlineVariant = JarvisNavyMuted,
    error = JarvisRed,
    onError = JarvisInk,
    errorContainer = JarvisRedDeep,
    onErrorContainer = JarvisFog,
)

// Jarvis Prime is designed as a dark, premium command surface. The
// light scheme exists only so the system "follow system theme" toggle
// doesn't produce an unreadable result during the daytime — it
// preserves the gold / cyan / red / green roles but lifts the
// foundation. Owner-facing surfaces (icon, voice, approvals) are
// always intended to read against the dark navy.
private val JarvisLightColors = lightColorScheme(
    primary = JarvisGoldDeep,
    onPrimary = JarvisInk,
    primaryContainer = JarvisGold,
    onPrimaryContainer = JarvisInk,
    secondary = JarvisCyanDeep,
    onSecondary = JarvisFog,
    secondaryContainer = JarvisCyan,
    onSecondaryContainer = JarvisInk,
    tertiary = JarvisGreenDeep,
    onTertiary = JarvisFog,
    background = JarvisFog,
    onBackground = JarvisInk,
    surface = JarvisFog,
    onSurface = JarvisInk,
    surfaceVariant = Color(0xFFE0E4EF),
    onSurfaceVariant = JarvisNavy,
    outline = Color(0xFFB1B8C7),
    outlineVariant = Color(0xFFB1B8C7),
    error = JarvisRedDeep,
    onError = JarvisFog,
    errorContainer = JarvisRed,
    onErrorContainer = JarvisInk,
)

@Composable
fun HermesTheme(
    themeMode: ThemeMode = ThemeMode.SYSTEM,
    content: @Composable () -> Unit
) {
    val systemDark = isSystemInDarkTheme()
    val useDark = when (themeMode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
    }

    MaterialTheme(
        colorScheme = if (useDark) JarvisDarkColors else JarvisLightColors,
        typography = HermesTypography,
        content = content
    )
}

@Composable
fun JarvisTheme(
    themeMode: ThemeMode = ThemeMode.DARK,
    content: @Composable () -> Unit,
) = HermesTheme(themeMode = themeMode, content = content)
