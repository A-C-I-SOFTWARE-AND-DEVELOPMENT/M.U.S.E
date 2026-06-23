package com.aci.hermes.ui.screens.live

import android.graphics.Bitmap
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext

/**
 * Renders whichever living-avatar body is active, given a renderer-
 * neutral [AvatarInputs]. This is the single switchboard the Jarvis Live
 * screen and the floating overlay both use, so the renderer choice and
 * the fallback ladder live in exactly one place.
 *
 * All "alive" kinds are drawn with self-contained Compose renderers
 * today: [JarvisPixelAvatar] (the default body, an animated sprite) and
 * [JarvisCharacterAvatar] (a procedural humanoid). The [AvatarKind.Rive]
 * and [AvatarKind.Character3D] kinds map to the procedural character for
 * now — a finished Rive/3D body drops in here later against the same
 * [AvatarInputs] contract. Fallbacks degrade gracefully and anything the
 * device can't drive has already been collapsed by
 * [DeviceCapability.effectiveKind] before it reaches here.
 */
@Composable
fun LivingAvatarHost(
    kind: AvatarKind,
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
    spriteSheet: Bitmap? = null,
    spriteLayout: SpriteSheetLayout? = null,
    photo: Bitmap? = null,
) {
    when (kind) {
        AvatarKind.AnimatedPixel ->
            if (spriteSheet != null && spriteLayout != null) {
                JarvisPixelAvatar(spriteSheet, spriteLayout, inputs, contentDescription, modifier)
            } else {
                JarvisCharacterAvatar(inputs, contentDescription, modifier)
            }

        // Rive: real animated art when a `res/raw/jarvis.riv` honoring the
        // JarvisStateMachine contract is shipped; otherwise the procedural body.
        AvatarKind.Rive -> {
            val context = LocalContext.current
            val hasRive = remember { riveAvatarAvailable(context) }
            if (hasRive) {
                JarvisRiveAvatar(inputs, contentDescription, modifier)
            } else {
                JarvisCharacterAvatar(inputs, contentDescription, modifier)
            }
        }

        // 3D body is served by the procedural character until finished art
        // lands (same input contract, zero call-site change).
        AvatarKind.Character3D ->
            JarvisCharacterAvatar(inputs, contentDescription, modifier)

        // A user-uploaded photo becomes a living, breathing avatar face.
        AvatarKind.Photo ->
            if (photo != null) {
                JarvisPhotoAvatar(photo, inputs, contentDescription, modifier)
            } else {
                JarvisLivingAvatar(
                    state = poseToLegacyState(inputs.pose),
                    motionEnabled = inputs.motionEnabled,
                    contentDescription = contentDescription,
                    modifier = modifier,
                )
            }

        // Orb / Pixel keep the original abstract renderer as the calm,
        // low-cost, reduced-motion-safe body.
        AvatarKind.Orb, AvatarKind.Pixel ->
            JarvisLivingAvatar(
                state = poseToLegacyState(inputs.pose),
                motionEnabled = inputs.motionEnabled,
                contentDescription = contentDescription,
                modifier = modifier,
            )
    }
}

/** The overlay window's content: the alive body, sized for the bubble. */
@Composable
fun JarvisOverlayContent(inputs: AvatarInputs) {
    LivingAvatarHost(
        kind = AvatarKind.Rive,
        inputs = inputs,
        contentDescription = "muse",
    )
}

/** Bridge new poses back onto the legacy 8-state orb palette. */
private fun poseToLegacyState(pose: AvatarPose): JarvisLiveState = when (pose) {
    AvatarPose.LISTEN -> JarvisLiveState.Listening
    AvatarPose.THINK -> JarvisLiveState.Thinking
    AvatarPose.WORK, AvatarPose.RUN, AvatarPose.PUSH, AvatarPose.PAGE_TURN,
    AvatarPose.SCROLL, AvatarPose.POINT,
    -> JarvisLiveState.Working
    AvatarPose.SPEAK, AvatarPose.RECOMMEND -> JarvisLiveState.Speaking
    AvatarPose.APPROVE -> JarvisLiveState.ApprovalNeeded
    AvatarPose.BLOCKED -> JarvisLiveState.Blocked
    AvatarPose.EMERGENCY -> JarvisLiveState.EmergencyStop
    AvatarPose.IDLE, AvatarPose.WANDER, AvatarPose.SLEEP, AvatarPose.WAKE -> JarvisLiveState.Idle
}
