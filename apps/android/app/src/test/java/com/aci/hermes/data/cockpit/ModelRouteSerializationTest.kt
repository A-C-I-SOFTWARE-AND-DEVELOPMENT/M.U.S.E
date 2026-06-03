package com.aci.hermes.data.cockpit

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Kotlin DTOs must decode the exact JSON the gateway emits
 * (`gateway/cockpit/handlers.py::model_routes`). These run on the JVM with no
 * emulator and are the contract pin between the two sides.
 */
class ModelRouteSerializationTest {

    private val json = CockpitHttp.json

    @Test
    fun `decodes a full model-routes payload`() {
        val raw = """
            {
              "routes": [
                {
                  "task_class": "coding_build",
                  "chosen": "claude",
                  "route_tier": "claude_code_worker",
                  "risk_class": "RC3",
                  "fallback_chain": ["claude", "qwen3-coder"],
                  "why": "coding_build: route -> claude",
                  "evidence": [{"model": "claude", "score": 0.81, "samples": 3}],
                  "local_first": false,
                  "paid_allowed": true,
                  "paid_enabled": false,
                  "owner_override": null
                }
              ],
              "task_classes": ["coding_build"],
              "paid_enabled": false,
              "overrides": {"task_overrides": {}, "paid_enabled": null, "updated_at": null},
              "generated_at": "2026-06-03T00:00:00Z"
            }
        """.trimIndent()

        val parsed = json.decodeFromString(ModelRouteList.serializer(), raw)
        assertEquals(1, parsed.routes.size)
        val d = parsed.routes[0]
        assertEquals("coding_build", d.taskClass)
        assertEquals("claude", d.chosen)
        assertEquals("claude_code_worker", d.routeTier)
        assertEquals(listOf("claude", "qwen3-coder"), d.fallbackChain)
        assertEquals("claude", d.evidence[0].model)
        assertEquals(0.81, d.evidence[0].score, 1e-9)
        assertTrue(d.paidAllowed)
        assertFalse(d.isOverridden)
    }

    @Test
    fun `tolerates a degraded honest-empty payload`() {
        val parsed = json.decodeFromString(
            ModelRouteList.serializer(),
            """{"routes": [], "error": "boom"}""",
        )
        assertTrue(parsed.routes.isEmpty())
        assertEquals("boom", parsed.error)
    }

    @Test
    fun `override request encodes only the fields set`() {
        val body = json.encodeToString(
            ModelRouteOverrideRequest.serializer(),
            ModelRouteOverrideRequest(taskClass = "summarization", model = "qwen"),
        )
        assertTrue(body.contains("\"task_class\":\"summarization\""))
        assertTrue(body.contains("\"model\":\"qwen\""))
    }

    @Test
    fun `decodes an owner-overridden decision`() {
        val parsed = json.decodeFromString(
            ModelRouteDecision.serializer(),
            """
            {"task_class":"summarization","chosen":"my-model","route_tier":"owner_override",
             "risk_class":"RC1","fallback_chain":["my-model"],"why":"pinned","evidence":[],
             "local_first":true,"paid_allowed":false,"paid_enabled":false,"owner_override":"my-model"}
            """.trimIndent(),
        )
        assertTrue(parsed.isOverridden)
        assertEquals("my-model", parsed.ownerOverride)
        assertNull(parsed.evidence.firstOrNull())
    }
}
