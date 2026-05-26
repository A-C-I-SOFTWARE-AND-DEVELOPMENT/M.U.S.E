package com.aci.hermes.ui.components

/**
 * What Jarvis Prime's interactive icon is currently representing.
 *
 *   IDLE      → on watch, calm pulse in JarvisGold.
 *   LISTENING → mic is hot, JarvisCyan ripple.
 *   WORKING   → a worker is executing on the gateway, JarvisCyan rotation.
 *   ALERT     → an approval is waiting, JarvisGold steady ring.
 *   CRITICAL  → emergency stop engaged or a CRITICAL approval is open,
 *                JarvisRed steady fill.
 *
 * The icon never crosses tiers without a corresponding semantic event —
 * the [JarvisInteractiveIcon] composable is purely presentational.
 */
enum class JarvisIconState {
    IDLE,
    LISTENING,
    WORKING,
    ALERT,
    CRITICAL,
}
