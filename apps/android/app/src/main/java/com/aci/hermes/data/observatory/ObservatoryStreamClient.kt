package com.aci.hermes.data.observatory

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.coroutines.coroutineContext

/** One fused action from `GET /v1/observatory/actions` (the wallpaper feed). */
data class ActionEvent(
    val id: String,        // opaque resume cursor carried on the SSE `id:` line
    val kind: String,      // closed vocabulary, see gateway action_fusion.KINDS
    val source: String,    // collector | flywheel | cockpit | axiom
    val clusterId: String?,
    val jobId: String?,
    val label: String,
    val weight: Double,
    val severity: String,  // info | warn | error | critical
)

/** One super-node cluster from `GET /v1/observatory/snapshot` (the boot graph). */
data class ObservatoryCluster(
    val id: String,
    val x: Double,
    val y: Double,
    val z: Double,
    val radius: Double,
    val heat: Double?,     // null = no measured activity (rendered neutral)
)

/**
 * Read-only client for the Neural Observatory's live action feed.
 *
 * Mirrors [com.aci.hermes.data.jarvis.HttpJarvisChatGateway]'s self-contained
 * [HttpURLConnection] streaming idiom (no third-party HTTP dependency): the SSE
 * body is read line-by-line and parsed into [ActionEvent]s. Cancelling the
 * collecting coroutine closes the connection between lines via [ensureActive].
 *
 * Honest by construction: a `503` (collector opt-out) or `401` (unpaired) ends
 * the flow quietly — callers render a dormant wallpaper, never fabricated nodes.
 * Auth + endpoint come from the same paired connection facts every cockpit
 * surface uses (bearer token + gateway endpoint).
 */
class ObservatoryStreamClient(
    private val endpointProvider: () -> String,
    private val tokenProvider: () -> String?,
    private val logBuffer: LogBuffer? = null,
) {

    /** Boot graph: the super-node clusters with their server-computed positions.
     *  Empty list on any error / dormant gateway (honest-empty, never invented). */
    suspend fun snapshotClusters(): List<ObservatoryCluster> = fetchJson(SNAPSHOT_PATH)?.let { obj ->
        val graph = obj.optJSONObject("graph") ?: return emptyList()
        val arr = graph.optJSONArray("clusters") ?: return emptyList()
        buildList {
            for (i in 0 until arr.length()) {
                val c = arr.optJSONObject(i) ?: continue
                val pos = c.optJSONArray("pos") ?: continue
                add(
                    ObservatoryCluster(
                        id = c.optString("id"),
                        x = pos.optDouble(0, 0.0),
                        y = pos.optDouble(1, 0.0),
                        z = pos.optDouble(2, 0.0),
                        radius = c.optDouble("radius", 1.0),
                        heat = if (c.isNull("heat")) null else c.optDouble("heat"),
                    ),
                )
            }
        }
    } ?: emptyList()

    /** Live fused actions until the collecting coroutine is cancelled. Completes
     *  on dormant/unauth; the caller may reconnect (optionally with [lastEventId]). */
    fun actions(lastEventId: String? = null): Flow<ActionEvent> = flow {
        val base = endpointProvider().trimEnd('/')
        val conn = openGet("$base$ACTIONS_PATH", stream = true).apply {
            setRequestProperty("Accept", "text/event-stream")
            lastEventId?.let { setRequestProperty("Last-Event-ID", it) }
        }
        try {
            if (conn.responseCode != 200) return@flow // 401/503 → dormant, caller retries
            conn.inputStream.bufferedReader().use { r ->
                var event = "message"
                var id: String? = null
                val data = StringBuilder()
                while (true) {
                    coroutineContext.ensureActive()
                    val line = r.readLine() ?: break
                    when {
                        line.isEmpty() -> {                 // frame boundary
                            if (data.isNotEmpty()) parse(id, event, data.toString())?.let { emit(it) }
                            event = "message"; id = null; data.setLength(0)
                        }
                        line.startsWith(":") -> {}           // ": ping" heartbeat
                        line.startsWith("id:") -> id = line.substring(3).trim()
                        line.startsWith("event:") -> event = line.substring(6).trim()
                        line.startsWith("data:") -> data.append(line.substring(5).removePrefix(" "))
                    }
                }
            }
        } finally {
            conn.disconnect()
        }
    }.flowOn(Dispatchers.IO)

    private suspend fun fetchJson(path: String): JSONObject? = withContext(Dispatchers.IO) {
        runCatching {
            val base = endpointProvider().trimEnd('/')
            val conn = openGet("$base$path", stream = false)
            try {
                if (conn.responseCode != 200) null
                else JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
            } finally {
                conn.disconnect()
            }
        }.onFailure { logBuffer?.warn("observatory", "snapshot fetch failed: ${it.message}") }.getOrNull()
    }

    private fun openGet(url: String, stream: Boolean): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 5_000
            readTimeout = if (stream) 0 else 8_000
            tokenProvider()?.takeIf { it.isNotBlank() }?.let {
                setRequestProperty("Authorization", "Bearer $it")
            }
        }

    private fun parse(id: String?, event: String, json: String): ActionEvent? = runCatching {
        if (event == "meta.resync") return null // control frame, not a visual
        val o = JSONObject(json)
        val target = o.optJSONObject("target")
        ActionEvent(
            id = id.orEmpty(),
            kind = o.optString("kind", event),
            source = o.optString("source"),
            clusterId = target?.optString("cluster_id")?.ifBlank { null },
            jobId = target?.optString("job_id")?.ifBlank { null },
            label = o.optString("label"),
            weight = o.optDouble("weight", 1.0),
            severity = o.optString("severity", "info"),
        )
    }.getOrNull()

    companion object {
        private const val SNAPSHOT_PATH = "/v1/observatory/snapshot"
        private const val ACTIONS_PATH = "/v1/observatory/actions"
    }
}
