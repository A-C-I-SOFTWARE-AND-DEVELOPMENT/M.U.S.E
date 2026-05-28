package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.avatar.AvatarRenderKind
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceCapabilityTest {

    private fun profile(
        ram: Int = 6000,
        api: Int = 33,
        lowRam: Boolean = false,
        reducedMotion: Boolean = false,
    ) = DeviceCapability.Profile(ram, api, lowRam, reducedMotion)

    @Test
    fun `capable device keeps the 3D body`() {
        assertEquals(AvatarKind.Character3D, DeviceCapability.effectiveKind(AvatarKind.Character3D, profile()))
    }

    @Test
    fun `low-ram device falls back from 3D to rive`() {
        assertEquals(
            AvatarKind.Rive,
            DeviceCapability.effectiveKind(AvatarKind.Character3D, profile(ram = 2000)),
        )
        assertEquals(
            AvatarKind.Rive,
            DeviceCapability.effectiveKind(AvatarKind.Character3D, profile(lowRam = true)),
        )
    }

    @Test
    fun `reduced motion collapses everything to the orb`() {
        assertEquals(
            AvatarKind.Orb,
            DeviceCapability.effectiveKind(AvatarKind.Character3D, profile(reducedMotion = true)),
        )
        assertEquals(
            AvatarKind.Orb,
            DeviceCapability.effectiveKind(AvatarKind.Rive, profile(reducedMotion = true)),
        )
    }

    @Test
    fun `non-3d kinds pass through untouched`() {
        assertEquals(AvatarKind.Rive, DeviceCapability.effectiveKind(AvatarKind.Rive, profile()))
        assertEquals(
            AvatarKind.AnimatedPixel,
            DeviceCapability.effectiveKind(AvatarKind.AnimatedPixel, profile(ram = 1500)),
        )
    }

    @Test
    fun `supports3D respects ram and api floors`() {
        assertTrue(DeviceCapability.supports3D(profile()))
        assertFalse(DeviceCapability.supports3D(profile(api = 21)))
        assertFalse(DeviceCapability.supports3D(profile(ram = 1000)))
    }

    @Test
    fun `render kind maps to the live kind`() {
        assertEquals(AvatarKind.Rive, DeviceCapability.kindFor(AvatarRenderKind.RIVE))
        assertEquals(AvatarKind.Character3D, DeviceCapability.kindFor(AvatarRenderKind.CHARACTER_3D))
        assertEquals(AvatarKind.AnimatedPixel, DeviceCapability.kindFor(AvatarRenderKind.ANIMATED_PIXEL))
        assertEquals(AvatarKind.Pixel, DeviceCapability.kindFor(AvatarRenderKind.STILL))
    }
}
