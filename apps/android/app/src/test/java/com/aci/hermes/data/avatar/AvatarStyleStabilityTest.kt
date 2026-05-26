package com.aci.hermes.data.avatar

import org.junit.Assert.assertEquals
import org.junit.Test

class AvatarStyleStabilityTest {

    @Test
    fun avatarStyleNamesPinned() {
        assertEquals(
            listOf("NONE", "NAVY_GOLD", "CYAN_GLOW", "MONOCHROME_TERMINAL"),
            AvatarStyle.entries.map { it.name },
        )
    }

    @Test
    fun jarvisBuiltinNamesPinned() {
        assertEquals(
            listOf("GUARDIAN_SHIELD", "FAST_WORKER_BOLT", "KNOWLEDGE_MEMORY", "COMMAND_AUTO"),
            JarvisBuiltin.entries.map { it.name },
        )
    }

    @Test
    fun pixelSizeValuesPinned() {
        assertEquals(listOf(16, 32, 48), PixelSize.entries.map { it.px })
    }

    @Test
    fun avatarSourceNamesPinned() {
        assertEquals(listOf("BUILTIN", "GENERATED"), AvatarSource.entries.map { it.name })
    }
}
