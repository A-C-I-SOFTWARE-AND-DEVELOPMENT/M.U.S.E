package com.aci.hermes.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
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
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val systemDark = isSystemInDarkTheme()
    val useDark = when (themeMode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.DARK -> true
        ThemeMode.LIGHT -> false
    }

    val colors = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val ctx = LocalContext.current
            if (useDark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        }
        useDark -> HermesDarkColors
        else -> HermesLightColors
    }

    MaterialTheme(
        colorScheme = colors,
        typography = HermesTypography,
        content = content
    )
}
