package com.aci.hermes.manifest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element
import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Launch gate: the runtime permission set is part of the privacy
 * contract. Adding any new `<uses-permission>` to the manifest must
 * be a deliberate decision reviewed under approvals, not an
 * incidental side-effect of pulling in a library.
 *
 * If you genuinely need a new permission, update [EXPECTED_PERMISSIONS]
 * here AND surface the change in the PR description so the user can
 * approve it.
 */
class AndroidManifestPermissionsTest {

    @Test
    fun manifest_uses_permission_set_matches_allowlist() {
        val manifest = File("src/main/AndroidManifest.xml")
        assertTrue(
            "AndroidManifest.xml missing at ${manifest.absolutePath}",
            manifest.exists(),
        )

        val doc = DocumentBuilderFactory.newInstance().apply {
            isNamespaceAware = true
        }.newDocumentBuilder().parse(manifest)

        val nodes = doc.getElementsByTagName("uses-permission")
        val actual = sortedSetOf<String>()
        for (i in 0 until nodes.length) {
            val el = nodes.item(i) as Element
            val name = el.getAttributeNS(ANDROID_NS, "name")
                .ifBlank { el.getAttribute("android:name") }
            actual.add(name)
        }

        assertEquals(
            "AndroidManifest.xml uses-permission set drifted — update " +
                "EXPECTED_PERMISSIONS and flag the change in the PR.",
            EXPECTED_PERMISSIONS.toSortedSet(),
            actual,
        )
    }

    companion object {
        private const val ANDROID_NS = "http://schemas.android.com/apk/res/android"

        // Exact set of <uses-permission> declarations we expect in the
        // manifest. Keep in sync with src/main/AndroidManifest.xml.
        val EXPECTED_PERMISSIONS: Set<String> = setOf(
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
        )
    }
}
