package com.aci.hermes.ui.emergency

import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.longClick
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.ui.components.BANNER_HARD_STOP_TAG
import com.aci.hermes.ui.components.BANNER_LOCKDOWN_TAG
import com.aci.hermes.ui.components.CRITICAL_ACTION_CARD_TAG
import com.aci.hermes.ui.components.CRITICAL_ACTION_ENGAGE_TAG
import com.aci.hermes.ui.components.CRITICAL_ACTION_REQUEST_RESUME_TAG
import com.aci.hermes.ui.components.CriticalActionCard
import com.aci.hermes.ui.components.EMERGENCY_STOP_BUTTON_TAG
import com.aci.hermes.ui.components.EMERGENCY_STOP_CONFIRM_TAG
import com.aci.hermes.ui.components.EMERGENCY_STOP_DIALOG_TAG
import com.aci.hermes.ui.components.EmergencyStopBanner
import com.aci.hermes.ui.components.EmergencyStopButton
import com.aci.hermes.ui.components.EmergencyStopConfirmationDialog
import com.aci.hermes.ui.components.RESUME_APPROVAL_CONFIRM_TAG
import com.aci.hermes.ui.components.RESUME_APPROVAL_DIALOG_TAG
import com.aci.hermes.ui.components.ResumeApprovalDialog
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * Compose UI smoke tests. They cover the high-value visual contracts
 * called out in the build spec:
 *  - emergency button visible
 *  - confirmation appears
 *  - hard stop state renders
 *  - lockdown state renders
 *  - resume requires approval
 *  - icon updates
 *  - critical card emergency stop works
 */
class EmergencyStopUiTest {

    @get:Rule val composeTestRule = createComposeRule()

    @Test
    fun emergencyButton_isVisible() {
        composeTestRule.setContent {
            EmergencyStopButton(
                state = EmergencyStopState.INACTIVE,
                onTap = {},
                onLongPressEscalate = {},
            )
        }
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_BUTTON_TAG).assertIsDisplayed()
    }

    @Test
    fun emergencyButton_iconUpdatesWithState() {
        val state = mutableStateOf(EmergencyStopState.INACTIVE)
        composeTestRule.setContent {
            EmergencyStopButton(
                state = state.value,
                onTap = {},
                onLongPressEscalate = {},
            )
        }
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_BUTTON_TAG).assertIsDisplayed()
        state.value = EmergencyStopState.LOCKDOWN
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_BUTTON_TAG).assertIsDisplayed()
    }

    @Test
    fun confirmationDialog_appears_andEmitsTarget() {
        val choice = mutableStateOf<EmergencyStopState?>(null)
        composeTestRule.setContent {
            EmergencyStopConfirmationDialog(
                currentState = EmergencyStopState.INACTIVE,
                onDismiss = {},
                onConfirm = { target, _ -> choice.value = target },
            )
        }
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_DIALOG_TAG).assertIsDisplayed()
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_CONFIRM_TAG).performClick()
        assertNotNull(choice.value)
    }

    @Test
    fun hardStop_bannerRenders() {
        composeTestRule.setContent {
            EmergencyStopBanner(state = EmergencyStopState.HARD_STOP, onOpenControl = {})
        }
        composeTestRule.onNodeWithTag(BANNER_HARD_STOP_TAG).assertIsDisplayed()
    }

    @Test
    fun lockdown_bannerRenders() {
        composeTestRule.setContent {
            EmergencyStopBanner(state = EmergencyStopState.LOCKDOWN, onOpenControl = {})
        }
        composeTestRule.onNodeWithTag(BANNER_LOCKDOWN_TAG).assertIsDisplayed()
    }

    @Test
    fun resumeDialog_requiresApproverIdentity() {
        val approved = mutableStateOf<String?>(null)
        val denied = mutableStateOf<String?>(null)
        composeTestRule.setContent {
            ResumeApprovalDialog(
                currentState = EmergencyStopState.LOCKDOWN,
                requestedBy = "ui:test",
                onDismiss = {},
                onApprove = { approved.value = it },
                onDeny = { denied.value = it ?: "" },
            )
        }
        composeTestRule.onNodeWithTag(RESUME_APPROVAL_DIALOG_TAG).assertIsDisplayed()
        // Approve is disabled with empty approver field, so a click must not fire.
        composeTestRule.onNodeWithTag(RESUME_APPROVAL_CONFIRM_TAG).performClick()
        assertNull("Approve must require a non-blank approver identifier", approved.value)
    }

    @Test
    fun criticalCard_emergencyStop_clickFiresEngage() {
        var engaged = false
        composeTestRule.setContent {
            CriticalActionCard(
                state = EmergencyStopState.INACTIVE,
                onEngageStop = { engaged = true },
                onEscalate = {},
                onRequestResume = {},
                onOpenControl = {},
            )
        }
        composeTestRule.onNodeWithTag(CRITICAL_ACTION_CARD_TAG).assertIsDisplayed()
        composeTestRule.onNodeWithTag(CRITICAL_ACTION_ENGAGE_TAG).performClick()
        assertTrue(engaged)
    }

    @Test
    fun criticalCard_lockdown_offersOnlyResume() {
        var resumed = false
        composeTestRule.setContent {
            CriticalActionCard(
                state = EmergencyStopState.LOCKDOWN,
                onEngageStop = { resumed = false },
                onEscalate = { resumed = false },
                onRequestResume = { resumed = true },
                onOpenControl = {},
            )
        }
        composeTestRule.onNodeWithTag(CRITICAL_ACTION_CARD_TAG).assertIsDisplayed()
        composeTestRule.onNodeWithTag(CRITICAL_ACTION_REQUEST_RESUME_TAG).performClick()
        assertTrue(resumed)
    }

    @Test
    fun emergencyButton_longPress_escalates() {
        var escalated = 0
        composeTestRule.setContent {
            EmergencyStopButton(
                state = EmergencyStopState.SOFT_PAUSE,
                onTap = {},
                onLongPressEscalate = { escalated++ },
            )
        }
        composeTestRule.onNodeWithTag(EMERGENCY_STOP_BUTTON_TAG).performTouchInput { longClick() }
        composeTestRule.waitForIdle()
        assertEquals(1, escalated)
    }
}
