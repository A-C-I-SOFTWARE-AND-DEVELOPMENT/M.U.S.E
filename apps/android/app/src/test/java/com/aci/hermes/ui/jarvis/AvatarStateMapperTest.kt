package com.aci.hermes.ui.jarvis

import com.aci.hermes.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the avatar state-machine contract. The mapper is the single
 * source of truth for (icon-state-inputs × activity × reduced-motion)
 * → render spec; every safety floor and every status-text resolution
 * is covered here so a refactor that quietly downgrades a safety
 * signal fails the build.
 */
class AvatarStateMapperTest {

    private val onlineIdle = IconStateInputs(gatewayOnline = true)

    // ─── Per-activity mapping (input collapses to IDLE) ───────────

    @Test
    fun idle_activity_maps_to_idle_icon_state_and_idle_status() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Idle)
        assertEquals(IconState.IDLE, spec.iconState)
        assertEquals(AvatarActivity.Idle, spec.activity)
        assertEquals(R.string.avatar_status_idle, spec.statusStringResId)
    }

    @Test
    fun thinking_activity_maps_to_thinking_icon_state() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Thinking)
        assertEquals(IconState.THINKING, spec.iconState)
        assertEquals(AvatarActivity.Thinking, spec.activity)
        assertEquals(R.string.avatar_status_thinking, spec.statusStringResId)
    }

    @Test
    fun talking_activity_maps_to_speaking_icon_state() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Talking)
        assertEquals(IconState.SPEAKING, spec.iconState)
        assertEquals(AvatarActivity.Talking, spec.activity)
        assertEquals(R.string.avatar_status_talking, spec.statusStringResId)
    }

    @Test
    fun working_activity_maps_to_working_icon_state() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Working)
        assertEquals(IconState.WORKING, spec.iconState)
        assertEquals(AvatarActivity.Working, spec.activity)
        assertEquals(R.string.avatar_status_working, spec.statusStringResId)
    }

    @Test
    fun coding_activity_refines_working_with_coding_status() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Coding)
        // Icon-state stays WORKING (color/ring) but the activity
        // refinement surfaces in the status text.
        assertEquals(IconState.WORKING, spec.iconState)
        assertEquals(AvatarActivity.Coding, spec.activity)
        assertEquals(R.string.avatar_status_coding, spec.statusStringResId)
    }

    @Test
    fun testing_activity_refines_working_with_testing_status() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Testing)
        assertEquals(IconState.WORKING, spec.iconState)
        assertEquals(AvatarActivity.Testing, spec.activity)
        assertEquals(R.string.avatar_status_testing, spec.statusStringResId)
    }

    @Test
    fun blocked_activity_maps_to_blocked_icon_state() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Blocked)
        assertEquals(IconState.BLOCKED, spec.iconState)
        assertEquals(AvatarActivity.Blocked, spec.activity)
        assertEquals(R.string.avatar_status_blocked, spec.statusStringResId)
    }

    @Test
    fun waiting_for_approval_activity_maps_to_waiting_icon_state() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.WaitingForApproval)
        assertEquals(IconState.WAITING_FOR_APPROVAL, spec.iconState)
        assertEquals(AvatarActivity.WaitingForApproval, spec.activity)
        assertEquals(R.string.avatar_status_waiting_for_approval, spec.statusStringResId)
    }

    // ─── Safety floor — inputs always win ────────────────────────────

    @Test
    fun critical_action_pending_overrides_any_activity_hint() {
        val inputs = IconStateInputs(gatewayOnline = true, criticalActionPending = true)
        val spec = AvatarStateMapper.map(inputs, AvatarActivity.Coding)
        // Critical safety must not be hidden by an activity hint.
        assertEquals(IconState.CRITICAL_ACTION_PENDING, spec.iconState)
        assertEquals(AvatarActivity.WaitingForApproval, spec.activity)
        assertEquals(R.string.avatar_status_waiting_for_approval, spec.statusStringResId)
    }

    @Test
    fun serious_action_pending_overrides_any_activity_hint() {
        val inputs = IconStateInputs(gatewayOnline = true, seriousActionPending = true)
        val spec = AvatarStateMapper.map(inputs, AvatarActivity.Testing)
        assertEquals(IconState.SERIOUS_ACTION_PENDING, spec.iconState)
        assertEquals(AvatarActivity.WaitingForApproval, spec.activity)
    }

    @Test
    fun blocked_input_overrides_any_activity_hint() {
        val inputs = IconStateInputs(gatewayOnline = true, blocked = true)
        val spec = AvatarStateMapper.map(inputs, AvatarActivity.Working)
        assertEquals(IconState.BLOCKED, spec.iconState)
        assertEquals(AvatarActivity.Blocked, spec.activity)
        assertEquals(R.string.avatar_status_blocked, spec.statusStringResId)
    }

    @Test
    fun offline_overrides_any_activity_hint() {
        val inputs = IconStateInputs(gatewayOnline = false)
        val spec = AvatarStateMapper.map(inputs, AvatarActivity.Thinking)
        assertEquals(IconState.OFFLINE, spec.iconState)
        assertEquals(AvatarActivity.Blocked, spec.activity)
    }

    @Test
    fun listening_input_wins_over_thinking_activity() {
        // The session's actual state (mic open) is more trustworthy than
        // the activity hint someone forgot to update.
        val inputs = IconStateInputs(gatewayOnline = true, listening = true)
        val spec = AvatarStateMapper.map(inputs, AvatarActivity.Thinking)
        assertEquals(IconState.LISTENING, spec.iconState)
        assertEquals(AvatarActivity.Talking, spec.activity)
    }

    // ─── Reduced motion ──────────────────────────────────────────────

    @Test
    fun reduced_motion_zeroes_effective_pulse_amplitude() {
        val spec = AvatarStateMapper.map(
            inputs = onlineIdle,
            activity = AvatarActivity.Thinking,
            reducedMotion = true,
        )
        assertEquals(0f, spec.effectivePulseAmplitude, 0.0001f)
        assertTrue("reducedMotion flag must propagate", spec.reducedMotion)
    }

    @Test
    fun motion_on_preserves_appearance_pulse_amplitude() {
        val spec = AvatarStateMapper.map(
            inputs = onlineIdle,
            activity = AvatarActivity.Working,
            reducedMotion = false,
        )
        assertEquals(spec.appearance.pulseAmplitude, spec.effectivePulseAmplitude, 0.0001f)
    }

    // ─── Appearance still resolves from canonical palette ───────────

    @Test
    fun appearance_is_resolved_via_JarvisIconColors_not_re_invented() {
        val spec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Thinking)
        // Same icon-state must yield the same appearance whether you
        // come in via this mapper or via JarvisIconColors directly.
        assertEquals(
            JarvisIconColors.appearanceFor(IconState.THINKING),
            spec.appearance,
        )
    }

    @Test
    fun appearance_for_safety_floor_differs_from_idle() {
        val criticalSpec = AvatarStateMapper.map(
            IconStateInputs(gatewayOnline = true, criticalActionPending = true),
            AvatarActivity.Coding,
        )
        val idleSpec = AvatarStateMapper.map(onlineIdle, AvatarActivity.Coding)
        assertNotEquals(idleSpec.appearance, criticalSpec.appearance)
    }
}
