package com.aci.hermes.service

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.os.Handler
import android.os.Looper
import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
import com.aci.hermes.HermesApplication
import com.aci.hermes.data.observatory.ActionEvent
import com.aci.hermes.data.observatory.ObservatoryCluster
import com.aci.hermes.data.observatory.ObservatoryStreamClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import kotlin.math.min
import kotlin.random.Random
import kotlinx.coroutines.Dispatchers

/**
 * Live device wallpaper that renders the M.U.S.E neural network and pulses on
 * every real system action, synced from the paired gateway's
 * `/v1/observatory/*` routes — **native on the device, not a remote stream**.
 *
 * This is the Canvas baseline renderer (matches the app's existing Canvas
 * drawing, e.g. `PixelRoom`): a starfield, the real GraphRAG super-node clusters
 * placed from their server-computed positions, and an expanding ripple + energy
 * bump for each fused [ActionEvent]. The "ultimate quality" upgrade path —
 * a GLES2/Niagara-style instanced renderer with bloom — is specified in
 * `apps/android/docs/observatory-wallpaper.md`; it slots in behind the same
 * snapshot + actions data contract this service already consumes.
 *
 * Honest by construction: when the gateway is unpaired or the observatory
 * collector is opt-out (snapshot empty / actions 503), the wallpaper renders a
 * quiet starfield — never fabricated nodes or activity.
 */
class ObservatoryWallpaperService : WallpaperService() {

    override fun onCreateEngine(): Engine = ObservatoryEngine()

    private inner class ObservatoryEngine : Engine() {
        private val handler = Handler(Looper.getMainLooper())
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        private var visible = false
        private var width = 0
        private var height = 0

        // Connection facts, shared with every cockpit surface (no parallel store).
        private val settings by lazy {
            (applicationContext as HermesApplication).container.settingsRepository
        }
        private var endpoint: String = ""
        private val client by lazy {
            ObservatoryStreamClient(
                endpointProvider = { endpoint },
                tokenProvider = { settings.cockpitToken.value },
            )
        }

        // Scene state — only ever populated from real gateway data.
        private val nodes = ArrayList<Node>()
        private val ripples = ArrayList<Ripple>()
        private val stars = ArrayList<FloatArray>() // x,y,brightness (deterministic)
        @Volatile private var edgeTint = 0

        private val nodePaint = Paint(Paint.ANTI_ALIAS_FLAG)
        private val ripplePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE }
        private val starPaint = Paint(Paint.ANTI_ALIAS_FLAG)

        private val drawRunnable = Runnable { drawFrame() }

        override fun onCreate(surfaceHolder: SurfaceHolder?) {
            super.onCreate(surfaceHolder)
            scope.launch { settings.gatewayEndpoint.collect { endpoint = it } }
            scope.launch { loadSnapshot() }
            scope.launch { streamActions() }
        }

        override fun onVisibilityChanged(v: Boolean) {
            visible = v
            if (v) scheduleDraw() else handler.removeCallbacks(drawRunnable)
        }

        override fun onSurfaceChanged(holder: SurfaceHolder?, format: Int, w: Int, h: Int) {
            width = w
            height = h
            seedStars()
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder?) {
            visible = false
            handler.removeCallbacks(drawRunnable)
        }

        override fun onDestroy() {
            handler.removeCallbacks(drawRunnable)
            scope.cancel()
            super.onDestroy()
        }

        private suspend fun loadSnapshot() {
            val clusters = client.snapshotClusters()
            synchronized(nodes) {
                nodes.clear()
                clusters.forEach { nodes.add(Node(it)) }
            }
        }

        private suspend fun streamActions() {
            // Reconnect with backoff; the flow completes on dormant/unauth.
            var backoff = 1_000L
            while (true) {
                client.actions().collectLatest { onAction(it); backoff = 1_000L }
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(15_000L)
                // A graph rebuild may have moved clusters — refresh on reconnect.
                runCatching { loadSnapshot() }
            }
        }

        private fun onAction(ev: ActionEvent) {
            val node = ev.clusterId?.let { id -> synchronized(nodes) { nodes.firstOrNull { it.cluster.id == id } } }
            val (cx, cy) = node?.screen(width, height) ?: (width * 0.5f to height * 0.5f)
            val color = severityColor(ev.severity)
            synchronized(ripples) {
                if (ripples.size < MAX_RIPPLES) ripples.add(Ripple(cx, cy, color))
            }
            node?.let { it.energy = (it.energy + ev.weight.toFloat().coerceIn(0.2f, 1f)).coerceAtMost(2f) }
            if (node == null) edgeTint = color // non-spatial pulse → faint full-frame tint
        }

        private fun scheduleDraw() {
            handler.removeCallbacks(drawRunnable)
            if (visible) handler.postDelayed(drawRunnable, FRAME_MS)
        }

        private fun drawFrame() {
            val holder = surfaceHolder
            var canvas: Canvas? = null
            try {
                canvas = holder.lockCanvas() ?: return
                render(canvas)
            } finally {
                if (canvas != null) runCatching { holder.unlockCanvasAndPost(canvas) }
            }
            if (visible) scheduleDraw()
        }

        private fun render(c: Canvas) {
            c.drawColor(Color.rgb(5, 8, 15))
            // Starfield (deterministic; pure dressing, carries no data).
            for (s in stars) {
                starPaint.color = Color.argb((s[2] * 160).toInt(), 200, 220, 255)
                c.drawCircle(s[0], s[1], 1.4f, starPaint)
            }
            // Real cluster nodes.
            val now = System.currentTimeMillis()
            synchronized(nodes) {
                for (n in nodes) {
                    n.energy = (n.energy - DECAY).coerceAtLeast(0f)
                    val (x, y) = n.screen(width, height)
                    val base = ((n.cluster.heat ?: 0.0).toFloat() * 0.6f + 0.25f)
                    val glow = (base + n.energy).coerceIn(0f, 1.4f)
                    val r = (6f + n.cluster.radius.toFloat() * 2.2f + n.energy * 8f)
                    nodePaint.shader = RadialGradient(
                        x, y, r,
                        Color.argb((glow * 200).toInt().coerceIn(0, 255), 122, 224, 255),
                        Color.TRANSPARENT, Shader.TileMode.CLAMP,
                    )
                    c.drawCircle(x, y, r, nodePaint)
                }
            }
            nodePaint.shader = null
            // Action ripples (expand + fade), and retire finished ones.
            synchronized(ripples) {
                val it = ripples.iterator()
                while (it.hasNext()) {
                    val rp = it.next()
                    val age = (now - rp.born) / RIPPLE_MS.toFloat()
                    if (age >= 1f) { it.remove(); continue }
                    ripplePaint.color = Color.argb(((1f - age) * 180).toInt(), Color.red(rp.color), Color.green(rp.color), Color.blue(rp.color))
                    ripplePaint.strokeWidth = 3f * (1f - age)
                    c.drawCircle(rp.x, rp.y, age * (min(width, height) * 0.18f), ripplePaint)
                }
            }
            // Faint non-spatial pulse tint, fading each frame.
            if (edgeTint != 0) {
                c.drawColor(Color.argb(26, Color.red(edgeTint), Color.green(edgeTint), Color.blue(edgeTint)))
                edgeTint = 0
            }
        }

        private fun seedStars() {
            stars.clear()
            if (width == 0 || height == 0) return
            val rng = Random(0x5EED)
            repeat(STAR_COUNT) {
                stars.add(floatArrayOf(rng.nextFloat() * width, rng.nextFloat() * height, rng.nextFloat()))
            }
        }
    }

    /** A real cluster placed on screen from its server-computed [-100,100]^3 position. */
    private class Node(val cluster: ObservatoryCluster) {
        var energy = 0f
        fun screen(w: Int, h: Int): Pair<Float, Float> {
            val s = min(w, h) * 0.0042f // map [-100,100] across ~84% of the short side
            return (w / 2f + cluster.x.toFloat() * s) to (h / 2f + cluster.y.toFloat() * s)
        }
    }

    private class Ripple(val x: Float, val y: Float, val color: Int) {
        val born = System.currentTimeMillis()
    }

    private companion object {
        const val FRAME_MS = 33L          // ~30 fps when visible
        const val DECAY = 0.02f
        const val MAX_RIPPLES = 64
        const val RIPPLE_MS = 1_400L
        const val STAR_COUNT = 140

        fun severityColor(severity: String): Int = when (severity) {
            "error" -> Color.rgb(255, 90, 102)
            "warn" -> Color.rgb(255, 204, 102)
            "critical" -> Color.rgb(255, 42, 68)
            else -> Color.rgb(122, 224, 255)
        }
    }
}
