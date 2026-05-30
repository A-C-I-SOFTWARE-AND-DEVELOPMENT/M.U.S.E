package com.aci.hermes.data.cockpit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure transport-helper tests — no socket, no Android. Covers URL
 * joining, bearer attachment, and the error-envelope decode/fallback
 * that the cockpit UI branches on.
 */
class CockpitHttpTest {

    private val json = CockpitHttp.json

    @Test
    fun `joinUrl avoids double slashes and normalises leading slash`() {
        assertEquals("http://127.0.0.1:8765/v1/health", CockpitHttp.joinUrl("http://127.0.0.1:8765", "/v1/health"))
        assertEquals("http://127.0.0.1:8765/v1/health", CockpitHttp.joinUrl("http://127.0.0.1:8765/", "/v1/health"))
        assertEquals("http://127.0.0.1:8765/v1/health", CockpitHttp.joinUrl("http://127.0.0.1:8765", "v1/health"))
        assertEquals("http://127.0.0.1:8765/v1/health", CockpitHttp.joinUrl("  http://127.0.0.1:8765/  ", "v1/health"))
    }

    @Test
    fun `headers attach bearer only when token present`() {
        val withToken = CockpitHttp.headers("abc123")
        assertEquals("Bearer abc123", withToken["Authorization"])
        assertEquals("application/json", withToken["Accept"])

        assertNull(CockpitHttp.headers(null)["Authorization"])
        assertNull(CockpitHttp.headers("")["Authorization"])
        assertNull(CockpitHttp.headers("   ")["Authorization"])
    }

    @Test
    fun `parseError decodes the contract envelope`() {
        val body = """{"error":{"code":"validation_failed","message":"bad key","details":{"key":"missing"}}}"""
        val err = CockpitHttp.parseError(json, 400, body)
        assertEquals("validation_failed", err.code)
        assertEquals("bad key", err.message)
        assertEquals("missing", err.details?.get("key"))
    }

    @Test
    fun `parseError synthesizes a code from status when body is not an envelope`() {
        assertEquals("unauthorized", CockpitHttp.parseError(json, 401, "nope").code)
        assertEquals("forbidden", CockpitHttp.parseError(json, 403, "").code)
        assertEquals("not_found", CockpitHttp.parseError(json, 404, "").code)
        assertEquals("conflict", CockpitHttp.parseError(json, 409, "").code)
        assertEquals("unprocessable", CockpitHttp.parseError(json, 422, "").code)
        assertEquals("backend_error", CockpitHttp.parseError(json, 500, "boom").code)
    }

    @Test
    fun `tolerant json ignores unknown keys`() {
        val status = json.decodeFromString(
            RuntimeStatus.serializer(),
            """
            {
              "gateway": {"version":"0.1.0","started_at":"t","pid":7,"mode":"local","extra":"ignored"},
              "host": {"platform":"Linux","arch":"x86_64","hostname":"h"},
              "queue": {"running":1,"queued":2,"waiting_approval":0},
              "future_field": true
            }
            """.trimIndent(),
        )
        assertEquals("local", status.gateway.mode)
        assertEquals(1, status.queue.running)
        assertEquals("Linux", status.host.platform)
    }

    @Test
    fun `health status resolves version across both response variants`() {
        val live = json.decodeFromString(
            HealthStatus.serializer(),
            """{"ok":true,"service":"hermes-cockpit","api_version":"1.0.0","gateway_version":"0.14.0"}""",
        )
        assertTrue(live.ok)
        assertEquals("0.14.0", live.resolvedVersion)

        val legacy = json.decodeFromString(
            HealthStatus.serializer(),
            """{"ok":false,"version":"0.9.0","message":"unhealthy"}""",
        )
        assertFalse(legacy.ok)
        assertEquals("0.9.0", legacy.resolvedVersion)
    }
}
