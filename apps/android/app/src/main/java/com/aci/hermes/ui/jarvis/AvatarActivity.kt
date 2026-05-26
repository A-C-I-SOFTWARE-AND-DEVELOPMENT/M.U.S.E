package com.aci.hermes.ui.jarvis

import androidx.annotation.StringRes
import com.aci.hermes.R

/**
 * Finer-grained "what is Jarvis doing right now?" overlay on top of
 * [IconState]. The icon's [IconState] is the safety-relevant signal
 * (which color/ring to show); [AvatarActivity] is the
 * presence-relevant signal (what plain-language status text to show
 * the operator).
 *
 * Mapping to [IconState] (see [AvatarStateMapper] for the full
 * collapse rule):
 *  - [Idle]               → [IconState.IDLE]
 *  - [Thinking]           → [IconState.THINKING]
 *  - [Talking]            → [IconState.SPEAKING]
 *  - [Working]            → [IconState.WORKING]
 *  - [Coding]             → [IconState.WORKING]  (refinement)
 *  - [Testing]            → [IconState.WORKING]  (refinement)
 *  - [Blocked]            → [IconState.BLOCKED]
 *  - [WaitingForApproval] → [IconState.WAITING_FOR_APPROVAL]
 *
 * The mapper resolves precedence so a critical safety state
 * (CRITICAL_ACTION_PENDING, BLOCKED) always wins over a lower-priority
 * activity hint.
 */
enum class AvatarActivity {
    Idle,
    Thinking,
    Talking,
    Working,
    Coding,
    Testing,
    Blocked,
    WaitingForApproval;

    /**
     * R.string resource id of the plain-language status string for
     * this activity. Resolves via the Compose layer with
     * [androidx.compose.ui.res.stringResource].
     */
    @get:StringRes
    val statusStringResId: Int
        get() = when (this) {
            Idle -> R.string.avatar_status_idle
            Thinking -> R.string.avatar_status_thinking
            Talking -> R.string.avatar_status_talking
            Working -> R.string.avatar_status_working
            Coding -> R.string.avatar_status_coding
            Testing -> R.string.avatar_status_testing
            Blocked -> R.string.avatar_status_blocked
            WaitingForApproval -> R.string.avatar_status_waiting_for_approval
        }
}

/**
 * Maps an [AvatarActivity] to the [IconState] it implies. Used by
 * [AvatarStateMapper] when no higher-priority safety signal is set.
 */
fun AvatarActivity.toIconState(): IconState = when (this) {
    AvatarActivity.Idle -> IconState.IDLE
    AvatarActivity.Thinking -> IconState.THINKING
    AvatarActivity.Talking -> IconState.SPEAKING
    AvatarActivity.Working -> IconState.WORKING
    AvatarActivity.Coding -> IconState.WORKING
    AvatarActivity.Testing -> IconState.WORKING
    AvatarActivity.Blocked -> IconState.BLOCKED
    AvatarActivity.WaitingForApproval -> IconState.WAITING_FOR_APPROVAL
}
