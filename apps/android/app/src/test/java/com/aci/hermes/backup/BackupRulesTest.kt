package com.aci.hermes.backup

import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Manifest-assertion test for the cloud-backup / device-transfer
 * exclusion rules.
 *
 * The Android orchestrator persists two user-generated stores:
 *
 *   * `app_files/datastore/hermes_settings.preferences_pb` — Jetpack
 *     DataStore preferences.
 *   * `files/hermes_tasks.json` — JSON list of [com.aci.hermes.data.model.HermesTask]s.
 *
 * Both **must** be excluded from `<cloud-backup>` AND `<device-transfer>`
 * (Android 12+) and from `<full-backup-content>` (pre-12 path), or
 * user-typed task descriptions will silently leave the device on a
 * Google Drive backup or Android device-to-device transfer.
 *
 * If you add a third user-data sink to the app, extend the
 * `expectedExclusions` set below and update the XML in step.
 */
class BackupRulesTest {

    private val expectedExclusions = setOf(
        "datastore/hermes_settings.preferences_pb",
        "hermes_tasks.json",
    )

    @Test
    fun `backup_rules excludes every user-data sink from full-backup`() {
        val xml = readXml("src/main/res/xml/backup_rules.xml")
        for (path in expectedExclusions) {
            assertTrue(
                "backup_rules.xml must exclude '$path' from full-backup-content",
                xml.contains("path=\"$path\""),
            )
        }
        // The full-backup-content element is required at API ≤ 30.
        assertTrue(
            "backup_rules.xml must wrap exclusions in <full-backup-content>",
            xml.contains("<full-backup-content>") && xml.contains("</full-backup-content>"),
        )
    }

    @Test
    fun `data_extraction_rules excludes every user-data sink from cloud-backup`() {
        val xml = readXml("src/main/res/xml/data_extraction_rules.xml")
        val cloud = sliceBetween(xml, "<cloud-backup>", "</cloud-backup>")
            ?: fail("data_extraction_rules.xml missing <cloud-backup> block")
                .let { return }
        for (path in expectedExclusions) {
            assertTrue(
                "<cloud-backup> must exclude '$path'",
                cloud.contains("path=\"$path\""),
            )
        }
    }

    @Test
    fun `data_extraction_rules excludes every user-data sink from device-transfer`() {
        val xml = readXml("src/main/res/xml/data_extraction_rules.xml")
        val transfer = sliceBetween(xml, "<device-transfer>", "</device-transfer>")
            ?: fail("data_extraction_rules.xml missing <device-transfer> block")
                .let { return }
        for (path in expectedExclusions) {
            assertTrue(
                "<device-transfer> must exclude '$path'",
                transfer.contains("path=\"$path\""),
            )
        }
    }

    @Test
    fun `backup rules do not mention the removed encrypted shared prefs file`() {
        val full = readXml("src/main/res/xml/backup_rules.xml")
        val xtract = readXml("src/main/res/xml/data_extraction_rules.xml")
        // The legacy `hermes_secure_prefs.xml` SharedPreferences store
        // was removed when the chat / gateway architecture was retired
        // (see SettingsRepository.kt docs). Stale references would
        // confuse readers and silently fail to protect the actual data.
        assertTrue(
            "backup_rules.xml must not reference the removed hermes_secure_prefs.xml",
            !full.contains("hermes_secure_prefs"),
        )
        assertTrue(
            "data_extraction_rules.xml must not reference the removed hermes_secure_prefs.xml",
            !xtract.contains("hermes_secure_prefs"),
        )
    }

    @Test
    fun `manifest wires both rule files`() {
        val manifest = readXml("src/main/AndroidManifest.xml")
        assertTrue(
            "Manifest must wire android:fullBackupContent=@xml/backup_rules",
            manifest.contains("@xml/backup_rules"),
        )
        assertTrue(
            "Manifest must wire android:dataExtractionRules=@xml/data_extraction_rules",
            manifest.contains("@xml/data_extraction_rules"),
        )
    }

    private fun readXml(relativePath: String): String {
        // `./gradlew testDebugUnitTest` runs with the module dir (`apps/android/app/`)
        // as the working directory, so a direct relative read works.
        val direct = File(relativePath)
        if (direct.isFile) return direct.readText()
        // Defensive fallback: walk up from `user.dir` to find a parent
        // that contains the module.
        val startCwd: String = System.getProperty("user.dir") ?: "."
        var here: File? = File(startCwd)
        while (here != null) {
            val candidate = File(here, "apps/android/app/$relativePath")
            if (candidate.isFile) return candidate.readText()
            val fallback = File(here, relativePath)
            if (fallback.isFile) return fallback.readText()
            here = here.parentFile
        }
        fail("Could not locate $relativePath relative to cwd $startCwd")
        return "" // unreachable
    }

    private fun sliceBetween(xml: String, open: String, close: String): String? {
        val start = xml.indexOf(open)
        if (start < 0) return null
        val end = xml.indexOf(close, start + open.length)
        if (end < 0) return null
        return xml.substring(start + open.length, end)
    }
}
