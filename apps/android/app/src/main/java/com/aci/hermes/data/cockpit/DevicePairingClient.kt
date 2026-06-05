package com.aci.hermes.data.cockpit

import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.json.Json

/**
 * Live client for the cockpit device-pairing handshake
 * (`POST /v1/cockpit/pair/start` → code, `POST /v1/cockpit/pair/confirm` →
 * per-device token). It is the pre-auth sibling of [HermesCockpitClient]:
 * pairing is the one flow that runs *before* a bearer token exists, so these
 * two routes are called with no `Authorization` header.
 *
 * It reuses the exact transport contract the rest of the cockpit surface is
 * built on — [CockpitHttpExecutor] (injected so the request/response mapping
 * is unit-tested without a socket), [CockpitHttp.json] (tolerant decoding),
 * [CockpitHttp.parseError] (the typed error envelope), and the
 * [CockpitResult] outcome (`Success` / `Failure` / `Unreachable`). The
 * endpoint is read through a provider, not captured at construction, so the
 * client picks up *Settings → Connection* changes without being rebuilt.
 *
 * On a successful confirm the raw device token (returned by the gateway
 * exactly once) is persisted through [SettingsRepository.setCockpitToken] —
 * the *same* path every other "pair a gateway" flow uses. That setter writes
 * the encrypted-at-rest store **and** updates the in-memory `cockpitToken`
 * StateFlow that [HermesCockpitClient] reads its bearer from (mirrored into
 * [com.aci.hermes.di.AppContainer]'s token cache); persisting straight to
 * [com.aci.hermes.data.preferences.SecureTokenStore] would leave that cache
 * `null` until the process is recreated, so authenticated calls would still
 * fail with "Not paired" right after a successful confirm. The token is never
 * logged.
 */
class DevicePairingClient(
    private val endpointProvider: () -> String,
    private val settingsRepository: SettingsRepository,
    private val executor: CockpitHttpExecutor = JdkHttpExecutor,
    private val json: Json = CockpitHttp.json,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) {

    /**
     * Begin pairing: ask the gateway to mint a short-lived code. [deviceName]
     * is an optional human label; a blank name is sent as absent. A `429`
     * [CockpitResult.Failure] means pairing is temporarily unavailable
     * (rate-limited / locked out / too many pending codes) — honest, never a
     * fabricated code.
     */
    suspend fun startPairing(deviceName: String? = null): CockpitResult<PairingStart> =
        request(
            path = "/v1/cockpit/pair/start",
            deserializer = PairingStart.serializer(),
            body = json.encodeToString(
                PairingStartRequest.serializer(),
                PairingStartRequest(deviceName = deviceName?.takeIf { it.isNotBlank() }),
            ),
        )

    /**
     * Confirm a pairing [code] and exchange it for the per-device token.
     * Issuing a token is owner-gated, so [authorization] must equal the exact
     * owner phrase ([OWNER_AUTHORIZATION_PHRASE]) — the gateway returns `403`
     * otherwise; a bad/expired code is a `401`. On success the raw token
     * (returned by the gateway exactly once) is persisted through
     * [SettingsRepository.setCockpitToken] — which writes the encrypted store
     * *and* updates the in-memory `cockpitToken` StateFlow the live client
     * reads — before the result is handed back, so the very next authenticated
     * call is already paired.
     */
    suspend fun confirmPairing(
        code: String,
        authorization: String? = null,
    ): CockpitResult<PairingConfirm> {
        val result = request(
            path = "/v1/cockpit/pair/confirm",
            deserializer = PairingConfirm.serializer(),
            body = json.encodeToString(
                PairingConfirmRequest.serializer(),
                PairingConfirmRequest(pairingCode = code, authorization = authorization),
            ),
        )
        if (result is CockpitResult.Success) {
            // The raw token is handed back exactly once — persist it through the
            // repository so secure storage AND the in-memory source the live
            // client reads from both update (no double-write: setCockpitToken
            // already wraps SecureTokenStore.write).
            settingsRepository.setCockpitToken(result.value.token)
        }
        return result
    }

    // ─── internals ──────────────────────────────────────────────────────
    //
    // Mirrors HermesCockpitClient.request: build the request off the provider
    // endpoint, run it through the injected executor, turn a transport
    // throwable into Unreachable, decode a 2xx body (Unreachable on malformed),
    // and decode the typed error envelope for any non-2xx. These two routes
    // are unauthenticated, so no bearer token is attached.

    private suspend fun <T> request(
        path: String,
        deserializer: DeserializationStrategy<T>,
        body: String,
    ): CockpitResult<T> = withContext(ioDispatcher) {
        val endpoint = endpointProvider().trim()
        if (endpoint.isBlank()) {
            return@withContext CockpitResult.Unreachable("No gateway endpoint configured")
        }

        val httpRequest = CockpitRequest(
            method = "POST",
            url = CockpitHttp.joinUrl(endpoint, path),
            headers = CockpitHttp.headers(token = null),
            body = body,
            connectTimeoutMs = CockpitHttp.DEFAULT_CONNECT_TIMEOUT_MS,
            readTimeoutMs = CockpitHttp.DEFAULT_READ_TIMEOUT_MS,
        )

        val raw = try {
            executor.execute(httpRequest)
        } catch (e: Exception) {
            return@withContext CockpitResult.Unreachable(e.message ?: "Gateway unreachable")
        }

        if (raw.status in 200..299) {
            val value = try {
                json.decodeFromString(deserializer, raw.body)
            } catch (e: Exception) {
                return@withContext CockpitResult.Unreachable("Malformed response: ${e.message}")
            }
            CockpitResult.Success(value)
        } else {
            CockpitResult.Failure(CockpitHttp.parseError(json, raw.status, raw.body), raw.status)
        }
    }

    companion object {
        /** Exact phrase the gateway requires to issue a device token (owner gate). */
        const val OWNER_AUTHORIZATION_PHRASE: String = "Yes, with authorization."
    }
}
