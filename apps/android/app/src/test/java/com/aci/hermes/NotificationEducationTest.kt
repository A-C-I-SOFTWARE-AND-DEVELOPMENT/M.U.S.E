package com.aci.hermes

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Notification permission UX guardrails.
 *
 *   - Notifications are NEVER prompted automatically; the request only
 *     fires when the user taps the home banner Enable button or the
 *     settings row. This test asserts that MainActivity does not call
 *     `requestPermission.launch(...)` from onCreate.
 *   - The notification-education banner has a string explaining why
 *     notifications are useful before any system prompt.
 */
class NotificationEducationTest {

    private val mainActivitySource: String = run {
        val candidates = listOf(
            File("src/main/java/com/aci/hermes/MainActivity.kt"),
            File("app/src/main/java/com/aci/hermes/MainActivity.kt"),
            File("apps/android/app/src/main/java/com/aci/hermes/MainActivity.kt"),
        )
        candidates.firstOrNull { it.exists() }?.readText()
            ?: error("could not locate MainActivity.kt from ${File(".").absolutePath}")
    }

    private val stringsXml: String = run {
        val candidates = listOf(
            File("src/main/res/values/strings.xml"),
            File("app/src/main/res/values/strings.xml"),
            File("apps/android/app/src/main/res/values/strings.xml"),
        )
        candidates.firstOrNull { it.exists() }?.readText()
            ?: error("could not locate strings.xml from ${File(".").absolutePath}")
    }

    @Test
    fun on_create_does_not_call_request_permission_launch() {
        val onCreateIdx = mainActivitySource.indexOf("override fun onCreate")
        assertTrue("onCreate not found", onCreateIdx > 0)
        val endIdx = mainActivitySource.indexOf("private fun", startIndex = onCreateIdx)
            .let { if (it == -1) mainActivitySource.length else it }
        val onCreateBody = mainActivitySource.substring(onCreateIdx, endIdx)
        assertFalse(
            "onCreate should not call requestNotificationPermission.launch — " +
                "permission must be user-initiated.\n$onCreateBody",
            onCreateBody.contains("requestNotificationPermission.launch"),
        )
    }

    @Test
    fun notification_request_is_isolated_in_helper_function() {
        // The helper is allowed to call launch; this confirms the
        // entry-point split is intentional.
        assertTrue(
            "expected requestNotificationPermissionIfNeeded helper",
            mainActivitySource.contains("requestNotificationPermissionIfNeeded"),
        )
    }

    @Test
    fun education_banner_string_is_present() {
        assertTrue(
            "home_notification_banner string missing",
            stringsXml.contains("home_notification_banner"),
        )
        assertTrue(
            "voice permission education string missing",
            stringsXml.contains("voice_permission_education"),
        )
    }

    @Test
    fun notification_education_toggle_string_is_present() {
        assertTrue(
            "notification education settings string missing",
            stringsXml.contains("settings_notifications_education_label"),
        )
    }

    @Test
    fun jarvis_prime_naming_used_in_strings() {
        val occurrences = "Jarvis Prime".toRegex().findAll(stringsXml).count()
        assertTrue("Jarvis Prime branding missing", occurrences >= 5)
    }

    @Test
    fun app_label_is_jarvis_prime() {
        val match = Regex("<string name=\"app_name\">([^<]+)</string>").find(stringsXml)
        assertNotNull(match)
        assertEquals("Jarvis Prime", match!!.groupValues[1])
    }
}
