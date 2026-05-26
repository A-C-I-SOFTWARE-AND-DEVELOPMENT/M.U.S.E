package com.aci.hermes.ui.components.icon

import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.accessibilityLabel

/**
 * Accessibility surface for the interactive icon. Defers the
 * user-readable label to [IconState.accessibilityLabel] (the single
 * source of truth) and adds a gesture-aware hint TalkBack announces as
 * the primary action.
 */

/** Stable, non-blank label for TalkBack `contentDescription`. */
fun IconState.semanticLabel(): String = accessibilityLabel()

/**
 * Hint TalkBack announces alongside the icon's primary `onClick`.
 * The hint is intentionally specific to the current state so the user
 * understands what `Tap` will do *right now*.
 */
fun IconState.semanticActionHint(): String = when (this) {
    IconState.WAITING_FOR_APPROVAL,
    IconState.SERIOUS_ACTION_PENDING,
    IconState.CRITICAL_ACTION_PENDING -> "Double-tap to review pending action"
    IconState.LISTENING -> "Double-tap to stop listening"
    IconState.BLOCKED -> "Double-tap for details"
    IconState.OFFLINE -> "Double-tap for status"
    else -> "Double-tap to open Jarvis"
}
