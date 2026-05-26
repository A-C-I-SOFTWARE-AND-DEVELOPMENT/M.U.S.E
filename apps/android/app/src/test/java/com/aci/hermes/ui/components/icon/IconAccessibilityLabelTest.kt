package com.aci.hermes.ui.components.icon

import com.aci.hermes.ui.jarvis.IconState
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the accessibility labels and action hints the interactive icon
 * surfaces to TalkBack. The mission-required six states each need a
 * non-blank label distinct from the others, and the action hint must
 * tell the user what `Tap` means *in the current state*.
 */
class IconAccessibilityLabelTest {

    private val requiredStates = listOf(
        IconState.IDLE,
        IconState.LISTENING,
        IconState.WORKING,
        IconState.WAITING_FOR_APPROVAL,
        IconState.BLOCKED,
        IconState.CRITICAL_ACTION_PENDING,
    )

    @Test
    fun `every required state has a non-blank semantic label`() {
        requiredStates.forEach { state ->
            val label = state.semanticLabel()
            assertTrue("label blank for $state", label.isNotBlank())
        }
    }

    @Test
    fun `required states have pairwise distinct labels`() {
        val labels = requiredStates.map { it.semanticLabel() }
        // 1:1 between state and label across the required set.
        assertTrue(
            "duplicate labels: $labels",
            labels.size == labels.toSet().size,
        )
    }

    @Test
    fun `emergency stop label is distinct from approval and blocked`() {
        val emergency = IconState.CRITICAL_ACTION_PENDING.semanticLabel()
        assertNotEquals(emergency, IconState.WAITING_FOR_APPROVAL.semanticLabel())
        assertNotEquals(emergency, IconState.BLOCKED.semanticLabel())
        assertNotEquals(emergency, IconState.SERIOUS_ACTION_PENDING.semanticLabel())
    }

    @Test
    fun `action hint differs between listening, approval and idle`() {
        val listening = IconState.LISTENING.semanticActionHint()
        val approval = IconState.WAITING_FOR_APPROVAL.semanticActionHint()
        val idle = IconState.IDLE.semanticActionHint()
        assertNotEquals(listening, approval)
        assertNotEquals(listening, idle)
        assertNotEquals(approval, idle)
    }

    @Test
    fun `approval class states share the review hint`() {
        val approvalHint = IconState.WAITING_FOR_APPROVAL.semanticActionHint()
        assertTrue("approval hint blank", approvalHint.isNotBlank())
        // Serious and critical land on the same "review" hint by design — TalkBack
        // distinguishes them via the contentDescription/stateDescription, not the hint.
        listOf(
            IconState.SERIOUS_ACTION_PENDING,
            IconState.CRITICAL_ACTION_PENDING,
        ).forEach { state ->
            assertTrue(
                "${state.name} hint should reference review: ${state.semanticActionHint()}",
                state.semanticActionHint().contains("review", ignoreCase = true),
            )
        }
    }
}
