package com.aci.hermes.safety

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RiskTierTest {

    @Test fun safe_requires_no_confirmation_and_no_impact_report() {
        assertEquals(0, RiskTier.SAFE.confirmationsRequired)
        assertFalse(RiskTier.SAFE.requiresImpactReport)
        assertFalse(RiskTier.SAFE.requiresRollbackPlan)
    }

    @Test fun risky_asks_once() {
        assertEquals(1, RiskTier.RISKY.confirmationsRequired)
        assertFalse(RiskTier.RISKY.requiresImpactReport)
    }

    @Test fun serious_asks_twice() {
        assertEquals(2, RiskTier.SERIOUS.confirmationsRequired)
        assertFalse(RiskTier.SERIOUS.requiresImpactReport)
        assertFalse(RiskTier.SERIOUS.requiresRollbackPlan)
    }

    @Test fun critical_requires_impact_report_rollback_and_two_confirmations() {
        assertEquals(2, RiskTier.CRITICAL.confirmationsRequired)
        assertTrue(RiskTier.CRITICAL.requiresImpactReport)
        assertTrue(RiskTier.CRITICAL.requiresRollbackPlan)
    }
}
