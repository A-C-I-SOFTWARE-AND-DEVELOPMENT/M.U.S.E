package com.aci.hermes.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import com.aci.hermes.data.preferences.ThemeMode

private val HermesLightColors = lightColorScheme(
    primary = HermesGoldDeep,
    onPrimary = HermesInk,
    secondary = HermesViolet,
    onSecondary = HermesPaper,
    background = HermesPaper,
    onBackground = HermesInk,
    surface = HermesSurfaceBright,
    onSurface = HermesInk,
    surfaceVariant = HermesPaper,
    error = HermesError
)

private val HermesDarkColors = darkColorScheme(
    primary = HermesGold,
    onPrimary = HermesInk,
    secondary = HermesViolet,
    onSecondary = HermesPaper,
    background = HermesInk,
    onBackground = HermesPaper,
    surface = HermesSurfaceDim,
    onSurface = HermesPaper,
    surfaceVariant = HermesInkSoft,
    error = HermesError
)

private val HermesLightSemantics = HermesSemantics(
    warn = HermesWarnDark,
    onWarn = HermesPaper,
    warnSurface = HermesWarnSoft,
    success = HermesSuccessDark,
    onSuccess = HermesPaper,
    successSurface = HermesSuccessSoft,
    info = HermesInfoDark,
    onInfo = HermesPaper,
    infoSurface = HermesInfoSoft,
    dangerSurface = HermesDangerSoft,
)

private val HermesDarkSemantics = HermesSemantics(
    warn = HermesWarn,
    onWarn = HermesInk,
    warnSurface = HermesWarnDark.copy(alpha = 0.20f),
    success = HermesSuccess,
    onSuccess = HermesInk,
    successSurface = HermesSuccessDark.copy(alpha = 0.22f),
    info = HermesInfo,
    onInfo = HermesPaper,
    infoSurface = HermesInfoDark.copy(alpha = 0.22f),
    dangerSurface = HermesError.copy(alpha = 0.18f),
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

    val semantics = if (useDark) HermesDarkSemantics else HermesLightSemantics
    val motion = rememberMotionPreferences()
    val spacing = HermesSpacing()

    CompositionLocalProvider(
        LocalHermesSemantics provides semantics,
        LocalMotion provides motion,
        LocalSpacing provides spacing,
    ) {
        MaterialTheme(
            colorScheme = if (useDark) HermesDarkColors else HermesLightColors,
            typography = HermesTypography,
            shapes = HermesShapes,
            content = content
        )
    }
}
