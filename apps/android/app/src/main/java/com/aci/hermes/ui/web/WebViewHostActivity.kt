package com.aci.hermes.ui.web

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import com.aci.hermes.HermesApplication
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import java.net.HttpURLConnection
import java.net.URL

/**
 * Full-screen WebView host that renders the NEXUS PWA as the unified app's
 * primary UI, wiring the [NexusBridge] so the web layer can reach the native
 * services a browser cannot (voice, overlay, token, emergency stop).
 *
 * **Phase 1 (additive, default-OFF).** This Activity is `exported=false` and is
 * launched only when the owner opts into the unified shell
 * (`SettingsRepository.unifiedPwaShellEnabled`). Until the Phase-2 cutover the
 * shipped app still lands on the native Compose `MainActivity`, so adding this
 * file changes no default behavior. See `docs/mobile/NEXUS_UNIFIED_APP_PLAN.md`.
 *
 * Absorbs the standalone `apps/nexus/android` WebView shell (which Phase 3
 * retires): same loopback-gateway-first load strategy and the same
 * permission/file/download bridges, plus the native [NexusBridge].
 */
class WebViewHostActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var bridge: NexusBridge
    private val bridgeScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /**
     * The live page URL, written only on the main thread (page lifecycle
     * callbacks) and read on the WebView's JS-binder thread by the bridge.
     * `@Volatile` gives the binder thread a consistent recent value without a
     * lock; the bridge re-checks trust on every call.
     */
    @Volatile
    private var liveUrl: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        setContentView(webView)

        val settings = (application as HermesApplication).container.settingsRepository
        bridge = NexusBridge(
            appContext = applicationContext,
            settings = settings,
            scope = bridgeScope,
            currentUrl = { liveUrl },
        )

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = WebSettings.LOAD_DEFAULT
            userAgentString = "$userAgentString NEXUSAndroid"
        }

        // Expose the bridge object to the page. Every method self-guards on the
        // live origin ([NexusBridgeOriginGuard]); navigation below also keeps
        // untrusted origins out of this WebView entirely (belt and suspenders).
        webView.addJavascriptInterface(bridge, NexusBridge.JS_INTERFACE_NAME)

        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView, url: String?, favicon: android.graphics.Bitmap?) {
                liveUrl = url
                super.onPageStarted(view, url, favicon)
            }

            override fun onPageFinished(view: WebView, url: String?) {
                liveUrl = url
                super.onPageFinished(view, url)
            }

            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                val target = request.url.toString()
                // Keep trusted first-party navigation in-app; hand everything
                // else (link-outs, mailto/tel/intent) to the system so the
                // bridge-bearing WebView only ever holds a trusted origin.
                if (NexusBridgeOriginGuard.isTrusted(target)) return false
                return try {
                    startActivity(Intent(Intent.ACTION_VIEW, request.url))
                    true
                } catch (e: Exception) {
                    true
                }
            }
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })

        if (savedInstanceState == null) chooseAndLoad()
    }

    /**
     * Prefer the local gateway when one is up — load it same-origin at
     * `http://127.0.0.1:<port>/nexus/` so the app + API share one http origin
     * (no mixed-content, no CORS). Fall back to the hosted PWA otherwise.
     */
    private fun chooseAndLoad() {
        Thread {
            val local = "http://127.0.0.1:$GATEWAY_PORT"
            val url = if (probe("$local/v1/health")) "$local/nexus/" else HOSTED_PWA_URL
            runOnUiThread { webView.loadUrl(url) }
        }.start()
    }

    private fun probe(url: String): Boolean = try {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 1500
            readTimeout = 1500
            requestMethod = "GET"
        }
        val ok = conn.responseCode in 200..299
        conn.disconnect()
        ok
    } catch (e: Exception) {
        false
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        webView.saveState(outState)
    }

    override fun onRestoreInstanceState(savedInstanceState: Bundle) {
        super.onRestoreInstanceState(savedInstanceState)
        webView.restoreState(savedInstanceState)
    }

    override fun onDestroy() {
        bridgeScope.cancel()
        // Leave the foreground services running: voice/overlay are
        // owner-controlled and carry their own notifications, and the user's
        // emergency-stop / notification controls own their teardown — not this
        // transient view surface.
        super.onDestroy()
    }

    companion object {
        private const val GATEWAY_PORT = 8765
        private const val HOSTED_PWA_URL =
            "https://a-c-i-software-and-development.github.io/M.U.S.E/"
    }
}
