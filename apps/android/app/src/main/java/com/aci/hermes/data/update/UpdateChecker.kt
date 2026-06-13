package com.aci.hermes.data.update

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

/**
 * Checks the public `android-latest.json` manifest for a newer build. Standalone
 * by design — it talks to the GitHub release channel, not the local cockpit
 * gateway, so it does not use [com.aci.hermes.data.cockpit.HermesCockpitClient].
 *
 * The network fetch is injected ([fetch]) so the decision path is JVM-unit
 * testable without real IO. The production fetch mirrors the cockpit's
 * `JdkHttpExecutor` (stdlib [HttpURLConnection], no third-party HTTP) but
 * **follows redirects** — GitHub release asset URLs 30x to a CDN.
 */
class UpdateChecker(
    private val currentVersionCode: Int,
    private val currentVersionName: String,
    private val manifestUrl: String = DEFAULT_MANIFEST_URL,
    private val fetch: (String) -> String? = ::httpGet,
) {
    /** Fetch the manifest and decide. Never throws; failures map to [UpdateState.Unknown]. */
    suspend fun check(): UpdateState = withContext(Dispatchers.IO) {
        val body = fetch(manifestUrl)
        UpdateState.evaluate(
            currentVersionCode = currentVersionCode,
            currentVersionName = currentVersionName,
            manifest = body?.let(UpdateManifest::parse),
        )
    }

    companion object {
        /** Stable rolling-channel manifest URL (sibling of the rolling APK). */
        const val DEFAULT_MANIFEST_URL: String =
            "https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/hermes-agent/releases/download/" +
                "android-latest/android-latest.json"

        private const val TIMEOUT_MS = 10_000

        private fun httpGet(url: String): String? = try {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true
                useCaches = false
            }
            try {
                if (connection.responseCode in 200..299) {
                    connection.inputStream.bufferedReader().use { it.readText() }
                } else {
                    null
                }
            } finally {
                connection.disconnect()
            }
        } catch (_: Throwable) {
            null
        }
    }
}
