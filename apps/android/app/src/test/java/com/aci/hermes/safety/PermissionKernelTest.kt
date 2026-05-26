package com.aci.hermes.safety

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class PermissionKernelTest {

    @Test fun fresh_request_returns_show_education_and_moves_to_pending() {
        val kernel = PermissionKernel()
        val step = kernel.requestPermission(JarvisPermission.NOTIFICATIONS)
        assertTrue(step is PermissionKernel.NextStep.ShowEducation)
        assertEquals(
            PermissionState.EDUCATION_PENDING,
            kernel.stateOf(JarvisPermission.NOTIFICATIONS),
        )
    }

    @Test fun cancelling_education_returns_to_not_requested() {
        val kernel = PermissionKernel()
        kernel.requestPermission(JarvisPermission.NOTIFICATIONS)
        kernel.cancelEducation(JarvisPermission.NOTIFICATIONS)
        assertEquals(
            PermissionState.NOT_REQUESTED,
            kernel.stateOf(JarvisPermission.NOTIFICATIONS),
        )
    }

    @Test fun acknowledging_education_unlocks_system_dialog() {
        val kernel = PermissionKernel()
        kernel.requestPermission(JarvisPermission.MICROPHONE)
        val step = kernel.acknowledgeEducation(JarvisPermission.MICROPHONE)
        assertTrue(step is PermissionKernel.NextStep.InvokeSystemDialog)
        assertEquals(
            PermissionState.SYSTEM_PROMPT_PENDING,
            kernel.stateOf(JarvisPermission.MICROPHONE),
        )
        assertTrue(kernel.stateOf(JarvisPermission.MICROPHONE).canInvokeSystemDialog)
    }

    @Test fun granted_request_returns_already_granted() {
        val kernel = PermissionKernel(
            initialStates = mapOf(JarvisPermission.MICROPHONE to PermissionState.GRANTED)
        )
        assertSame(
            PermissionKernel.NextStep.AlreadyGranted,
            kernel.requestPermission(JarvisPermission.MICROPHONE),
        )
    }

    @Test fun permanently_denied_routes_to_settings() {
        val kernel = PermissionKernel(
            initialStates = mapOf(JarvisPermission.NOTIFICATIONS to PermissionState.PERMANENTLY_DENIED)
        )
        val step = kernel.requestPermission(JarvisPermission.NOTIFICATIONS)
        assertTrue(step is PermissionKernel.NextStep.SendToSettings)
    }

    @Test fun denied_after_first_dialog_can_be_re_educated_not_re_prompted_directly() {
        val kernel = PermissionKernel()
        kernel.requestPermission(JarvisPermission.NOTIFICATIONS)
        kernel.acknowledgeEducation(JarvisPermission.NOTIFICATIONS)
        kernel.recordSystemDecision(JarvisPermission.NOTIFICATIONS, granted = false)
        // A re-request must surface education again — not re-launch the OS dialog.
        val step = kernel.requestPermission(JarvisPermission.NOTIFICATIONS)
        assertTrue(step is PermissionKernel.NextStep.ShowEducation)
    }

    @Test fun acknowledge_education_requires_education_pending_state() {
        val kernel = PermissionKernel()
        val ex = runCatching { kernel.acknowledgeEducation(JarvisPermission.NOTIFICATIONS) }
            .exceptionOrNull()
        assertTrue(ex is IllegalArgumentException)
    }

    @Test fun reconcile_upgrades_to_granted_when_os_says_yes() {
        val kernel = PermissionKernel()
        kernel.reconcileFromSystem(JarvisPermission.NOTIFICATIONS, isCurrentlyGranted = true)
        assertEquals(
            PermissionState.GRANTED,
            kernel.stateOf(JarvisPermission.NOTIFICATIONS),
        )
    }

    @Test fun reconcile_downgrades_when_user_revokes_in_settings() {
        val kernel = PermissionKernel(
            initialStates = mapOf(JarvisPermission.MICROPHONE to PermissionState.GRANTED)
        )
        kernel.reconcileFromSystem(JarvisPermission.MICROPHONE, isCurrentlyGranted = false)
        assertEquals(
            PermissionState.DENIED,
            kernel.stateOf(JarvisPermission.MICROPHONE),
        )
    }

    @Test fun sms_and_call_log_are_in_the_phase1_banned_list() {
        val banned = JarvisPermission.phase1Banned
        assertTrue(banned.contains("android.permission.READ_SMS"))
        assertTrue(banned.contains("android.permission.SEND_SMS"))
        assertTrue(banned.contains("android.permission.RECEIVE_SMS"))
        assertTrue(banned.contains("android.permission.READ_CALL_LOG"))
        assertTrue(banned.contains("android.permission.WRITE_CALL_LOG"))
        assertTrue(banned.contains("android.permission.SYSTEM_ALERT_WINDOW"))
    }

    @Test fun jarvis_permissions_enum_only_contains_phase1_allowed_set() {
        // If anyone adds a new JarvisPermission entry, this test forces
        // a deliberate update — Phase 1 is intentionally tiny.
        val names = JarvisPermission.entries.map { it.name }.toSet()
        assertEquals(setOf("NOTIFICATIONS", "MICROPHONE"), names)
    }
}
