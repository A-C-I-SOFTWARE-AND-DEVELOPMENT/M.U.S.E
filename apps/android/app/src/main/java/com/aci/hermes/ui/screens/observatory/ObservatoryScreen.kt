package com.aci.hermes.ui.screens.observatory

import android.annotation.SuppressLint
import android.net.Uri
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.aci.hermes.data.cockpit.BackendStatus
import com.aci.hermes.data.cockpit.CockpitHttp
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.ui.designsystem.MuseButton
import com.aci.hermes.ui.designsystem.MuseButtonVariant
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The Neural Observatory cockpit screen — a WebView host for the gateway's
 * interactive 3D Observatory page (`/cockpit/observatory.html`).
 *
 * The page itself is served by the paired Hermes gateway; this screen only
 * frames it natively. Connection facts come from the *same* stores every
 * other cockpit surface reads — [SettingsRepository.gatewayEndpoint]
 * (DataStore) for the base URL and [SettingsRepository.cockpitToken] (the
 * encrypted-at-rest token store) for the bearer — so pairing once in
 * Settings → Connection lights this screen up too; there is no parallel
 * settings store.
 *
 * Auth is handed to the page via the URL *fragment* (`#token=…`): fragments
 * never leave the client in HTTP requests, so the bearer cannot land in
 * gateway access logs. The page stashes it in its own localStorage (which is
 * why DOM storage is enabled).
 *
 * Honesty rule (mirrors [BackendStatus]): the WebView is only mounted after
 * a real `/v1/health` 2xx. An unpaired or unreachable gateway renders a
 * Compose dormant state with a retry — never a raw WebView error page, and
 * never a fabricated "online".
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ObservatoryScreen(
    settingsRepository: SettingsRepository,
    cockpitClient: HermesCockpitClient,
    onBack: () -> Unit,
) {
    val endpoint by settingsRepository.gatewayEndpoint.collectAsState(
        initial = SettingsRepository.DEFAULT_GATEWAY_ENDPOINT,
    )
    val token by settingsRepository.cockpitToken.collectAsState()

    // Bumped by the dormant-state Retry and the top-bar refresh; re-keys the
    // health probe without touching the stored connection facts.
    var probeAttempt by remember { mutableIntStateOf(0) }
    var status by remember { mutableStateOf(BackendStatus.CHECKING) }
    var webView by remember { mutableStateOf<WebView?>(null) }

    LaunchedEffect(endpoint, token, probeAttempt) {
        status = BackendStatus.CHECKING
        status = if (endpoint.isBlank() || token.isNullOrBlank()) {
            // The Observatory page needs the bearer, so "no token yet" is
            // dormant-unpaired even though /v1/health itself is tokenless.
            BackendStatus.UNPAIRED
        } else {
            BackendStatus.from(endpointConfigured = true, result = cockpitClient.health())
        }
    }

    // The Observatory URL. The token rides in the fragment, percent-encoded;
    // fragments are stripped client-side so it never reaches server logs.
    val observatoryUrl = remember(endpoint, token) {
        val bearer = token
        if (endpoint.isBlank() || bearer.isNullOrBlank()) null
        else CockpitHttp.joinUrl(endpoint, OBSERVATORY_PATH) + "#token=" + Uri.encode(bearer)
    }

    // System back walks the page's own history first, then pops the screen.
    BackHandler {
        val view = webView
        if (view != null && view.canGoBack()) view.goBack() else onBack()
    }

    // Pause/resume the WebView with the host lifecycle (stops JS timers and
    // the 3D render loop off-screen); destroy it when the screen leaves the
    // back stack so nothing keeps rendering or holding the page alive.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE -> webView?.onPause()
                Lifecycle.Event.ON_RESUME -> webView?.onResume()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            webView?.destroy()
            webView = null
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Observatory") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            val view = webView
                            // Reload the live page; from a dormant state the
                            // same affordance re-runs the health probe.
                            if (status.isReachable && view != null) view.reload()
                            else probeAttempt++
                        },
                    ) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Reload")
                    }
                },
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                // Deep-space backdrop behind the page while it loads, so the
                // 3D scene never flashes white in.
                .background(ObservatoryBackdrop),
        ) {
            when {
                status == BackendStatus.CHECKING -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
                }

                status.isReachable && observatoryUrl != null -> {
                    ObservatoryWebView(
                        url = observatoryUrl,
                        onWebViewCreated = { created ->
                            // A stale instance survives a dormant interlude
                            // (the AndroidView left composition without the
                            // screen being disposed) — retire it explicitly.
                            webView?.takeIf { it !== created }?.destroy()
                            webView = created
                        },
                        modifier = Modifier.fillMaxSize(),
                    )
                }

                else -> {
                    ObservatoryDormant(
                        status = status,
                        onRetry = { probeAttempt++ },
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }
        }
    }
}

/**
 * The framework WebView host (no extra Gradle dependency). JavaScript + DOM
 * storage are required by the Observatory page (3D scene + localStorage
 * token); wide viewport so the scene scales to the phone.
 */
@SuppressLint("SetJavaScriptEnabled") // Page is the user's own paired gateway, not arbitrary web.
@Composable
private fun ObservatoryWebView(
    url: String,
    onWebViewCreated: (WebView) -> Unit,
    modifier: Modifier = Modifier,
) {
    AndroidView(
        modifier = modifier,
        factory = { context ->
            WebView(context).apply {
                setBackgroundColor(ObservatoryBackdrop.toArgb())
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.useWideViewPort = true
                settings.loadWithOverviewMode = true
                // Keep navigation in-page (no external browser hop, which
                // would also leak the token fragment out of the app).
                webViewClient = WebViewClient()
            }.also(onWebViewCreated)
        },
        update = { view ->
            // `update` runs on every recomposition; the tag guard makes the
            // load idempotent and re-fires only when base/token change.
            if (view.tag != url) {
                view.tag = url
                view.loadUrl(url)
            }
        },
    )
}

/**
 * Honest dormant state: the gateway is unpaired or not answering, so no
 * WebView is mounted (a raw `net::ERR_…` page would imply the cockpit is
 * broken rather than simply offline). Mirrors the [BackendStatus] split the
 * rest of the cockpit uses — unpaired points at Settings → Connection,
 * offline offers a retry.
 */
@Composable
private fun ObservatoryDormant(
    status: BackendStatus,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val unpaired = status == BackendStatus.UNPAIRED
    Column(
        modifier = modifier.padding(JarvisTokens.SpaceXl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd, Alignment.CenterVertically),
    ) {
        Icon(
            imageVector = if (unpaired) Icons.Filled.Link else Icons.Filled.CloudOff,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = if (unpaired) "Observatory dormant" else "Gateway unreachable",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
        )
        Text(
            text = if (unpaired) {
                "The Observatory is served by your MUSE gateway. Pair this " +
                    "device in Settings → Connection to light it up."
            } else {
                "The paired gateway is not answering right now. Check that " +
                    "`hermes cockpit serve` is running, then retry."
            },
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        MuseButton(
            onClick = onRetry,
            text = "Retry",
            variant = MuseButtonVariant.Secondary,
        )
    }
}

/** Gateway route of the Neural Observatory page. */
private const val OBSERVATORY_PATH = "/cockpit/observatory.html"

/** Near-black space backdrop shown behind/under the page while it loads. */
private val ObservatoryBackdrop = Color(0xFF05080F)
