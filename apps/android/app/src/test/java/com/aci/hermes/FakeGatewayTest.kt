package com.aci.hermes

import com.aci.hermes.data.gateway.ConnectionState
import com.aci.hermes.data.gateway.FakeGatewayClient
import com.aci.hermes.data.gateway.GatewayMode
import com.aci.hermes.data.model.Approval
import com.aci.hermes.data.model.ApprovalDecision
import com.aci.hermes.data.model.ApprovalRisk
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FakeGatewayTest {

    @Test
    fun start_seeds_fixtures_and_marks_connection() = runTest {
        val gw = FakeGatewayClient()
        assertEquals(GatewayMode.MOCK, gw.mode)
        gw.start()
        assertTrue(gw.approvals.isNotEmpty())
        assertEquals(ConnectionState.Connected, gw.connection.first())
    }

    @Test
    fun fixtures_cover_full_risk_gradient() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        val risks = gw.approvals.map { it.risk }.toSet()
        assertTrue(ApprovalRisk.LOW in risks)
        assertTrue(ApprovalRisk.MEDIUM in risks)
        assertTrue(ApprovalRisk.HIGH in risks)
        assertTrue(ApprovalRisk.CRITICAL in risks)
    }

    @Test
    fun critical_fixture_carries_impact_report() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        val critical = gw.approvals.first { it.risk == ApprovalRisk.CRITICAL }
        assertNotNull("critical approval should have impact report", critical.impact)
        assertEquals(false, critical.impact!!.reversible)
    }

    @Test
    fun decide_records_audit_entry() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        val pending = gw.approvals.first { it.risk == ApprovalRisk.MEDIUM }
        gw.decideApproval(pending, approve = true, notes = "ok")
        val decided = gw.approvals.first { it.id == pending.id }
        assertEquals(ApprovalDecision.APPROVED, decided.decision)
        assertTrue(gw.audit.isNotEmpty())
        assertEquals("approve", gw.audit.last().action)
    }

    @Test
    fun chat_destructive_input_creates_critical_approval() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        val before = gw.approvals.size
        val response = gw.submitChat("please wipe everything")
        assertNotNull(response.createdApprovalId)
        val after: List<Approval> = gw.approvals
        assertTrue(after.size > before)
        val created = after.first { it.id == response.createdApprovalId }
        assertEquals(ApprovalRisk.CRITICAL, created.risk)
    }

    @Test
    fun stop_marks_connection_disconnected() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        gw.stop()
        assertEquals(ConnectionState.Disconnected, gw.connection.first())
    }

    @Test
    fun heartbeat_does_not_throw_and_keeps_running() = runTest {
        val gw = FakeGatewayClient()
        gw.start()
        gw.heartbeat()
        gw.heartbeat()
        // Connection should still be marked connected after pings.
        assertEquals(ConnectionState.Connected, gw.connection.first())
    }
}
