package com.aci.hermes.ui.screens.live

import android.graphics.Bitmap
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.Paint
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp

/**
 * The 2D pixel-art character. Renders one row of a sprite sheet, where
 * each row is an [AvatarPose] animation and each column a frame. Frames
 * advance on an infinite transition whose speed scales with
 * [AvatarInputs.energy]. Nearest-neighbor sampling keeps the pixels
 * crisp (no blur), matching the avatar picker's existing look.
 *
 * The sheet is produced on-device by [com.aci.hermes.data.avatar.AvatarPixelator]
 * from the user's uploaded image (WS-A image→avatar conversion).
 */
@Composable
fun JarvisPixelAvatar(
    sheet: Bitmap,
    layout: SpriteSheetLayout,
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val row = layout.rowFor(inputs.pose)
    val frameCount = layout.frameCount.coerceAtLeast(1)
    val animate = inputs.motionEnabled && frameCount > 1

    val transition = rememberInfiniteTransition(label = "jarvis-pixel")
    val progress by transition.animateFloat(
        initialValue = 0f,
        targetValue = if (animate) frameCount.toFloat() else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(framePeriodMs(inputs.energy) * frameCount, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "jarvis-pixel-frame",
    )
    val frame = progress.toInt().coerceIn(0, frameCount - 1)
    val image = remember(sheet) { sheet.asImageBitmap() }

    Canvas(
        modifier = modifier
            .size(220.dp)
            .semantics { this.contentDescription = contentDescription },
    ) {
        val fw = layout.frameWidth
        val fh = layout.frameHeight
        drawIntoCanvas { canvas ->
            canvas.drawImageRect(
                image = image,
                srcOffset = IntOffset(frame * fw, row * fh),
                srcSize = IntSize(fw, fh),
                dstOffset = IntOffset(0, 0),
                dstSize = IntSize(size.width.toInt(), size.height.toInt()),
                paint = Paint().apply { filterQuality = FilterQuality.None },
            )
        }
    }
}

/** Geometry of a uniform sprite sheet: rows = poses, columns = frames. */
data class SpriteSheetLayout(
    val frameWidth: Int,
    val frameHeight: Int,
    val frameCount: Int,
    /** Pose → row index. Falls back to row 0 for unmapped poses. */
    val poseRows: Map<AvatarPose, Int>,
) {
    fun rowFor(pose: AvatarPose): Int = poseRows[pose] ?: 0
}

/** Faster frames at higher energy: ~70ms (hot) … ~200ms (calm/sleep). */
private fun framePeriodMs(energy: Float): Int =
    (200 - (energy.coerceIn(0f, 1f) * 130)).toInt().coerceAtLeast(60)
