package com.aci.hermes.ui.screens.avatar

import com.aci.hermes.R
import com.aci.hermes.ui.jarvis.JarvisAvatarProfile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the bundled-avatar set. The picker ships these so a user can
 * pick something usable without ever opening the photo picker.
 */
class DefaultAvatarsTest {

    @Test
    fun all_default_entries_are_resolvable() {
        for (entry in DefaultAvatars.ALL) {
            assertTrue(
                "drawable id ${entry.drawableResId} must be > 0",
                entry.drawableResId > 0,
            )
            assertTrue(
                "name string id ${entry.nameStringResId} must be > 0",
                entry.nameStringResId > 0,
            )
        }
    }

    @Test
    fun all_default_ids_are_unique() {
        val ids = DefaultAvatars.ALL.map { it.id }
        assertEquals(
            "default entry ids must be unique",
            ids.size,
            ids.toSet().size,
        )
    }

    @Test
    fun all_default_drawable_resources_are_unique() {
        val drawables = DefaultAvatars.ALL.map { it.drawableResId }
        assertEquals(
            "default drawable resources must be unique",
            drawables.size,
            drawables.toSet().size,
        )
    }

    @Test
    fun cyan_is_the_launch_default() {
        assertEquals(R.drawable.ic_jarvis_avatar_cyan, DefaultAvatars.Cyan.drawableResId)
        val profile = DefaultAvatars.defaultProfile(now = 100L)
        val source = profile.source as JarvisAvatarProfile.Source.BuiltIn
        assertEquals(R.drawable.ic_jarvis_avatar_cyan, source.drawableResId)
        assertEquals(JarvisAvatarProfile.DEFAULT_NAME, profile.name)
    }

    @Test
    fun to_profile_preserves_selected_at_timestamp() {
        val now = 1_716_739_200_000L
        val profile = DefaultAvatars.toProfile(DefaultAvatars.Gold, now)
        assertEquals(now, profile.selectedAt)
    }

    @Test
    fun built_in_source_is_distinct_from_user_generated() {
        val builtIn = JarvisAvatarProfile.Source.BuiltIn(1)
        val userGen = JarvisAvatarProfile.Source.UserGenerated("/path")
        assertNotEquals(builtIn::class, userGen::class)
    }
}
