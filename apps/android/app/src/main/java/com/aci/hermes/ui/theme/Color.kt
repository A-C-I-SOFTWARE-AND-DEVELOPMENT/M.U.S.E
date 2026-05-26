package com.aci.hermes.ui.theme

import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

val HermesGold = Color(0xFFFFD700)
val HermesGoldDeep = Color(0xFFB8860B)
val HermesInk = Color(0xFF0E0E12)
val HermesInkSoft = Color(0xFF1A1A24)
val HermesPaper = Color(0xFFFAF9F6)
val HermesViolet = Color(0xFF5865F2)
val HermesError = Color(0xFFE5484D)
val HermesSurfaceDim = Color(0xFF161620)
val HermesSurfaceBright = Color(0xFFF1EFE8)

// Semantic tokens. Material 3 only ships error in its color scheme, so
// "warning", "success", and "info" live as Jarvis-specific extensions
// and are pulled through [LocalHermesSemantics]. Keeping them here
// prevents one-off Color literals from leaking into screen code.
val HermesWarn = Color(0xFFE0A82E)
val HermesWarnDark = Color(0xFFB8860B)
val HermesSuccess = Color(0xFF2EA468)
val HermesSuccessDark = Color(0xFF1F7A4D)
val HermesInfo = Color(0xFF5865F2)
val HermesInfoDark = Color(0xFF3A45B5)
val HermesDangerSoft = Color(0xFFFFE5E7)
val HermesWarnSoft = Color(0xFFFFF4D6)
val HermesSuccessSoft = Color(0xFFDDF3E7)
val HermesInfoSoft = Color(0xFFE3E5FF)

data class HermesSemantics(
    val warn: Color,
    val onWarn: Color,
    val warnSurface: Color,
    val success: Color,
    val onSuccess: Color,
    val successSurface: Color,
    val info: Color,
    val onInfo: Color,
    val infoSurface: Color,
    val dangerSurface: Color,
)

val LocalHermesSemantics = staticCompositionLocalOf {
    HermesSemantics(
        warn = HermesWarn,
        onWarn = HermesInk,
        warnSurface = HermesWarnSoft,
        success = HermesSuccess,
        onSuccess = HermesPaper,
        successSurface = HermesSuccessSoft,
        info = HermesInfo,
        onInfo = HermesPaper,
        infoSurface = HermesInfoSoft,
        dangerSurface = HermesDangerSoft,
    )
}
