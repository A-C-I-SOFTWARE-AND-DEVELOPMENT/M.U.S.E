package com.aci.hermes.safety

/**
 * The full set of Android runtime permissions Jarvis Prime is allowed to
 * request in Phase 1. SMS and Call Log are deliberately absent and
 * declared out-of-scope by product policy.
 *
 * Each permission carries a human-readable purpose surfaced in the
 * education sheet — the system dialog only appears after the user has
 * read the purpose and tapped "Continue".
 */
enum class JarvisPermission(
    val manifestName: String,
    val purpose: String,
    val trigger: String,
) {
    NOTIFICATIONS(
        manifestName = "android.permission.POST_NOTIFICATIONS",
        purpose = "Show the persistent Jarvis Prime status notification while the gateway is running, and surface approvals you have requested.",
        trigger = "After you turn on the Jarvis Prime gateway from the dashboard.",
    ),
    MICROPHONE(
        manifestName = "android.permission.RECORD_AUDIO",
        purpose = "Capture voice input while you hold the talk control. Jarvis Prime never listens in the background and is not an always-on assistant.",
        trigger = "After you tap and hold the voice control for the first time.",
    );

    companion object {
        /** Permissions never declared. Surfaced for tests and policy auditing. */
        val phase1Banned: List<String> = listOf(
            "android.permission.READ_SMS",
            "android.permission.SEND_SMS",
            "android.permission.RECEIVE_SMS",
            "android.permission.READ_CALL_LOG",
            "android.permission.WRITE_CALL_LOG",
            "android.permission.SYSTEM_ALERT_WINDOW",
        )
    }
}
