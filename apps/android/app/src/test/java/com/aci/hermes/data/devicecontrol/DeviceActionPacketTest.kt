package com.aci.hermes.data.devicecontrol

import com.aci.hermes.data.automation.AutomationIntent
import com.aci.hermes.data.automation.GlobalAction
import com.aci.hermes.data.automation.PageDirection
import com.aci.hermes.data.automation.ScrollDirection
import org.junit.Assert.assertEquals
import org.junit.Test

/** Intent → sensitivity + required-capability + preview classification. */
class DeviceActionPacketTest {

    @Test
    fun `launching an app is sensitive and needs package visibility`() {
        val packet = DeviceActionPacket.from(AutomationIntent.OpenApp("facebook"), resolvedLabel = "Facebook")
        assertEquals(DeviceActionSensitivity.SENSITIVE, packet.sensitivity)
        assertEquals(
            setOf(DeviceControlCapability.ACCESSIBILITY, DeviceControlCapability.PACKAGE_VISIBILITY),
            packet.requiredCapabilities,
        )
        assertEquals("Open Facebook", packet.previewLabel)
    }

    @Test
    fun `tapping a target is sensitive`() {
        val packet = DeviceActionPacket.from(AutomationIntent.PushTarget("send"))
        assertEquals(DeviceActionSensitivity.SENSITIVE, packet.sensitivity)
        assertEquals(setOf(DeviceControlCapability.ACCESSIBILITY), packet.requiredCapabilities)
        assertEquals("Tap \"send\"", packet.previewLabel)
    }

    @Test
    fun `navigation actions are standard`() {
        val scroll = DeviceActionPacket.from(AutomationIntent.Scroll(ScrollDirection.DOWN))
        val page = DeviceActionPacket.from(AutomationIntent.TurnPage(PageDirection.LEFT))
        val nav = DeviceActionPacket.from(AutomationIntent.Navigate(GlobalAction.HOME))

        assertEquals(DeviceActionSensitivity.STANDARD, scroll.sensitivity)
        assertEquals(DeviceActionSensitivity.STANDARD, page.sensitivity)
        assertEquals(DeviceActionSensitivity.STANDARD, nav.sensitivity)

        assertEquals(setOf(DeviceControlCapability.ACCESSIBILITY), scroll.requiredCapabilities)
        assertEquals("Scroll down", scroll.previewLabel)
        assertEquals("Turn page left", page.previewLabel)
        assertEquals("Go home", nav.previewLabel)
    }

    @Test
    fun `required capability mapping matches the catalog helper`() {
        val intent = AutomationIntent.OpenApp("x")
        assertEquals(
            DeviceControlCapability.requiredFor(intent),
            DeviceActionPacket.from(intent).requiredCapabilities,
        )
    }
}
