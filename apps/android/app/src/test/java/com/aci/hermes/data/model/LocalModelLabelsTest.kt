package com.aci.hermes.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

class LocalModelLabelsTest {

    @Test
    fun `runtime labels are honest`() {
        assertEquals("Runtime reachable", LocalModelLabels.runtime("runtime_reachable"))
        assertEquals("Configured", LocalModelLabels.runtime("configured"))
        assertEquals("Not configured", LocalModelLabels.runtime("not_configured"))
        assertEquals("Not configured", LocalModelLabels.runtime("anything_unknown"))
    }

    @Test
    fun `model label reflects backend status when not smoke-tested`() {
        assertEquals("Variant installed", LocalModelLabels.model("variant_installed", smokeTested = false))
        assertEquals("Promoted for task", LocalModelLabels.model("promoted_for_task", smokeTested = false))
        assertEquals("Fallback only", LocalModelLabels.model("fallback_only", smokeTested = false))
    }

    @Test
    fun `smoke result takes precedence over backend status`() {
        // A passed smoke is the strongest evidence of readiness.
        assertEquals("Smoke-tested", LocalModelLabels.model("variant_installed", smokeTested = true))
        // A failed smoke wins even over a promotion — never show "ready".
        assertEquals(
            "Blocked / error",
            LocalModelLabels.model("promoted_for_task", smokeTested = true, smokeFailed = true),
        )
    }
}
