package com.aci.hermes.data.cockpit

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Kotlin mirror of the device-pairing API
 * (`POST /v1/cockpit/pair/start` and `POST /v1/cockpit/pair/confirm`,
 * backed by `gateway/cockpit/device_pairing.py` via `handlers.pair_start` /
 * `handlers.pair_confirm`).
 *
 * Pairing is the one flow that runs *before* the cockpit holds a bearer
 * token: `pair/start` mints a short-lived code, and `pair/confirm` exchanges
 * that code (plus the exact owner authorization phrase) for a fresh
 * per-device token that is returned exactly once. Nothing here makes network
 * calls or carries provider secrets — [DevicePairingClient] performs the
 * transport, and the only secret the phone ever stores is the device token,
 * persisted through [com.aci.hermes.data.preferences.SecureTokenStore].
 *
 * One-to-one with the JSON shapes the gateway returns; absent fields stay at
 * their declared defaults under the tolerant [CockpitHttp.json] decoder.
 */

/**
 * Response of `POST /v1/cockpit/pair/start` (HTTP 201).
 *
 * [expiresAt] is the epoch (seconds, may be fractional) at which the code
 * stops being accepted; [expiresIn] is the code's TTL in whole seconds
 * (`device_pairing.CODE_TTL_SECONDS`). A refusal (rate-limited / locked out /
 * too many pending codes) is a `429` [CockpitResult.Failure], never a
 * fabricated code.
 */
@Serializable
data class PairingStart(
    @SerialName("pairing_code") val pairingCode: String,
    @SerialName("expires_at") val expiresAt: Double = 0.0,
    @SerialName("expires_in") val expiresIn: Int = 0,
)

/**
 * POST body for `pair/start`. [deviceName] is an optional human label for the
 * device record (e.g. "Jeremiah's Pixel"); the gateway treats a blank name as
 * absent.
 */
@Serializable
data class PairingStartRequest(
    @SerialName("device_name") val deviceName: String? = null,
)

/**
 * Response of `POST /v1/cockpit/pair/confirm` (HTTP 201). The raw [token] is
 * returned exactly once — the gateway keeps only its hash — so the client
 * persists it immediately and never logs it. [tokenType] is `"Bearer"`.
 */
@Serializable
data class PairingConfirm(
    @SerialName("device_id") val deviceId: String,
    val token: String,
    @SerialName("token_type") val tokenType: String = "Bearer",
)

/**
 * POST body for `pair/confirm`. Issuing a device token is owner-gated: the
 * gateway returns `403` unless [authorization] equals the exact owner phrase,
 * so a process that can merely reach the loopback pairing route cannot
 * self-issue a credential. A bad/expired [pairingCode] is a `401`.
 */
@Serializable
data class PairingConfirmRequest(
    @SerialName("pairing_code") val pairingCode: String,
    val authorization: String? = null,
)
