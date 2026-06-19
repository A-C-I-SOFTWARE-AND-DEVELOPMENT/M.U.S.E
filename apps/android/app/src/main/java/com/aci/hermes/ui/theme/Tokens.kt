package com.aci.hermes.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * muse design tokens — spacing, radii, elevations.
 *
 * Numbers come from docs/jarvis-prime-app-design-system.md. Use these
 * constants in composables instead of hard-coding values, so a future
 * density change happens in one place.
 */
object JarvisTokens {

    // Spacing — 4dp baseline grid.
    val SpaceXxs = 2.dp
    val SpaceXs  = 4.dp
    val SpaceSm  = 8.dp
    val SpaceMd  = 12.dp
    val SpaceLg  = 16.dp
    val SpaceXl  = 20.dp
    val SpaceXxl = 24.dp
    val SpaceXxxl = 32.dp

    // Card / surface radii.
    val RadiusSm  = 8.dp
    val RadiusMd  = 14.dp
    val RadiusLg  = 20.dp
    val RadiusXl  = 28.dp

    // Status pill geometry.
    val PillHeight  = 26.dp
    val PillRadius  = 14.dp

    // Hairline border for "command-center" framed cards.
    val BorderHairline = 1.dp
    val BorderFocus    = 1.5.dp

    // Glow ring for active / listening / approval states.
    val GlowRing       = 2.dp

    // Reusable shapes.
    val ShapeCard     = RoundedCornerShape(RadiusMd)
    val ShapeCardLarge = RoundedCornerShape(RadiusLg)
    val ShapePill     = RoundedCornerShape(PillRadius)
    val ShapeButton   = RoundedCornerShape(RadiusSm)
}

/**
 * Material 3 [Shapes] derived from [JarvisTokens] radii, wired into the
 * theme so every M3 component (Card, Button, Menu, Sheet, …) picks up the
 * branded corner language by default — not just the screens that reach for
 * `JarvisTokens.Shape*` explicitly.
 */
val JarvisShapes = Shapes(
    extraSmall = RoundedCornerShape(JarvisTokens.RadiusSm),
    small = RoundedCornerShape(JarvisTokens.RadiusSm),
    medium = RoundedCornerShape(JarvisTokens.RadiusMd),
    large = RoundedCornerShape(JarvisTokens.RadiusLg),
    extraLarge = RoundedCornerShape(JarvisTokens.RadiusXl),
)
