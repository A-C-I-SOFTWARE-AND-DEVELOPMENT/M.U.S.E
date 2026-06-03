package com.aci.hermes.ui.screens.live

import android.graphics.Bitmap
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.foundation.shape.CircleShape

/**
 * A **living photo avatar** — the user's own picture, gently *breathing* (a
 * subtle scale pulse whose tempo/amplitude track [AvatarInputs.energy]) so it
 * reads as alive, not a static headshot. Holds still when motion is disabled
 * (reduced motion / sleep). This is what turns a "Choose photo" upload into a
 * real, animated JARVIS face.
 */
@Composable
fun JarvisPhotoAvatar(
    photo: Bitmap,
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val periodMs = (1600 - inputs.energy * 1000f).toInt().coerceAtLeast(500)
    val transition = rememberInfiniteTransition(label = "photo-breath")
    val breath by transition.animateFloat(
        initialValue = 1f,
        targetValue = 1f + 0.04f * (0.3f + inputs.energy),
        animationSpec = infiniteRepeatable(
            animation = tween(periodMs, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "photo-scale",
    )
    val applied = if (inputs.motionEnabled) breath else 1f

    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Image(
            bitmap = photo.asImageBitmap(),
            contentDescription = contentDescription,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .fillMaxSize()
                .scale(applied)
                .clip(CircleShape),
        )
    }
}
