package com.aci.hermes

import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.AuditSeverity
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EmergencyStopTest {

    @Test
    fun arm_sets_armed_true_with_reason() {
        val es = EmergencyStopController()
        val ev = es.arm("device compromised")
        assertTrue(es.isArmed())
        assertEquals("emergency_stop_arm", ev.action)
        assertEquals(AuditSeverity.CRITICAL, ev.severity)
        assertNotNull(es.state.value.since)
    }

    @Test
    fun arm_without_reason_is_allowed() {
        val es = EmergencyStopController()
        es.arm(null)
        assertTrue(es.isArmed())
        assertNull(es.state.value.reason)
    }

    @Test
    fun clear_marks_disarmed_and_emits_audit() {
        val es = EmergencyStopController()
        es.arm(null)
        val cleared = es.clear("all good")
        assertFalse(es.isArmed())
        assertEquals("emergency_stop_clear", cleared.action)
        assertEquals(AuditSeverity.NOTICE, cleared.severity)
    }

    @Test
    fun arm_audit_event_is_appendable_to_audit_repo() {
        val es = EmergencyStopController()
        val audit = AuditRepository()
        val ev = es.arm("breach")
        val appended = audit.append(ev)
        assertEquals(1, audit.events.value.size)
        assertEquals(appended.id, audit.events.value.first().id)
        assertTrue(appended.proofHash.startsWith("0x"))
    }

    @Test
    fun arm_then_clear_yields_audit_trail() {
        val es = EmergencyStopController()
        val audit = AuditRepository()
        audit.append(es.arm("first"))
        audit.append(es.clear("done"))
        assertEquals(2, audit.events.value.size)
        // Newer entry surfaces first.
        assertEquals("emergency_stop_clear", audit.events.value.first().action)
        assertEquals("emergency_stop_arm", audit.events.value.last().action)
    }
}
