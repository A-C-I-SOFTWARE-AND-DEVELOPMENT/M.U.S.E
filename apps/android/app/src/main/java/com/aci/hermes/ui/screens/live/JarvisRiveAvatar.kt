package com.aci.hermes.ui.screens.live

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import app.rive.runtime.kotlin.compose.Rive
import app.rive.runtime.kotlin.controllers.RiveFileController
import app.rive.runtime.kotlin.core.Fit

/**
 * The primary "truly alive" Jarvis body: a Rive vector character driven
 * by a single state machine. We never swap animations imperatively from
 * Kotlin — we set state-machine inputs and let the artboard blend
 * between idle / run / push / page-turn / sleep, which is what makes the
 * motion read as continuous and lifelike.
 *
 * Input contract (see `docs/avatar/rive-state-contract.md`):
 *  - number input `pose`   ← [AvatarPose.ordinal]
 *  - number input `energy` ← 0..100 (from [AvatarInputs.energy])
 *  - boolean input `motion`← [AvatarInputs.motionEnabled]
 *
 * The placeholder `R.raw.jarvis` artboard ships these inputs so the app
 * runs end-to-end; swapping in finished art needs zero Kotlin changes.
 */
@Composable
fun JarvisRiveAvatar(
    inputs: AvatarInputs,
    contentDescription: String,
    modifier: Modifier = Modifier,
    artboardResId: Int = DEFAULT_ARTBOARD,
    stateMachineName: String = STATE_MACHINE,
) {
    val controller = remember { RiveFileController() }

    LaunchedEffect(inputs) {
        runCatching {
            controller.setNumberState(stateMachineName, INPUT_POSE, inputs.pose.ordinal.toFloat())
            controller.setNumberState(stateMachineName, INPUT_ENERGY, inputs.energy * 100f)
            controller.setBooleanState(stateMachineName, INPUT_MOTION, inputs.motionEnabled)
        }
    }

    Rive(
        fileSource = artboardResId,
        controller = controller,
        fit = Fit.CONTAIN,
        stateMachineName = stateMachineName,
        autoplay = true,
        modifier = modifier.semantics { this.contentDescription = contentDescription },
    )
}

private const val DEFAULT_ARTBOARD: Int = com.aci.hermes.R.raw.jarvis
private const val STATE_MACHINE = "JarvisStateMachine"
private const val INPUT_POSE = "pose"
private const val INPUT_ENERGY = "energy"
private const val INPUT_MOTION = "motion"
