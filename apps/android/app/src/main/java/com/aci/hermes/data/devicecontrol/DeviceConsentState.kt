package com.aci.hermes.data.devicecontrol

/**
 * The owner's current device-control consent. Pure data so the broker
 * decision is unit-testable without Android.
 *
 * - [enabled]: the master switch. Until the owner explicitly turns this
 *   on, no device action runs — defaults to off so a fresh install has
 *   device control dormant.
 * - [consentedCapabilities]: the per-capability switches the owner has
 *   turned on. The broker requires a capability to be *both* consented
 *   here and granted by the OS before it will act.
 * - [confirmSensitiveActions]: when true (the default), **SENSITIVE** actions
 *   (launching an app, tapping a target) are never auto-run — they need an
 *   explicit confirmation. The owner can disable this (an owner-gated, high
 *   power choice) so sensitive actions execute immediately; every action is
 *   still logged either way. This toggle governs SENSITIVE actions **only** —
 *   it can never disable confirmation for [DeviceActionSensitivity.IRREVERSIBLE]
 *   actions, which the broker floors unconditionally.
 */
data class DeviceConsentState(
    val enabled: Boolean = false,
    val consentedCapabilities: Set<DeviceControlCapability> = emptySet(),
    val confirmSensitiveActions: Boolean = true,
) {
    fun hasConsented(capability: DeviceControlCapability): Boolean =
        capability in consentedCapabilities
}
