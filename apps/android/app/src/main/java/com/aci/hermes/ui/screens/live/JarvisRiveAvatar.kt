package com.aci.hermes.ui.screens.live

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.viewinterop.AndroidView
import app.rive.runtime.kotlin.RiveAnimationView

/**
 * Top-tier animated avatar driven by a Rive state machine — data-driven, so
 * finished art drops in with zero Kotlin changes (see
 * `docs/avatar/rive-state-contract.md`). Maps the renderer-neutral
 * [AvatarInputs] onto the **`JarvisStateMachine`** inputs:
 *  - `pose`   (number) ← [AvatarPose.ordinal] (0–16)
 *  - `energy` (number) ← energy * 100 (0–100)
 *  - `motion` (boolean) ← motionEnabled
 *
 * The art lives at `res/raw/jarvis.riv`. Use [riveAvatarAvailable] to check
 * presence; callers fall back to a built-in body when the asset isn't shipped.
 */
private const val STATE_MACHINE = "JarvisStateMachine"

fun riveAvatarAvailable(context: Context): Boolean =
    context.resources.getIdentifier("jarvis", "raw", context.packageName) != 0

@Composable
fun JarvisRiveAvatar(
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val resId = remember {
        context.resources.getIdentifier("jarvis", "raw", context.packageName)
    }
    if (resId == 0) return

    AndroidView(
        modifier = modifier.semantics { this.contentDescription = contentDescription },
        factory = { ctx ->
            RiveAnimationView(ctx).apply {
                runCatching {
                    setRiveResource(resId, stateMachineName = STATE_MACHINE, autoplay = true)
                }
            }
        },
        update = { view ->
            runCatching {
                view.setNumberState(STATE_MACHINE, "pose", inputs.pose.ordinal.toFloat())
                view.setNumberState(STATE_MACHINE, "energy", inputs.energy.coerceIn(0f, 1f) * 100f)
                view.setBooleanState(STATE_MACHINE, "motion", inputs.motionEnabled)
            }
        },
    )
}
