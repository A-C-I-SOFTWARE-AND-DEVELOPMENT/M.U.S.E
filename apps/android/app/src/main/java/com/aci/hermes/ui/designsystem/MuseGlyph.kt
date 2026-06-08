package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisViolet

// Cool-white bloom tints. Per docs/brand/muse-design-language.md these are
// *derived glows*, not brand color tokens — they exist only inside the core's
// bloom so it reads cool against the warm-neutral white core. Defined locally
// (NOT in theme/Color.kt) because they are not part of the Singularity token
// set; the brand colors stay in Color.kt as Jarvis* and are reused below.
private val BloomInner = Color(0xFFF2FBFF) // tight, near-white center
private val BloomMid = Color(0xFFD4F2FF)   // mid halo
private val BloomEdge = Color(0xFFE0F8FF)  // wide faint edge

/**
 * The MUSE incandescent mark — "one mind, many pathways."
 *
 * A single white [core][JarvisGold] that blazes in the void, wrapped by one
 * thin **matte** spectral ring ([JarvisCyan] → [JarvisViolet]) with a single
 * gap, rotated -32° so the gap sits lower-right (canonical geometry from
 * `docs/brand/muse-design-language.md` §2 and the cockpit header svg).
 *
 * Lighting recipe (§5): volumetric bloom on the **white core only**, built
 * from stacked cool-white radial halos plus a tight core punch. The ring is
 * matte — **never** glowed or bloomed (emissive core + matte ring = the depth
 * read). No drop shadows, no lens flare, no ring glow.
 *
 * Vector-drawn so it scales cleanly at any density and survives small sizes.
 *
 * @param size square edge length.
 * @param showBloom when true, draws the cool-white core bloom. Set false for
 *                  the tightest small-size rendering where the bloom would
 *                  collapse the icon into a blob.
 */
@Composable
fun MuseGlyph(
    size: Dp = 64.dp,
    showBloom: Boolean = true,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier.size(size)) {
        val w = this.size.width
        val h = this.size.height
        val centre = Offset(w / 2f, h / 2f)
        val extent = minOf(w, h) / 2f

        // Geometry mirrors the canonical viewBox-48 construction:
        //   ring r = 15 / 24 ≈ 0.625 of half-extent, stroke 1.6 / 24,
        //   core r = 3.1 / 24. dasharray "66 28" → a single gap.
        val ringRadius = extent * 0.625f
        val ringStroke = (extent * 0.105f).coerceAtLeast(1.4f)
        val coreRadius = (extent * 0.13f).coerceAtLeast(1.2f)

        // --- Core bloom: stacked cool-white radial halos (core ONLY). ---
        // Wide-faint edge → mid → tight bright center, then a high-emissive
        // core punch so it blazes like a real light source. Deterministic;
        // no renderer-specific filters.
        if (showBloom) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(BloomEdge.copy(alpha = 0.18f), Color.Transparent),
                    center = centre,
                    radius = extent * 0.95f,
                ),
                radius = extent * 0.95f,
                center = centre,
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(BloomMid.copy(alpha = 0.32f), Color.Transparent),
                    center = centre,
                    radius = extent * 0.55f,
                ),
                radius = extent * 0.55f,
                center = centre,
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(BloomInner.copy(alpha = 0.85f), Color.Transparent),
                    center = centre,
                    radius = coreRadius * 2.4f,
                ),
                radius = coreRadius * 2.4f,
                center = centre,
            )
        }

        // --- Matte spectral ring with a single gap, rotated -32°. ---
        // Drawn as an arc (the gap = the missing sweep). Left→right
        // cyan→violet linear gradient, round caps. NO glow.
        rotate(degrees = -32f, pivot = centre) {
            val topLeft = Offset(centre.x - ringRadius, centre.y - ringRadius)
            val ringSize = androidx.compose.ui.geometry.Size(ringRadius * 2f, ringRadius * 2f)
            // "66 28" dash on a ~96-unit circumference scale → ~70% drawn arc.
            val sweep = 360f * (66f / (66f + 28f))
            drawArc(
                brush = Brush.linearGradient(
                    colors = listOf(JarvisCyan, JarvisViolet),
                    start = topLeft,
                    end = Offset(topLeft.x + ringSize.width, topLeft.y + ringSize.height),
                ),
                startAngle = -90f,
                sweepAngle = sweep,
                useCenter = false,
                topLeft = topLeft,
                size = ringSize,
                style = Stroke(width = ringStroke, cap = StrokeCap.Round),
            )
        }

        // --- The incandescent core: the single brightest point. ---
        drawCircle(
            color = JarvisGold,
            radius = coreRadius,
            center = centre,
        )
    }
}
