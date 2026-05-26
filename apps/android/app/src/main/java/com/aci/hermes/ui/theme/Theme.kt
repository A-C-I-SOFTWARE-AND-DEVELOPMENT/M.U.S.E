package com.aci.hermes.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import com.aci.hermes.data.preferences.ThemeMode

private val JarvisLightColors = lightColorScheme(
    primary = JarvisGoldDeep,
    onPrimary = JarvisInk,
    primaryContainer = JarvisGoldSoft,
    onPrimaryContainer = JarvisInk,
    secondary = JarvisAzureDeep,
    onSecondary = JarvisPaper,
    secondaryContainer = JarvisPaperDeep,
    onSecondaryContainer = JarvisInk,
    tertiary = JarvisJade,
    background = JarvisPaper,
    onBackground = JarvisInk,
    surface = JarvisSurfaceBrightLight,
    onSurface = JarvisInk,
    surfaceVariant = JarvisPaperDeep,
    onSurfaceVariant = JarvisInkSoft,
    error = JarvisCrimson,
    onError = JarvisPaper,
)

private val JarvisDarkColors = darkColorScheme(
    primary = JarvisGold,
    onPrimary = JarvisInk,
    primaryContainer = JarvisGoldDeep,
    onPrimaryContainer = JarvisInk,
    secondary = JarvisAzure,
    onSecondary = JarvisInk,
    secondaryContainer = JarvisInkMid,
    onSecondaryContainer = JarvisPaper,
    tertiary = JarvisJade,
    background = JarvisInk,
    onBackground = JarvisPaper,
    surface = JarvisSurfaceDimDark,
    onSurface = JarvisPaper,
    surfaceVariant = JarvisInkSoft,
    onSurfaceVariant = JarvisPaperDeep,
    error = JarvisCrimson,
    onError = JarvisPaper,
)

@Composable
fun JarvisTheme(
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
        content = content,
    )
}

/**
 * Backwards-compatible alias for the original name. Prefer [JarvisTheme]
 * in new code.
 */
@Composable
fun HermesTheme(
    themeMode: ThemeMode = ThemeMode.SYSTEM,
    content: @Composable () -> Unit,
) = JarvisTheme(themeMode = themeMode, content = content)
