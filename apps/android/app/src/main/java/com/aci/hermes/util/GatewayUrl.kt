package com.aci.hermes.util

import android.os.Build
import java.net.ConnectException
import java.net.InetAddress
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/**
 * Helpers for reasoning about the gateway URL the user typed and the
 * errors we get back when we try to dial it. Keeps all the
 * "10.0.2.2 only works in the emulator" knowledge in one place so the
 * UI, the connection probe, and the docs stay consistent.
 */
object GatewayUrl {

    /** Hosts that only resolve from inside an Android emulator. */
    private val EMULATOR_ONLY_HOSTS = setOf("10.0.2.2", "10.0.2.3", "10.0.3.2")

    /**
     * Best-effort emulator detection. Uses standard Build fingerprints —
     * good enough to tell "running on the AVD" from "running on a real
     * Pixel" for the purpose of warning the user. Not a security boundary.
     */
    val isProbablyEmulator: Boolean by lazy {
        val fp = Build.FINGERPRINT.orEmpty()
        val model = Build.MODEL.orEmpty()
        val product = Build.PRODUCT.orEmpty()
        val hardware = Build.HARDWARE.orEmpty()
        val brand = Build.BRAND.orEmpty()
        val device = Build.DEVICE.orEmpty()
        fp.startsWith("generic") ||
            fp.startsWith("unknown") ||
            fp.contains("emulator", ignoreCase = true) ||
            model.contains("google_sdk", ignoreCase = true) ||
            model.contains("Emulator", ignoreCase = true) ||
            model.contains("Android SDK built for", ignoreCase = true) ||
            product.contains("sdk_gphone", ignoreCase = true) ||
            product == "sdk" ||
            product == "google_sdk" ||
            hardware == "goldfish" ||
            hardware == "ranchu" ||
            brand.startsWith("generic") && device.startsWith("generic")
    }

    /** Extract the host component from a user-entered URL, or `null` if it can't be parsed. */
    fun hostOf(url: String): String? = runCatching {
        java.net.URI(url.trim()).host?.lowercase()
    }.getOrNull()

    /**
     * `true` if the URL points at an Android emulator loopback host. Those
     * hosts only resolve to "the development machine running the AVD"
     * — they are unreachable from a real device on a Wi-Fi network and
     * from anywhere else.
     */
    fun isEmulatorOnlyHost(url: String): Boolean {
        val host = hostOf(url) ?: return false
        return host in EMULATOR_ONLY_HOSTS
    }

    /**
     * Warning text shown next to the gateway URL field when we can tell
     * the user is about to shoot themselves in the foot — typically by
     * leaving the emulator-only `10.0.2.2` URL in place on a real phone.
     * Returns `null` if the URL looks fine.
     */
    fun warningFor(url: String): String? {
        if (url.isBlank()) return null
        if (isEmulatorOnlyHost(url) && !isProbablyEmulator) {
            return "10.0.2.2 only works inside the Android emulator. " +
                "On a real phone, use the LAN IP of your gateway " +
                "(e.g. http://192.168.1.42:8080), an ngrok / Cloudflare " +
                "tunnel, or a public HTTPS URL."
        }
        if (url.startsWith("http://", ignoreCase = true) &&
            !isLoopbackOrLan(hostOf(url))
        ) {
            return "Production gateways should use HTTPS. http:// is only " +
                "safe on localhost or a trusted LAN."
        }
        return null
    }

    private fun isLoopbackOrLan(host: String?): Boolean {
        if (host.isNullOrBlank()) return false
        if (host == "localhost") return true
        if (host in EMULATOR_ONLY_HOSTS) return true
        return runCatching {
            val addr = InetAddress.getByName(host)
            addr.isLoopbackAddress || addr.isSiteLocalAddress || addr.isLinkLocalAddress
        }.getOrDefault(false)
    }

    /**
     * Classification of why a gateway probe failed. The UI uses this to
     * render distinct copy — "Backend unreachable" reads very differently
     * from "Wrong backend URL" and we want users to be able to tell which
     * one they're hitting at a glance.
     */
    enum class FailureKind { UNREACHABLE, WRONG_URL, TLS, HTTP, UNKNOWN }

    data class Classified(val kind: FailureKind, val message: String)

    /**
     * Map a network exception (or a non-2xx HTTP code) to a user-friendly
     * explanation. The shape (kind + message) lets the UI pick an icon
     * and an action hint without re-parsing the string.
     */
    fun classifyFailure(t: Throwable?, httpCode: Int? = null, gatewayUrl: String? = null): Classified {
        if (httpCode != null) {
            return Classified(
                FailureKind.HTTP,
                "Gateway returned HTTP $httpCode. Check the gateway logs."
            )
        }
        val rawMsg = t?.message.orEmpty()
        // Specific "10.0.2.2 on a real phone" diagnosis takes precedence — the
        // OS error will be a connect timeout or "no route to host", but the
        // useful thing to tell the user is *why*.
        if (gatewayUrl != null && isEmulatorOnlyHost(gatewayUrl) && !isProbablyEmulator) {
            return Classified(
                FailureKind.WRONG_URL,
                "Can't reach ${hostOf(gatewayUrl) ?: gatewayUrl} from this device. " +
                    "10.0.2.2 only works inside the Android emulator — on a real " +
                    "phone use the LAN IP of your gateway, an ngrok / Cloudflare " +
                    "tunnel, or a public HTTPS URL."
            )
        }
        return when (t) {
            is UnknownHostException -> Classified(
                FailureKind.WRONG_URL,
                "Can't resolve the gateway host. Double-check the URL — typo, " +
                    "wrong domain, or DNS not reachable."
            )
            is NoRouteToHostException -> Classified(
                FailureKind.UNREACHABLE,
                "No route to the gateway. Check Wi-Fi / VPN and that the gateway " +
                    "is on the same network."
            )
            is SocketTimeoutException -> Classified(
                FailureKind.UNREACHABLE,
                "Gateway didn't respond in time. It may be offline, blocked by a " +
                    "firewall, or the URL points at a host that isn't running Hermes."
            )
            is ConnectException -> Classified(
                FailureKind.UNREACHABLE,
                "Gateway refused the connection. The host is reachable but nothing " +
                    "is listening on that port — is `hermes gateway start` running?"
            )
            is SSLException -> Classified(
                FailureKind.TLS,
                "TLS handshake failed: ${rawMsg.ifBlank { "certificate or protocol mismatch" }}."
            )
            else -> {
                val cls = t?.javaClass?.simpleName.orEmpty()
                Classified(
                    FailureKind.UNKNOWN,
                    when {
                        "UnknownHost" in cls -> "Can't resolve the gateway host."
                        "ConnectException" in cls -> "Couldn't connect to the gateway."
                        "SocketTimeout" in cls -> "Gateway didn't respond in time."
                        "SSL" in cls -> "TLS handshake failed: $rawMsg"
                        rawMsg.isNotBlank() -> rawMsg
                        else -> cls.ifBlank { "Unknown error" }
                    }
                )
            }
        }
    }
}
