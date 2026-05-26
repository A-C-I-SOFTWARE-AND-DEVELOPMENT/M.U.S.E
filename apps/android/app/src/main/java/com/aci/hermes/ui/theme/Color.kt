package com.aci.hermes.ui.theme

import androidx.compose.ui.graphics.Color

// Jarvis Prime palette. Gold against deep ink — premium, calm,
// readable in both light and dark.
val JarvisGold = Color(0xFFFFD24A)
val JarvisGoldDeep = Color(0xFFB8860B)
val JarvisGoldSoft = Color(0xFFFFE595)

val JarvisInk = Color(0xFF0B0B12)
val JarvisInkSoft = Color(0xFF161622)
val JarvisInkMid = Color(0xFF1F1F2C)

val JarvisPaper = Color(0xFFFAF7EF)
val JarvisPaperDeep = Color(0xFFEFEAD9)

val JarvisAzure = Color(0xFF5F8BFF)
val JarvisAzureDeep = Color(0xFF3D63D9)

val JarvisCrimson = Color(0xFFE5484D)
val JarvisAmber = Color(0xFFE9A23B)
val JarvisJade = Color(0xFF22A06B)

val JarvisSurfaceDimDark = Color(0xFF12121C)
val JarvisSurfaceBrightLight = Color(0xFFF2EDDD)

// Legacy aliases — preserved so anything still referencing the old
// names compiles. Prefer the Jarvis* names in new code.
val HermesGold get() = JarvisGold
val HermesGoldDeep get() = JarvisGoldDeep
val HermesInk get() = JarvisInk
val HermesInkSoft get() = JarvisInkSoft
val HermesPaper get() = JarvisPaper
val HermesViolet get() = JarvisAzure
val HermesError get() = JarvisCrimson
val HermesSurfaceDim get() = JarvisSurfaceDimDark
val HermesSurfaceBright get() = JarvisSurfaceBrightLight
