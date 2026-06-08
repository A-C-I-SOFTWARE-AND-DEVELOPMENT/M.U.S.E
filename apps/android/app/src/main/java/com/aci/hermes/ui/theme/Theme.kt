package com.aci.hermes.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import com.aci.hermes.data.preferences.ThemeMode

// MUSE is dark-first. The dark scheme is the canonical experience;
// the light scheme keeps the product usable in bright daylight but is not
// the primary identity.

private val JarvisDarkColors = darkColorScheme(
    primary           = JarvisGold,
    onPrimary         = JarvisInkAbyss,
    primaryContainer  = JarvisGoldDeep,
    onPrimaryContainer = JarvisInkAbyss,

    secondary         = JarvisCyan,
    onSecondary       = JarvisInkAbyss,
    secondaryContainer = JarvisCyanDeep,
    onSecondaryContainer = JarvisSignal,

    tertiary          = JarvisViolet,
    onTertiary        = JarvisInkAbyss,

    background        = JarvisInkAbyss,
    onBackground      = JarvisSignal,

    surface           = JarvisInkDeep,
    onSurface         = JarvisSignal,
    surfaceVariant    = JarvisInkRaised,
    onSurfaceVariant  = JarvisSignalDim,
    surfaceTint       = JarvisGold,

    // M3 surface hierarchy — mapped to the JARVIS ink ladder so elevation
    // reads as deeper-to-lighter navy rather than default grey tints.
    surfaceDim              = JarvisInkAbyss,
    surfaceBright           = JarvisInkRaised,
    surfaceContainerLowest  = JarvisInkAbyss,
    surfaceContainerLow     = JarvisInkNight,
    surfaceContainer        = JarvisInkDeep,
    surfaceContainerHigh    = JarvisInkRaised,
    surfaceContainerHighest = JarvisInkEdge,

    inverseSurface    = JarvisPaperSoft,
    inverseOnSurface  = JarvisInkOnPaper,
    inversePrimary    = JarvisGoldDeep,

    outline           = JarvisInkEdge,
    outlineVariant    = JarvisSignalGhost,

    error             = JarvisCrimson,
    onError           = JarvisInkAbyss,
    errorContainer    = JarvisCrimsonDeep,
    onErrorContainer  = JarvisSignal,

    scrim             = JarvisInkAbyss
)

private val JarvisLightColors = lightColorScheme(
    primary           = JarvisGoldDeep,
    onPrimary         = JarvisInkOnPaper,
    primaryContainer  = JarvisGold,
    onPrimaryContainer = JarvisInkOnPaper,

    secondary         = JarvisCyanDeep,
    onSecondary       = JarvisPaper,
    secondaryContainer = JarvisCyan,
    onSecondaryContainer = JarvisInkOnPaper,

    tertiary          = JarvisViolet,
    onTertiary        = JarvisPaper,

    background        = JarvisPaper,
    onBackground      = JarvisInkOnPaper,

    surface           = JarvisPaperSoft,
    onSurface         = JarvisInkOnPaper,
    surfaceVariant    = JarvisPaper,
    onSurfaceVariant  = JarvisInkOnPaper,
    surfaceTint       = JarvisGoldDeep,

    // Light surface hierarchy — restrained paper ladder.
    surfaceDim              = JarvisPaperSoft,
    surfaceBright           = JarvisPaper,
    surfaceContainerLowest  = JarvisPaper,
    surfaceContainerLow     = JarvisPaperSoft,
    surfaceContainer        = JarvisPaperSoft,
    surfaceContainerHigh    = JarvisPaperSoft,
    surfaceContainerHighest = JarvisPaper,

    outline           = JarvisSignalMute,
    outlineVariant    = JarvisSignalGhost,

    error             = JarvisCrimson,
    onError           = JarvisPaper,
    errorContainer    = JarvisCrimsonBright,
    onErrorContainer  = JarvisInkOnPaper
)

/**
 * Root theme. Renamed semantically to JarvisPrimeTheme; the old
 * [HermesTheme] entry point is kept as an alias so existing call sites
 * (MainActivity, previews) keep compiling.
 */
@Composable
fun JarvisPrimeTheme(
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
        typography = JarvisTypography,
        shapes = JarvisShapes,
        content = content
    )
}

/** Back-compat shim — old name, new identity. */
@Composable
fun HermesTheme(
    themeMode: ThemeMode = ThemeMode.SYSTEM,
    content: @Composable () -> Unit
) = JarvisPrimeTheme(themeMode = themeMode, content = content)
