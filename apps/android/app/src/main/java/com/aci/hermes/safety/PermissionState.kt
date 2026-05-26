package com.aci.hermes.safety

/**
 * State machine for a single Jarvis Prime permission.
 *
 *   NOT_REQUESTED         → no prompt has ever been shown.
 *   EDUCATION_PENDING     → user opened the entry point, education sheet
 *                            is queued but they have not tapped Continue.
 *   SYSTEM_PROMPT_PENDING → user accepted the education and the OS dialog
 *                            is open / waiting for their decision.
 *   GRANTED               → OS reports the permission is granted.
 *   DENIED                → OS reports the permission was denied. Jarvis
 *                            Prime degrades gracefully and never auto-retries.
 *   PERMANENTLY_DENIED    → user denied with "Don't ask again". The app
 *                            must route them to system Settings if they
 *                            change their mind, never re-prompt directly.
 */
enum class PermissionState {
    NOT_REQUESTED,
    EDUCATION_PENDING,
    SYSTEM_PROMPT_PENDING,
    GRANTED,
    DENIED,
    PERMANENTLY_DENIED;

    val isGranted: Boolean get() = this == GRANTED

    /**
     * True only when Jarvis Prime is permitted to invoke the OS request
     * flow without education — i.e. the kernel previously surfaced the
     * education sheet for this state transition.
     */
    val canInvokeSystemDialog: Boolean
        get() = this == SYSTEM_PROMPT_PENDING
}
