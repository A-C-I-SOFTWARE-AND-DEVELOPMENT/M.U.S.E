package com.aci.hermes.approvals

import com.aci.hermes.safety.RiskTier
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProofEngineTest {

    @Test fun risky_render_omits_impact_block() {
        val ap = Approval(summary = "rename", description = "x", tier = RiskTier.RISKY)
        val out = ProofEngine.render(ap)
        assertTrue(out.contains("Tier: RISKY"))
        assertFalse(out.contains("Impact"))
    }

    @Test fun serious_render_includes_two_tap_reminder() {
        val ap = Approval(summary = "delete", description = "x", tier = RiskTier.SERIOUS)
        val out = ProofEngine.render(ap)
        assertTrue(out.contains("SERIOUS"))
        assertTrue(out.contains("confirm twice"))
    }

    @Test fun critical_render_includes_full_impact_and_rollback() {
        val ap = Approval(
            summary = "drop table",
            description = "x",
            tier = RiskTier.CRITICAL,
            impact = Approval.ImpactReport(
                summary = "Deletes 50M rows.",
                affectedSurfaces = listOf("prod-db", "metrics"),
                rollback = "Restore from snapshot 2026-05-25.",
                estimatedDurationSeconds = 90,
            ),
        )
        val out = ProofEngine.render(ap)
        assertTrue(out.contains("Tier: CRITICAL"))
        assertTrue(out.contains("Deletes 50M rows"))
        assertTrue(out.contains("prod-db"))
        assertTrue(out.contains("Rollback plan"))
        assertTrue(out.contains("Restore from snapshot"))
        assertTrue(out.contains("Estimated duration: 90s"))
    }
}
