package com.aci.hermes.ui.components.icon

import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.IconStateInputs
import com.aci.hermes.ui.jarvis.IconStateMapper
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Asserts the "needs approval" wire-up from inputs to visible state.
 * `pendingApproval` is the non-destructive variant — it must map to
 * [IconState.WAITING_FOR_APPROVAL]. Critical actions must always win
 * when both signals are live (safer story dominates).
 */
class NeedsApprovalMappingTest {

    @Test
    fun `pendingApproval input resolves to WAITING_FOR_APPROVAL`() {
        val state = IconStateMapper.map(IconStateInputs(pendingApproval = true))
        assertEquals(IconState.WAITING_FOR_APPROVAL, state)
    }

    @Test
    fun `critical action beats pending approval`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                pendingApproval = true,
                criticalActionPending = true,
            ),
        )
        assertEquals(IconState.CRITICAL_ACTION_PENDING, state)
    }

    @Test
    fun `serious action beats pending approval`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                pendingApproval = true,
                seriousActionPending = true,
            ),
        )
        assertEquals(IconState.SERIOUS_ACTION_PENDING, state)
    }

    @Test
    fun `approval beats listening`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                pendingApproval = true,
                listening = true,
            ),
        )
        // Listening is a "what the assistant is doing" signal; approval
        // is a "what the user must do" signal. The user's signal wins.
        assertEquals(IconState.WAITING_FOR_APPROVAL, state)
    }

    @Test
    fun `offline overrides approval`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                gatewayOnline = false,
                pendingApproval = true,
                criticalActionPending = true,
            ),
        )
        assertEquals(IconState.OFFLINE, state)
    }
}
