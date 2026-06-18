package com.aci.hermes.ui.web

import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.JavascriptInterface
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.service.JarvisOverlayService
import com.aci.hermes.service.VoiceLoopService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The keystone of the PWA-first unified app (see
 * `docs/mobile/NEXUS_UNIFIED_APP_PLAN.md`): the **only** path by which the
 * NEXUS PWA, hosted in [WebViewHostActivity], reaches the native authority a
 * browser cannot have — the cockpit bearer token, the always-on voice loop,
 * the avatar overlay, and the emergency stop.
 *
 * Every method is refused unless the WebView's current page is a trusted
 * first-party origin ([NexusBridgeOriginGuard]); arbitrary web content that
 * the user navigates to never sees these capabilities. Owner-gated *server*
 * actions (spend / deploy / publish / merge) stay gated on the gateway exactly
 * as today — this bridge only exposes on-device, owner-consented surfaces.
 *
 * Methods return a boolean "accepted" (or a JSON string) rather than throwing,
 * because exceptions across the `@JavascriptInterface` boundary are swallowed
 * by the WebView and would surface to the PWA as an opaque failure.
 *
 * @param appContext application context (never an Activity — the bridge
 *   outlives configuration changes).
 * @param settings the single source of truth for on-device preferences/token.
 * @param scope an IO-capable scope for the suspend settings writes.
 * @param currentUrl a thread-safe snapshot of the WebView's current URL,
 *   updated on the main thread by the host; read here on the binder thread.
 */
class NexusBridge(
    private val appContext: Context,
    private val settings: SettingsRepository,
    private val scope: CoroutineScope,
    private val currentUrl: () -> String?,
    private val mainHandler: Handler = Handler(Looper.getMainLooper()),
) {

    /** Run [action] only if the live page is a trusted origin. */
    private inline fun guarded(action: () -> Unit): Boolean {
        if (!NexusBridgeOriginGuard.isTrusted(currentUrl())) {
            Log.w(TAG, "NexusBridge call refused: untrusted origin")
            return false
        }
        return runCatching { action(); true }
            .getOrElse { Log.w(TAG, "NexusBridge action failed", it); false }
    }

    /** Services touch the foreground; start/stop them on the main thread. */
    private fun onMain(block: () -> Unit) = mainHandler.post(block)

    /**
     * Shell metadata so the PWA can detect it is running inside the native app
     * (and which native capabilities are therefore available). A plain browser
     * sees no `NexusBridge` global and degrades to the honest "requires the
     * NEXUS app" state, mirroring the existing "requires gateway" pattern.
     */
    @JavascriptInterface
    fun shellInfo(): String {
        val version = runCatching {
            appContext.packageManager.getPackageInfo(appContext.packageName, 0).versionName
        }.getOrNull() ?: "unknown"
        return JSONObject().apply {
            put("shell", "android")
            put("bridgeVersion", BRIDGE_VERSION)
            put("appVersion", version)
            put("trustedOrigin", NexusBridgeOriginGuard.isTrusted(currentUrl()))
            put(
                "capabilities",
                org.json.JSONArray(
                    listOf("token", "voice", "overlay", "emergencyStop"),
                ),
            )
        }.toString()
    }

    /**
     * The cockpit bearer token, handed only to a trusted first-party origin so
     * the PWA can call the gateway. Returns `""` when untrusted or unpaired —
     * never throws across the bridge.
     */
    @JavascriptInterface
    fun getToken(): String {
        if (!NexusBridgeOriginGuard.isTrusted(currentUrl())) return ""
        return settings.cockpitToken.value.orEmpty()
    }

    /** Pair: persist the bearer token (encrypted at rest). */
    @JavascriptInterface
    fun setToken(token: String): Boolean = guarded {
        scope.launch { settings.setCockpitToken(token) }
    }

    /** Unpair: drop the stored token. */
    @JavascriptInterface
    fun clearToken(): Boolean = guarded {
        scope.launch { settings.clearCockpitToken() }
    }

    /** Arm the always-on voice loop (shows the mic foreground-service notice). */
    @JavascriptInterface
    fun voiceStart(): Boolean = guarded { onMain { VoiceLoopService.start(appContext) } }

    @JavascriptInterface
    fun voiceStop(): Boolean = guarded { onMain { VoiceLoopService.stop(appContext) } }

    /** Show the floating avatar overlay (specialUse foreground-service notice). */
    @JavascriptInterface
    fun overlayShow(): Boolean = guarded { onMain { JarvisOverlayService.start(appContext) } }

    @JavascriptInterface
    fun overlayHide(): Boolean = guarded { onMain { JarvisOverlayService.stop(appContext) } }

    /**
     * Emergency stop: persist the engaged flag (every mutation path reads it)
     * and tear down the running services. Resuming requires an explicit,
     * audited action elsewhere — there is no silent un-stop here.
     */
    @JavascriptInterface
    fun engageEmergencyStop(): Boolean = guarded {
        scope.launch { settings.setEmergencyStopEngaged(true) }
        onMain {
            VoiceLoopService.stop(appContext)
            JarvisOverlayService.stop(appContext)
            appContext.stopService(Intent(appContext, HermesService::class.java))
        }
    }

    companion object {
        const val TAG = "NexusBridge"

        /** The JS-side global name the PWA looks for. */
        const val JS_INTERFACE_NAME = "NexusBridge"

        /** Bumped when the contract changes so the PWA can feature-detect. */
        const val BRIDGE_VERSION = 1
    }
}
