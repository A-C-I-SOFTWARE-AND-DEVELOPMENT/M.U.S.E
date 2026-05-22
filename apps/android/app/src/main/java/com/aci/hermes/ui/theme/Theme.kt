package com.aci.hermes.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
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
        colorScheme = if (useDark) HermesDarkColors else HermesLightColors,
        typography = HermesTypography,
        content = content
    )
}
