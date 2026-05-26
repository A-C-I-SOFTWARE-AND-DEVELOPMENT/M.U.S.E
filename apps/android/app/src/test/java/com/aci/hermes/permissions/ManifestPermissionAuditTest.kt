package com.aci.hermes.permissions

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import java.io.File

/**
 * Pure-JVM permission-audit guard. The Jarvis Live command screen
 * must not add any of the permissions listed in [FORBIDDEN]. This
 * test parses AndroidManifest.xml from disk and snapshots the
 * approved permission list — any drift fails CI.
 */
class ManifestPermissionAuditTest {

    private val approved = setOf(
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    )

    private val forbidden = setOf(
        "android.permission.RECORD_AUDIO",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.CAMERA",
        "android.permission.SYSTEM_ALERT_WINDOW",
    )

    @Test
    fun `manifest contains exactly the approved permission set`() {
        val declared = readDeclaredPermissions()
        assertEquals(
            "Permission audit drift. Approved: $approved. Declared: $declared.",
            approved,
            declared,
        )
    }

    @Test
    fun `manifest declares none of the forbidden permissions`() {
        val declared = readDeclaredPermissions()
        for (perm in forbidden) {
            assertFalse(
                "Forbidden permission $perm appeared in manifest.",
                declared.contains(perm),
            )
        }
    }

    private fun readDeclaredPermissions(): Set<String> {
        val manifest = locateManifest()
        val regex = Regex("""uses-permission\s+android:name="([^"]+)"""")
        return regex.findAll(manifest.readText())
            .map { it.groupValues[1] }
            .toSet()
    }

    private fun locateManifest(): File {
        val candidates = listOf(
            File("src/main/AndroidManifest.xml"),
            File("app/src/main/AndroidManifest.xml"),
            File("apps/android/app/src/main/AndroidManifest.xml"),
        )
        return candidates.firstOrNull { it.exists() }
            ?: error("AndroidManifest.xml not found from cwd=${File(".").absolutePath}")
    }
}
