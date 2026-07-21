package com.aci.hermes.data.devicecontrol

import com.aci.hermes.data.automation.AutomationIntent

/**
 * The discrete device capabilities the owner consents to (and the OS
 * grants) before muse can operate the phone. These map onto the
 * permissions the personal-tool fork already declares in the manifest —
 * this enum does not add new permissions, it makes consent for each one
 * explicit, explainable, and revocable from the cockpit.
 *
 * Pure data: no Android types, so the broker and its tests share one shape
 * (mirrors the `data/automation` / `data/jarvis` pure-logic convention).
 */
enum class DeviceControlCapability(
    /** Stable id used for persistence (DataStore string-set) and logging. */
    val id: String,
    /** Short title shown on the consent row. */
    val title: String,
    /** Plain-English reason, shown before the owner enables it. */
    val explanation: String,
) {
    ACCESSIBILITY(
        id = "accessibility",
        title = "Accessibility — Jarvis' hands",
        explanation = "Lets Jarvis read the screen and perform real taps, swipes, and app " +
            "launches on your behalf. Required for any on-screen action.",
    ),
    OVERLAY(
        id = "overlay",
        title = "Display over other apps",
        explanation = "Lets the floating Jarvis avatar appear over other apps and show what " +
            "it is about to do while it acts.",
    ),
    MICROPHONE(
        id = "microphone",
        title = "Microphone — hands-free voice",
        explanation = "Lets you talk to Jarvis hands-free. Audio is processed by your device's " +
            "speech recognizer; Jarvis never records or uploads audio itself.",
    ),
    NOTIFICATIONS(
        id = "notifications",
        title = "Notifications",
        explanation = "Lets Jarvis post status, action previews, and approval prompts so you " +
            "stay aware of what it is doing.",
    ),
    PACKAGE_VISIBILITY(
        id = "package_visibility",
        title = "Installed-app visibility",
        explanation = "Lets Jarvis resolve a spoken app name (\"open Facebook\") to the right " +
            "installed app so it launches the one you meant.",
    ),
    BACKEND_CONNECTION(
        id = "backend",
        title = "Local backend connection",
        explanation = "Lets the cockpit reach your muse backend (orchestration, memory, " +
            "worker lanes). Device actions stay on-device; this is for full cockpit power.",
    );

    companion object {
        fun fromId(id: String): DeviceControlCapability? = entries.firstOrNull { it.id == id }

        /**
         * The capabilities a device-driving [intent] needs before it can run.
         * Every intent is performed by the accessibility service, so
         * [ACCESSIBILITY] is the hard gate; launching an app additionally
         * needs [PACKAGE_VISIBILITY] to resolve the name to a package.
         */
        fun requiredFor(intent: AutomationIntent): Set<DeviceControlCapability> = when (intent) {
            is AutomationIntent.OpenApp -> setOf(ACCESSIBILITY, PACKAGE_VISIBILITY)
            is AutomationIntent.PushTarget,
            is AutomationIntent.TurnPage,
            is AutomationIntent.Scroll,
            is AutomationIntent.Navigate -> setOf(ACCESSIBILITY)
        }
    }
}
