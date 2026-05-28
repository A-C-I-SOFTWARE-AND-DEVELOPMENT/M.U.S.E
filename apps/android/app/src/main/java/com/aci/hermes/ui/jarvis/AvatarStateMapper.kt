package com.aci.hermes.ui.jarvis

import androidx.annotation.StringRes

/**
 * Render specification for the living avatar.
 *
 * Resolved by [AvatarStateMapper] from one [IconStateInputs]
 * snapshot, the operator's current activity hint
 * ([AvatarActivity]), and the device's reduce-motion setting.
 *
 * `iconState` and `appearance` come straight from the existing icon
 * state machine (`IconStateMapper`, `JarvisIconColors`) — the avatar
 * layer never re-invents the icon's safety contract. It only adds:
 *  - the activity overlay (status text),
 *  - the reduced-motion override.
 */
data class AvatarRenderSpec(
    val iconState: IconState,
    val appearance: IconAppearance,
    val activity: AvatarActivity,
    @StringRes val statusStringResId: Int,
    val reducedMotion: Boolean,
) {
    /**
     * Pulse amplitude to use when rendering. Returns `0f` whenever
     * the device requested reduced motion, no matter what the icon's
     * appearance says — the appearance recipe drives the *resting*
     * visual; this property gates the *animated* visual.
     */
    val effectivePulseAmplitude: Float
        get() = if (reducedMotion) 0f else appearance.pulseAmplitude
}

/**
 * Pure, side-effect-free collapse of `(IconStateInputs, AvatarActivity,
 * reducedMotion) → AvatarRenderSpec`.
 *
 * Precedence — the **safety floor wins**:
 *   1. If `IconStateMapper.map(inputs)` returns one of the high-priority
 *      safety states (CRITICAL_ACTION_PENDING, SERIOUS_ACTION_PENDING,
 *      WAITING_FOR_APPROVAL, BLOCKED, OFFLINE, WARNING), the activity
 *      hint is *ignored* for color/iconography and the status text
 *      mirrors the icon state. The operator must always see the
 *      safety-relevant signal first.
 *   2. Otherwise, if the inputs already collapse to a non-IDLE state
 *      (LISTENING, THINKING, SPEAKING, WORKING, COMPLETE), the inputs
 *      win — the operator's actual session state is more trustworthy
 *      than the activity hint.
 *   3. Only when the inputs collapse to IDLE does the activity hint
 *      drive the icon state.
 *
 * For Coding / Testing (refinements of Working), the activity hint
 * survives as long as the inputs allow WORKING — the operator gets
 * the more specific status text.
 */
object AvatarStateMapper {

    /** Icon states that always override an activity hint. */
    private val SAFETY_FLOOR: Set<IconState> = setOf(
        IconState.CRITICAL_ACTION_PENDING,
        IconState.SERIOUS_ACTION_PENDING,
        IconState.WAITING_FOR_APPROVAL,
        IconState.BLOCKED,
        IconState.OFFLINE,
        IconState.WARNING,
    )

    fun map(
        inputs: IconStateInputs,
        activity: AvatarActivity = AvatarActivity.Idle,
        reducedMotion: Boolean = false,
    ): AvatarRenderSpec {
        val inputsState = IconStateMapper.map(inputs)
        val effectiveState = when {
            inputsState in SAFETY_FLOOR -> inputsState
            inputsState != IconState.IDLE -> inputsState
            else -> activity.toIconState()
        }
        val effectiveActivity = when (effectiveState) {
            IconState.BLOCKED -> AvatarActivity.Blocked
            IconState.WAITING_FOR_APPROVAL,
            IconState.SERIOUS_ACTION_PENDING,
            IconState.CRITICAL_ACTION_PENDING -> AvatarActivity.WaitingForApproval
            IconState.LISTENING,
            IconState.SPEAKING -> AvatarActivity.Talking
            IconState.THINKING -> AvatarActivity.Thinking
            IconState.WORKING -> when (activity) {
                AvatarActivity.Coding, AvatarActivity.Testing -> activity
                else -> AvatarActivity.Working
            }
            IconState.OFFLINE,
            IconState.WARNING -> AvatarActivity.Blocked
            IconState.IDLE, IconState.COMPLETE -> AvatarActivity.Idle
        }
        return AvatarRenderSpec(
            iconState = effectiveState,
            appearance = JarvisIconColors.appearanceFor(effectiveState),
            activity = effectiveActivity,
            statusStringResId = effectiveActivity.statusStringResId,
            reducedMotion = reducedMotion,
        )
    }
}
