package com.jeremiahecherd.jarvisprime

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Static, source-level guards that catch the most common regression:
 * something inside MainActivity calling requestPermissions, launching
 * a permission contract, or referencing POST_NOTIFICATIONS /
 * RECORD_AUDIO during startup.
 *
 * The check is a textual scan because we want to fail fast on the JVM
 * without an Android instrumentation harness. The two permission
 * education screens still reference these constants — they're the only
 * place runtime prompts are allowed.
 */
class StartupPermissionPolicyTest {

    private fun readKotlin(relative: String): String {
        val file = File("src/main/kotlin/$relative")
        assertTrue("source not found: ${file.absolutePath}", file.exists())
        return stripComments(file.readText())
    }

    /**
     * Removes `//` line comments and `/* ... */` block comments so the
     * policy scan only inspects actual code. Without this, the docs
     * comment in MainActivity that *describes* the policy would trip
     * the scan that *enforces* it.
     */
    private fun stripComments(source: String): String {
        val withoutBlocks = Regex("/\\*[\\s\\S]*?\\*/").replace(source, "")
        return withoutBlocks.lineSequence()
            .map { line -> line.substringBefore("//") }
            .joinToString("\n")
    }

    @Test
    fun mainActivityNeverRequestsPermissionsAtStartup() {
        val source = readKotlin("com/jeremiahecherd/jarvisprime/MainActivity.kt")
        val banned = listOf(
            "requestPermissions(",
            "RequestPermission()",
            "RequestMultiplePermissions()",
            "POST_NOTIFICATIONS",
            "RECORD_AUDIO",
            "SYSTEM_ALERT_WINDOW",
        )
        for (token in banned) {
            assertFalse(
                "MainActivity must not reference \"$token\" — permission flow lives in onboarding",
                source.contains(token),
            )
        }
    }

    @Test
    fun jarvisPrimeAppNeverRequestsPermissions() {
        val source = readKotlin("com/jeremiahecherd/jarvisprime/JarvisPrimeApp.kt")
        assertFalse(source.contains("requestPermissions("))
        assertFalse(source.contains("POST_NOTIFICATIONS"))
        assertFalse(source.contains("RECORD_AUDIO"))
    }

    @Test
    fun notificationEducationScreenOwnsTheNotificationPrompt() {
        val source = readKotlin(
            "com/jeremiahecherd/jarvisprime/ui/onboarding/NotificationEducationScreen.kt",
        )
        assertTrue(
            "Notification education screen must launch POST_NOTIFICATIONS",
            source.contains("POST_NOTIFICATIONS"),
        )
        assertTrue(
            "Notification education screen must register an ActivityResult contract",
            source.contains("rememberLauncherForActivityResult"),
        )
    }

    @Test
    fun voiceEducationScreenOwnsTheMicrophonePrompt() {
        val source = readKotlin(
            "com/jeremiahecherd/jarvisprime/ui/onboarding/VoiceEducationScreen.kt",
        )
        assertTrue(source.contains("RECORD_AUDIO"))
        assertTrue(source.contains("rememberLauncherForActivityResult"))
    }
}
