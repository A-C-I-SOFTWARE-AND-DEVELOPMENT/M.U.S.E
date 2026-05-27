package com.aci.hermes.ui.jarvis

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Pure-logic tests for [IconStateMapper]. No Android dependencies —
 * runs in `app/src/test` under stock JVM JUnit.
 */
class IconStateMapperTest {

    @Test
    fun `idle when nothing is happening`() {
        val state = IconStateMapper.map(IconStateInputs())
        assertEquals(IconState.IDLE, state)
    }

    @Test
    fun `offline wins over everything else`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                gatewayOnline = false,
                listening = true,
                thinking = true,
                criticalActionPending = true,
                pendingApproval = true,
            ),
        )
        assertEquals(IconState.OFFLINE, state)
    }

    @Test
    fun `critical wins over serious`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                criticalActionPending = true,
                seriousActionPending = true,
            ),
        )
        assertEquals(IconState.CRITICAL_ACTION_PENDING, state)
    }

    @Test
    fun `serious wins over waiting for approval`() {
        val state = IconStateMapper.map(
            IconStateInputs(
                seriousActionPending = true,
                pendingApproval = true,
            ),
        )
        assertEquals(IconState.SERIOUS_ACTION_PENDING, state)
    }

    @Test
    fun `blocked wins over warning`() {
        val state = IconStateMapper.map(
            IconStateInputs(blocked = true, warning = true),
        )
        assertEquals(IconState.BLOCKED, state)
    }

    @Test
    fun `listening wins over thinking and working`() {
        val state = IconStateMapper.map(
            IconStateInputs(listening = true, thinking = true, working = true),
        )
        assertEquals(IconState.LISTENING, state)
    }

    @Test
    fun `speaking wins over listening`() {
        val state = IconStateMapper.map(
            IconStateInputs(speaking = true, listening = true),
        )
        assertEquals(IconState.SPEAKING, state)
    }

    @Test
    fun `working maps when only working flag is set`() {
        val state = IconStateMapper.map(IconStateInputs(working = true))
        assertEquals(IconState.WORKING, state)
    }

    @Test
    fun `thinking maps when only thinking flag is set`() {
        val state = IconStateMapper.map(IconStateInputs(thinking = true))
        assertEquals(IconState.THINKING, state)
    }

    @Test
    fun `listening maps when only listening flag is set`() {
        val state = IconStateMapper.map(IconStateInputs(listening = true))
        assertEquals(IconState.LISTENING, state)
    }

    @Test
    fun `waiting for approval maps cleanly`() {
        val state = IconStateMapper.map(IconStateInputs(pendingApproval = true))
        assertEquals(IconState.WAITING_FOR_APPROVAL, state)
    }

    @Test
    fun `warning maps cleanly`() {
        val state = IconStateMapper.map(IconStateInputs(warning = true))
        assertEquals(IconState.WARNING, state)
    }

    @Test
    fun `recent completion maps to complete when alone`() {
        val state = IconStateMapper.map(IconStateInputs(recentCompletion = true))
        assertEquals(IconState.COMPLETE, state)
    }

    @Test
    fun `completion is suppressed by any active work`() {
        val state = IconStateMapper.map(
            IconStateInputs(recentCompletion = true, working = true),
        )
        assertEquals(IconState.WORKING, state)
    }

    @Test
    fun `serious and critical map to distinct states`() {
        val serious = IconStateMapper.map(IconStateInputs(seriousActionPending = true))
        val critical = IconStateMapper.map(IconStateInputs(criticalActionPending = true))
        assertEquals(IconState.SERIOUS_ACTION_PENDING, serious)
        assertEquals(IconState.CRITICAL_ACTION_PENDING, critical)
    }
}
