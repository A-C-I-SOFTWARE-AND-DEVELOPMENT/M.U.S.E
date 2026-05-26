package com.aci.hermes.ui.jarvis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins [JarvisAvatarProfile]'s shape. Two `Source` variants exist —
 * `BuiltIn` (drawable resource id, immutable) and `UserGenerated`
 * (app-private file path). The avatar layer is identity-agnostic at
 * the type level so the picker (added on a later branch) doesn't
 * leak storage details into the renderer.
 */
class JarvisAvatarProfileTest {

    @Test
    fun built_in_source_carries_drawable_res_id() {
        val src = JarvisAvatarProfile.Source.BuiltIn(drawableResId = 12345)
        assertEquals(12345, src.drawableResId)
    }

    @Test
    fun user_generated_source_carries_file_path_string() {
        val src = JarvisAvatarProfile.Source.UserGenerated(
            filePath = "/data/data/com.aci.hermes/files/avatars/user_avatar.png",
        )
        assertTrue(
            "user-generated source must point inside app-private storage",
            src.filePath.contains("/files/"),
        )
    }

    @Test
    fun profiles_with_different_sources_are_not_equal() {
        val a = JarvisAvatarProfile(
            name = "Jarvis",
            source = JarvisAvatarProfile.Source.BuiltIn(1),
            selectedAt = 100L,
        )
        val b = JarvisAvatarProfile(
            name = "Jarvis",
            source = JarvisAvatarProfile.Source.UserGenerated("/path"),
            selectedAt = 100L,
        )
        assertNotEquals(a, b)
    }

    @Test
    fun default_name_is_Jarvis() {
        assertEquals("Jarvis", JarvisAvatarProfile.DEFAULT_NAME)
    }

    @Test
    fun selected_at_preserves_wall_clock_value() {
        val now = 1_716_739_200_000L
        val profile = JarvisAvatarProfile(
            name = "Jarvis",
            source = JarvisAvatarProfile.Source.BuiltIn(0),
            selectedAt = now,
        )
        assertEquals(now, profile.selectedAt)
    }
}
