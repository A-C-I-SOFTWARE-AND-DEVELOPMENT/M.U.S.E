package com.aci.hermes.data.automation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AppTargetResolverTest {

    private val apps = listOf(
        AppTargetResolver.InstalledApp("com.facebook.katana", "Facebook"),
        AppTargetResolver.InstalledApp("com.instagram.android", "Instagram"),
        AppTargetResolver.InstalledApp("com.google.android.youtube", "YouTube"),
        AppTargetResolver.InstalledApp("com.android.settings", "Settings"),
    )
    private val resolver = AppTargetResolver(apps)

    @Test
    fun `exact label resolves`() {
        assertEquals("com.facebook.katana", resolver.resolve("Facebook")?.packageName)
    }

    @Test
    fun `nickname fb resolves to facebook via alias`() {
        assertEquals("com.facebook.katana", resolver.resolve("fb")?.packageName)
    }

    @Test
    fun `insta and ig both resolve to instagram`() {
        assertEquals("com.instagram.android", resolver.resolve("insta")?.packageName)
        assertEquals("com.instagram.android", resolver.resolve("ig")?.packageName)
    }

    @Test
    fun `package-id token match works when label differs`() {
        // "youtube" is a token of the package id and the label.
        assertEquals("com.google.android.youtube", resolver.resolve("youtube")?.packageName)
    }

    @Test
    fun `unknown app returns null`() {
        assertNull(resolver.resolve("spotify"))
        assertNull(resolver.resolve(""))
    }

    @Test
    fun `icon bounds are carried through when present`() {
        val withIcon = AppTargetResolver(
            listOf(
                AppTargetResolver.InstalledApp(
                    "com.facebook.katana",
                    "Facebook",
                    iconBounds = ScreenRect(10f, 20f, 110f, 120f),
                ),
            ),
        )
        assertEquals(ScreenRect(10f, 20f, 110f, 120f), withIcon.resolve("facebook")?.bounds)
    }
}
