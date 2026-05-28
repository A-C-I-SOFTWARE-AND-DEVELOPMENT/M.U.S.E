package com.aci.hermes.ui.jarvis

import com.aci.hermes.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Pins the [AvatarActivity] enum's contract: every value has a
 * status string resource and an icon-state mapping. Adding or
 * removing a value should be a deliberate change paid for here.
 */
class AvatarActivityTest {

    @Test
    fun enum_lists_the_eight_canonical_activities() {
        assertEquals(
            listOf(
                "Idle", "Thinking", "Talking", "Working",
                "Coding", "Testing", "Blocked", "WaitingForApproval",
            ),
            AvatarActivity.entries.map { it.name },
        )
    }

    @Test
    fun every_activity_has_a_distinct_status_string_resource_id() {
        val ids = AvatarActivity.entries.map { it.statusStringResId }
        assertEquals(
            "every activity must have a unique status string",
            ids.size,
            ids.toSet().size,
        )
    }

    @Test
    fun status_string_ids_are_real_R_string_resources() {
        // Each id should equal one of the published R.string.avatar_status_*
        // resource ids. If a rename / removal happens this fails first.
        assertEquals(R.string.avatar_status_idle, AvatarActivity.Idle.statusStringResId)
        assertEquals(R.string.avatar_status_thinking, AvatarActivity.Thinking.statusStringResId)
        assertEquals(R.string.avatar_status_talking, AvatarActivity.Talking.statusStringResId)
        assertEquals(R.string.avatar_status_working, AvatarActivity.Working.statusStringResId)
        assertEquals(R.string.avatar_status_coding, AvatarActivity.Coding.statusStringResId)
        assertEquals(R.string.avatar_status_testing, AvatarActivity.Testing.statusStringResId)
        assertEquals(R.string.avatar_status_blocked, AvatarActivity.Blocked.statusStringResId)
        assertEquals(
            R.string.avatar_status_waiting_for_approval,
            AvatarActivity.WaitingForApproval.statusStringResId,
        )
    }

    @Test
    fun icon_state_mapping_collapses_coding_and_testing_under_working() {
        assertEquals(IconState.WORKING, AvatarActivity.Working.toIconState())
        assertEquals(IconState.WORKING, AvatarActivity.Coding.toIconState())
        assertEquals(IconState.WORKING, AvatarActivity.Testing.toIconState())
    }

    @Test
    fun icon_state_mapping_for_safety_relevant_activities_is_exact() {
        assertEquals(IconState.BLOCKED, AvatarActivity.Blocked.toIconState())
        assertEquals(
            IconState.WAITING_FOR_APPROVAL,
            AvatarActivity.WaitingForApproval.toIconState(),
        )
    }

    @Test
    fun idle_and_thinking_and_talking_map_to_distinct_icon_states() {
        assertNotEquals(
            AvatarActivity.Idle.toIconState(),
            AvatarActivity.Thinking.toIconState(),
        )
        assertNotEquals(
            AvatarActivity.Thinking.toIconState(),
            AvatarActivity.Talking.toIconState(),
        )
    }
}
