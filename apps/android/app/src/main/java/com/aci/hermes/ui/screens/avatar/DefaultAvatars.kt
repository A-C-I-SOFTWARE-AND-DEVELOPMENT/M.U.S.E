package com.aci.hermes.ui.screens.avatar

import androidx.annotation.DrawableRes
import com.aci.hermes.R
import com.aci.hermes.ui.jarvis.JarvisAvatarProfile

/**
 * Built-in avatar choices shipped with the app. The picker offers
 * these first so the user has something usable without going through
 * the photo picker / pixelator at all.
 *
 * Each entry resolves to a `JarvisAvatarProfile.Source.BuiltIn`
 * pointing at a vector drawable in `res/drawable/`. The picker view-
 * model rebuilds a `JarvisAvatarProfile` from the chosen entry at
 * selection time.
 */
object DefaultAvatars {

    data class Entry(
        val id: String,
        @DrawableRes val drawableResId: Int,
        val nameStringResId: Int,
    )

    val Cyan = Entry(
        id = "default_cyan",
        drawableResId = R.drawable.ic_jarvis_avatar_cyan,
        nameStringResId = R.string.avatar_default_cyan,
    )
    val Gold = Entry(
        id = "default_gold",
        drawableResId = R.drawable.ic_jarvis_avatar_gold,
        nameStringResId = R.string.avatar_default_gold,
    )
    val Slate = Entry(
        id = "default_slate",
        drawableResId = R.drawable.ic_jarvis_avatar_slate,
        nameStringResId = R.string.avatar_default_slate,
    )
    val Violet = Entry(
        id = "default_violet",
        drawableResId = R.drawable.ic_jarvis_avatar_violet,
        nameStringResId = R.string.avatar_default_violet,
    )

    /** Ordered list shown in the picker grid. Cyan first = launch default. */
    val ALL: List<Entry> = listOf(Cyan, Gold, Slate, Violet)

    /** The default profile for a fresh install. */
    fun defaultProfile(now: Long = System.currentTimeMillis()): JarvisAvatarProfile =
        JarvisAvatarProfile(
            name = JarvisAvatarProfile.DEFAULT_NAME,
            source = JarvisAvatarProfile.Source.BuiltIn(Cyan.drawableResId),
            selectedAt = now,
        )

    /** Convert an entry to a profile (with the wall-clock timestamp). */
    fun toProfile(entry: Entry, now: Long = System.currentTimeMillis()): JarvisAvatarProfile =
        JarvisAvatarProfile(
            name = JarvisAvatarProfile.DEFAULT_NAME,
            source = JarvisAvatarProfile.Source.BuiltIn(entry.drawableResId),
            selectedAt = now,
        )
}
