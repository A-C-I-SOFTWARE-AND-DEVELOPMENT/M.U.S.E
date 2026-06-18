package com.aci.hermes.ui.web

import java.net.URI

/**
 * Decides whether the page currently loaded in the unified-shell WebView is a
 * **trusted first-party origin** that may see the [NexusBridge]. Pure logic so
 * it is unit-testable without a WebView/emulator.
 *
 * The bridge is the one place where web content can reach native authority
 * (token, emergency stop, voice/overlay services), so it must never be exposed
 * to arbitrary web origins. Only two origins are trusted:
 *
 *  1. The hosted NEXUS PWA on GitHub Pages (`https`, the project's own host).
 *  2. A **loopback** gateway (`127.0.0.1` / `localhost` / `[::1]`) — the
 *     user's own machine, same-origin with `muse cockpit serve`.
 *
 * Everything else (a link the user followed out to the open web, an http page
 * that is not loopback, a look-alike host) is untrusted and the bridge refuses.
 */
object NexusBridgeOriginGuard {

    /** The canonical hosted PWA host. https only. */
    const val HOSTED_HOST: String = "a-c-i-software-and-development.github.io"

    private val LOOPBACK_HOSTS = setOf("127.0.0.1", "localhost", "::1", "[::1]")

    /**
     * True when [url] is an origin allowed to use the native bridge.
     *
     * @param url the WebView's current URL (may be null before first load).
     */
    fun isTrusted(url: String?): Boolean {
        if (url.isNullOrBlank()) return false
        val uri = runCatching { URI(url) }.getOrNull() ?: return false
        val scheme = uri.scheme?.lowercase() ?: return false
        val host = uri.host?.lowercase() ?: return false

        return when {
            // Hosted PWA: must be HTTPS on exactly our host (no sub-domain
            // wildcarding, no look-alikes).
            scheme == "https" && host == HOSTED_HOST -> true
            // Loopback gateway: the user's own machine. http is acceptable for
            // loopback only — it never leaves the device.
            scheme == "http" && host in LOOPBACK_HOSTS -> true
            else -> false
        }
    }
}
