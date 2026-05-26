package com.aci.hermes.ui.components.icon

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Guard test: this lane must not add any Android permissions —
 * especially `SYSTEM_ALERT_WINDOW`, which the mission explicitly
 * forbids. The test reads `AndroidManifest.xml` from disk so a future
 * silent edit shows up as a failed assertion here without needing the
 * Android build tooling.
 */
class ManifestPermissionsUnchangedTest {

    private val expected = setOf(
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    )

    @Test
    fun `manifest declares exactly the expected permissions`() {
        val manifest = locateManifest()
        val text = manifest.readText()
        val declared = PERMISSION_REGEX.findAll(text)
            .map { it.groupValues[1] }
            .toSet()
        assertEquals(
            "permission set drifted — review against the icon lane scope",
            expected,
            declared,
        )
    }

    @Test
    fun `manifest does not declare SYSTEM_ALERT_WINDOW`() {
        val text = locateManifest().readText()
        assertFalse(
            "SYSTEM_ALERT_WINDOW is explicitly out of scope for this lane",
            text.contains("SYSTEM_ALERT_WINDOW"),
        )
    }

    @Test
    fun `manifest does not declare overlay-management intents`() {
        val text = locateManifest().readText()
        assertFalse(
            "ACTION_MANAGE_OVERLAY_PERMISSION is out of scope",
            text.contains("ACTION_MANAGE_OVERLAY_PERMISSION"),
        )
    }

    private fun locateManifest(): File {
        // testDebugUnitTest runs with cwd = apps/android/app, so the
        // first candidate is the common case. The fallbacks cover
        // invocations from other working directories (IDE, repo root).
        val candidates = listOf(
            File("src/main/AndroidManifest.xml"),
            File("app/src/main/AndroidManifest.xml"),
            File("apps/android/app/src/main/AndroidManifest.xml"),
        )
        val resolved = candidates.firstOrNull { it.exists() }
        assertNotNull(
            "AndroidManifest.xml not found — tried: ${candidates.joinToString { it.path }}",
            resolved,
        )
        val file = resolved!!
        assertTrue("manifest unreadable: ${file.absolutePath}", file.canRead())
        return file
    }

    companion object {
        private val PERMISSION_REGEX =
            Regex("""<uses-permission\s+android:name="([^"]+)"\s*/>""")
    }
}
