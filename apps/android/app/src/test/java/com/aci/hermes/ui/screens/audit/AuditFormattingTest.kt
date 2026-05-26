package com.aci.hermes.ui.screens.audit

import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.VerificationStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AuditFormattingTest {

    @Test
    fun `failure-like action results are marked as failures`() {
        assertTrue(ActionResult.FAILED.isFailureLike())
        assertTrue(ActionResult.ROLLED_BACK.isFailureLike())
        assertTrue(ActionResult.BLOCKED.isFailureLike())
        assertFalse(ActionResult.SUCCESS.isFailureLike())
        assertFalse(ActionResult.PARTIAL.isFailureLike())
    }

    @Test
    fun `every enum has a human readable label`() {
        RiskTier.values().forEach { assertTrue(it.displayLabel().isNotBlank()) }
        ApprovalState.values().forEach { assertTrue(it.displayLabel().isNotBlank()) }
        ActionResult.values().forEach { assertTrue(it.displayLabel().isNotBlank()) }
        RouteDestination.values().forEach { assertTrue(it.displayLabel().isNotBlank()) }
        VerificationStatus.values().forEach { assertTrue(it.displayLabel().isNotBlank()) }
    }

    @Test
    fun `confidence label formats sane values`() {
        assertEquals("—", confidenceLabel(0f))
        assertEquals("88% confidence", confidenceLabel(0.88f))
        assertEquals("100% confidence", confidenceLabel(1f))
    }
}
