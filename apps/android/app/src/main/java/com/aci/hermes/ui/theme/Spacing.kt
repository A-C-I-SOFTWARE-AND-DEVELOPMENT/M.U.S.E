package com.aci.hermes.ui.theme

import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Single source of truth for paddings, gaps, and corner radii inside the
 * Jarvis Prime cockpit. Screens reach this through [LocalSpacing] so a
 * future density tweak or larger-display retune is a one-file change
 * rather than a global search.
 */
data class HermesSpacing(
    val none: Dp = 0.dp,
    val xs: Dp = 4.dp,
    val sm: Dp = 8.dp,
    val md: Dp = 12.dp,
    val lg: Dp = 16.dp,
    val xl: Dp = 24.dp,
    val xxl: Dp = 32.dp,
    val screen: Dp = 16.dp,
    val cardPadding: Dp = 16.dp,
    val cardGap: Dp = 12.dp,
    val cornerSm: Dp = 8.dp,
    val cornerMd: Dp = 12.dp,
    val cornerLg: Dp = 20.dp,
    val statusDot: Dp = 10.dp,
    val touchTarget: Dp = 48.dp,
)

val LocalSpacing = staticCompositionLocalOf { HermesSpacing() }
