package dev.aci.nexus.daemon.net

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * The daemon's ENTIRE dependency on the M.U.S.E. backend. Mirrors
 * ../../CONTRACT.md. No UI logic lives here.
 */
@Serializable
data class StatusSnapshot(
    val idle: Int = 0,
    val running: Int = 0,
    val error: Int = 0,
    val needsAuth: Int = 0,
)

@Serializable
data class AuthRequest(
    val id: String,
    val action: String,
    val risk: String = "owner-gated",
    val expiresAt: Long = 0L,
)

sealed interface DaemonFrame {
    data class Status(val snapshot: StatusSnapshot) : DaemonFrame
    data class Event(val kind: String, val message: String) : DaemonFrame
    data class Auth(val request: AuthRequest) : DaemonFrame
}

class MuseClient(
    private val baseUrl: String,
    private val token: String,
    private val http: OkHttpClient = OkHttpClient(),
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val jsonMedia = "application/json".toMediaType()

    private fun authed(builder: Request.Builder) =
        builder.header("Authorization", "Bearer $token")

    /** Persistent status/event/auth socket held open by the foreground service. */
    fun connect(onFrame: (DaemonFrame) -> Unit, onClosed: () -> Unit): WebSocket {
        val req = authed(Request.Builder().url("${baseUrl.trimEnd('/')}/api/ws")).build()
        return http.newWebSocket(req, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { decode(text) }.getOrNull()?.let(onFrame)
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = onClosed()
            override fun onFailure(webSocket: WebSocket, t: Throwable, r: Response?) = onClosed()
        })
    }

    private fun decode(text: String): DaemonFrame? {
        val obj = json.parseToJsonElement(text)
        val type = obj.toString()
        return when {
            "\"type\":\"status\"" in type ->
                DaemonFrame.Status(json.decodeFromString(StatusSnapshot.serializer(), text))
            "\"type\":\"auth-request\"" in type ->
                DaemonFrame.Auth(json.decodeFromString(AuthRequest.serializer(), text))
            "\"type\":\"event\"" in type -> {
                val o = json.decodeFromString(EventFrame.serializer(), text)
                DaemonFrame.Event(o.kind, o.message)
            }
            else -> null
        }
    }

    @Serializable
    private data class EventFrame(val kind: String = "", val message: String = "")

    /** Approve/Deny an owner-gated action. M.U.S.E. enforces policy server-side. */
    fun resolveAuth(id: String, approve: Boolean) {
        val body = """{"decision":"${if (approve) "approve" else "deny"}"}"""
            .toRequestBody(jsonMedia)
        val req = authed(
            Request.Builder().url("${baseUrl.trimEnd('/')}/api/auth/$id/resolve").post(body)
        ).build()
        http.newCall(req).execute().close()
    }

    /** Share-sheet → new M.U.S.E. goal. */
    fun sendGoal(text: String) {
        val body = json.encodeToString(GoalReq.serializer(), GoalReq(text)).toRequestBody(jsonMedia)
        val req = authed(
            Request.Builder().url("${baseUrl.trimEnd('/')}/api/goals").post(body)
        ).build()
        http.newCall(req).execute().close()
    }

    @Serializable
    private data class GoalReq(val text: String, val source: String = "android-share")
}
