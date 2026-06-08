package com.aci.hermes.data.emergency

import kotlinx.serialization.Serializable

/**
 * MUSE emergency stop levels. Each level raises the gate higher.
 *
 * - [INACTIVE]: nothing blocked.
 * - [SOFT_PAUSE]: no new task starts; in-flight work continues.
 * - [HARD_STOP]: blocks sends, deletes, pushes, deploys in the UI.
 * - [LOCKDOWN]: blocks all non-read-only actions except status, audit,
 *   export, and resume.
 *
 * Transitions are not free — escalating up is direct, returning to
 * [INACTIVE] always goes through the approval-gated resume flow.
 */
@Serializable
enum class EmergencyStopState {
    INACTIVE,
    SOFT_PAUSE,
    HARD_STOP,
    LOCKDOWN;

    val isActive: Boolean get() = this != INACTIVE

    /** Severity ordinal; higher means more restrictive. */
    val severity: Int get() = ordinal
}

/**
 * Kinds of actions the rest of the app asks the emergency stop layer
 * about before performing. Used by [EmergencyStopController.isBlocked].
 */
enum class GuardedAction {
    /** Starting a new task, agent run, or background job. */
    START_TASK,

    /** Pushing/sending generated output to an external tool. */
    SEND,

    /** Destructive UI state mutation (delete, clear, wipe). */
    DELETE,

    /** Outbound code push or PR creation. */
    PUSH,

    /** Triggering deploys, releases, or production rollouts. */
    DEPLOY,

    /** Any non-read-only mutation that is not one of the above. */
    MUTATE,

    /** Read-only inspection — never blocked. */
    READ,

    /** Status / audit / export — always allowed even in lockdown. */
    STATUS,
}
