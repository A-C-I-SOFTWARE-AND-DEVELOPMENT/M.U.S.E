package com.aci.hermes.automation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PersonalActionPlannerTest {
    private val grants = listOf(
        CapabilityGrant(AndroidCapability.PackageVisibility, AndroidCapabilityStatus.Granted),
        CapabilityGrant(AndroidCapability.Overlay, AndroidCapabilityStatus.Granted),
        CapabilityGrant(AndroidCapability.Accessibility, AndroidCapabilityStatus.Granted),
    )

    @Test
    fun clickFacebookDirectExecutesWhenCapabilitiesAreGranted() {
        val contract = PersonalActionPlanner().buildContract(
            request = "click on Facebook",
            targetAppLabel = "Facebook",
            targetPackage = "com.facebook.katana",
            grants = grants,
        )
        assertEquals(PersonalActionExecutionMode.DirectExecute, contract.executionMode)
        assertTrue(contract.ownerAuthorized)
        assertEquals(emptyList<AndroidCapability>(), contract.missingCapabilities)
    }

    @Test
    fun missingCapabilitiesBlockExecutionButNotOwnerAuthorization() {
        val contract = PersonalActionPlanner().buildContract(
            request = "click on Facebook",
            targetAppLabel = "Facebook",
            targetPackage = "com.facebook.katana",
        )
        assertEquals(PersonalActionExecutionMode.BlockedMissingCapability, contract.executionMode)
        assertTrue(contract.ownerAuthorized)
        assertTrue(AndroidCapability.Accessibility in contract.missingCapabilities)
    }

    @Test
    fun postingPausesBeforeFinalGesture() {
        val contract = PersonalActionPlanner().buildContract(
            request = "post this to Facebook",
            targetAppLabel = "Facebook",
            grants = grants,
        )
        assertEquals(PersonalActionExecutionMode.ExecuteWithPausePoint, contract.executionMode)
        assertTrue(contract.pauseReason.contains("send/post/publish"))
    }
}
