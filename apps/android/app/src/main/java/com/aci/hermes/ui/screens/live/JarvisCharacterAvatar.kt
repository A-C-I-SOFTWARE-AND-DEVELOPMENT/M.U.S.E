package com.aci.hermes.ui.screens.live

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.HermesCrimson
import com.aci.hermes.ui.theme.HermesCyan
import com.aci.hermes.ui.theme.HermesGold
import com.aci.hermes.ui.theme.HermesGoldDeep
import com.aci.hermes.ui.theme.HermesViolet
import kotlin.math.sin

/**
 * The default living JARVIS body — a self-contained procedural
 * character drawn with Compose Canvas (no third-party runtime). It
 * reads the renderer-neutral [AvatarInputs] and animates a small
 * humanoid: a glowing core/head, a torso, and four limbs that swing
 * for [AvatarPose.RUN], reach for [AvatarPose.PUSH], curl for
 * [AvatarPose.SLEEP], etc.
 *
 * This is deliberately art-light but genuinely alive (limb motion,
 * breathing, energy-scaled tempo, state-colored aura) and depends only
 * on Compose APIs the app already uses, so it compiles and runs without
 * any external avatar SDK. A finished Rive/3D body drops in behind
 * [LivingAvatarHost] later against the same [AvatarInputs] contract
 * (see `docs/avatar/rive-state-contract.md`).
 */
@Composable
fun JarvisCharacterAvatar(
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val palette = characterPalette(inputs.pose)
    val transition = rememberInfiniteTransition(label = "jarvis-character")

    // One shared 0..1 phase; tempo scales with energy. Frozen when motion off.
    val periodMs = (1600 - (inputs.energy.coerceIn(0f, 1f) * 1100)).toInt().coerceAtLeast(420)
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = if (inputs.motionEnabled) (2f * Math.PI.toFloat()) else 0f,
        animationSpec = infiniteRepeatable(
            animation = tween(periodMs, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "jarvis-character-phase",
    )

    Box(
        modifier = modifier
            .size(220.dp)
            .semantics { this.contentDescription = contentDescription },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(220.dp)) {
            drawAura(palette, inputs, phase)
            drawFigure(palette, inputs, phase)
        }
    }
}

private data class CharacterPalette(val core: Color, val limb: Color, val aura: Color)

private fun DrawScope.drawAura(palette: CharacterPalette, inputs: AvatarInputs, phase: Float) {
    val center = Offset(size.width / 2f, size.height * 0.42f)
    val pulse = if (inputs.motionEnabled) 1f + 0.08f * sin(phase) else 1f
    val radius = size.minDimension * 0.42f * pulse
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(palette.aura.copy(alpha = 0.45f), Color.Transparent),
            center = center,
            radius = radius,
        ),
        radius = radius,
        center = center,
    )
}

/**
 * A stick-and-glow humanoid. Limb angles are derived from the pose so
 * RUN swings the arms/legs out of phase, PUSH extends one arm forward,
 * SLEEP collapses the figure, etc.
 */
private fun DrawScope.drawFigure(palette: CharacterPalette, inputs: AvatarInputs, phase: Float) {
    val cx = size.width / 2f
    val unit = size.minDimension
    val headR = unit * 0.10f
    val sleeping = inputs.pose == AvatarPose.SLEEP

    val headY = if (sleeping) size.height * 0.55f else size.height * 0.30f
    val hipY = headY + unit * (if (sleeping) 0.10f else 0.32f)
    val shoulderY = headY + headR + unit * 0.04f

    // Head + core glow.
    drawCircle(
        brush = Brush.radialGradient(
            listOf(palette.core, palette.core.copy(alpha = 0.15f)),
            center = Offset(cx, headY),
            radius = headR * 1.4f,
        ),
        radius = headR,
        center = Offset(cx, headY),
    )

    val limbStroke = Stroke(width = unit * 0.035f, cap = StrokeCap.Round)

    // Spine.
    drawLine(palette.limb, Offset(cx, headY + headR), Offset(cx, hipY), limbStroke.width, StrokeCap.Round)

    val swing = if (inputs.motionEnabled) sin(phase) else 0f
    val (armSwing, legSwing) = limbMotion(inputs.pose, swing)

    val armLen = unit * 0.20f
    val legLen = unit * 0.24f

    // Arms — for PUSH, the lead arm reaches forward (toward +x).
    val push = inputs.pose == AvatarPose.PUSH || inputs.pose == AvatarPose.PAGE_TURN
    val leadArmAngle = if (push) 0.05f else armSwing
    drawLine(
        palette.limb,
        Offset(cx, shoulderY),
        Offset(cx + armLen * (if (push) 1.1f else 0.7f), shoulderY + armLen * leadArmAngle),
        limbStroke.width, StrokeCap.Round,
    )
    drawLine(
        palette.limb,
        Offset(cx, shoulderY),
        Offset(cx - armLen * 0.7f, shoulderY - armLen * armSwing),
        limbStroke.width, StrokeCap.Round,
    )

    // Legs — swing out of phase with the arms when running.
    drawLine(
        palette.limb,
        Offset(cx, hipY),
        Offset(cx + legLen * 0.5f, hipY + legLen + legLen * legSwing),
        limbStroke.width, StrokeCap.Round,
    )
    drawLine(
        palette.limb,
        Offset(cx, hipY),
        Offset(cx - legLen * 0.5f, hipY + legLen - legLen * legSwing),
        limbStroke.width, StrokeCap.Round,
    )
}

/** Returns (armSwing, legSwing) amplitudes for the active pose. */
private fun limbMotion(pose: AvatarPose, swing: Float): Pair<Float, Float> = when (pose) {
    AvatarPose.RUN -> 0.9f * swing to -0.9f * swing
    AvatarPose.WANDER -> 0.4f * swing to -0.4f * swing
    AvatarPose.WORK, AvatarPose.SCROLL -> 0.25f * swing to 0f
    AvatarPose.SLEEP -> 0f to 0f
    AvatarPose.RECOMMEND, AvatarPose.POINT -> 0.15f * swing to 0f
    else -> 0.18f * swing to -0.1f * swing
}

private fun characterPalette(pose: AvatarPose): CharacterPalette = when (pose) {
    AvatarPose.LISTEN, AvatarPose.SPEAK ->
        CharacterPalette(HermesCyan, HermesCyan, HermesCyan.copy(alpha = 0.5f))
    AvatarPose.THINK, AvatarPose.WORK, AvatarPose.RUN, AvatarPose.PUSH,
    AvatarPose.PAGE_TURN, AvatarPose.SCROLL, AvatarPose.POINT, AvatarPose.APPROVE,
    ->
        CharacterPalette(HermesGold, HermesGoldDeep, HermesViolet.copy(alpha = 0.5f))
    AvatarPose.BLOCKED, AvatarPose.EMERGENCY ->
        CharacterPalette(HermesCrimson, HermesCrimson, HermesCrimson.copy(alpha = 0.5f))
    AvatarPose.SLEEP ->
        CharacterPalette(HermesGoldDeep.copy(alpha = 0.5f), HermesGoldDeep.copy(alpha = 0.5f), HermesViolet.copy(alpha = 0.25f))
    AvatarPose.RECOMMEND ->
        CharacterPalette(HermesGold, HermesCyan, HermesGold.copy(alpha = 0.5f))
    AvatarPose.IDLE, AvatarPose.WANDER, AvatarPose.WAKE ->
        CharacterPalette(HermesGold.copy(alpha = 0.8f), HermesGoldDeep, HermesViolet.copy(alpha = 0.35f))
}
