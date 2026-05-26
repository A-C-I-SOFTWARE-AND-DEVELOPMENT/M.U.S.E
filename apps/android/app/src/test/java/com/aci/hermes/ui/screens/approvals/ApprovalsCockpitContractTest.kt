package com.aci.hermes.ui.screens.approvals

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Cockpit-layer safety net for the approval surface.
 *
 * The existing [com.aci.hermes.approval.NoDirectDestructiveActionTest]
 * already scans every .kt file under `src/main/java/com/aci/hermes/approval/` for direct
 * destructive calls. This test adds a second, broader scan from the
 * cockpit's perspective so a refactor that moves approval code around
 * cannot accidentally drop the invariant. Both must hold:
 *
 *   1. The approval surface never opens a network socket directly.
 *   2. The approval surface never executes a subprocess.
 *   3. The approval surface never deletes / clears app data.
 *
 * Approvals always exit via [com.aci.hermes.approval.event.ApprovalEventSink].
 * The runtime decides what to do with the event — the Android client
 * only emits.
 */
class ApprovalsCockpitContractTest {

    private val forbiddenPatterns = listOf(
        // Process / subprocess execution
        Regex("""Runtime\.getRuntime\(\)\.exec\b"""),
        Regex("""ProcessBuilder\b"""),
        Regex("""Class\.forName\(.*\.getMethod\b"""),
        // Network IO
        Regex("""HttpURLConnection\b"""),
        Regex("""OkHttpClient\b"""),
        Regex("""\bRetrofit\b"""),
        Regex("""okhttp3\.Call\b"""),
        Regex("""\bjava\.net\.URL\(.*\)\.openConnection\b"""),
        // Storage / data deletion
        Regex("""ContentResolver.*\.delete\("""),
        Regex("""SQLiteDatabase\b"""),
        Regex("""\.execSQL\("""),
        Regex("""\.deleteRecursively\("""),
        Regex("""File\(.*\)\.delete\(\)"""),
    )

    @Test
    fun approval_surface_never_performs_destructive_actions_from_the_cockpit() {
        val approvalDir = File("src/main/java/com/aci/hermes/approval")
        // The production approval tree is required by the cockpit
        // contract — if someone deleted it we want a loud failure
        // (not a silent pass).
        assertTrue(
            "approval source tree missing at ${approvalDir.absolutePath}",
            approvalDir.exists(),
        )

        val violations = mutableListOf<String>()
        approvalDir.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .forEach { file ->
                file.readLines().forEachIndexed { index, line ->
                    val stripped = line.substringBefore("//").trim()
                    if (stripped.isEmpty()) return@forEachIndexed
                    for (pattern in forbiddenPatterns) {
                        if (pattern.containsMatchIn(stripped)) {
                            violations += "${file.path}:${index + 1}  $stripped  matches $pattern"
                        }
                    }
                }
            }

        assertEquals(
            "approval surface must never perform destructive work directly " +
                "from the cockpit; every decision must exit via ApprovalEventSink. " +
                "Found:\n" + violations.joinToString("\n"),
            0,
            violations.size,
        )
    }

    @Test
    fun approval_event_sink_is_the_only_outbound_path() {
        // Belt-and-braces: there must be at least one Kotlin file under
        // approval/ that mentions ApprovalEventSink. If it disappears,
        // approve/reject decisions have nowhere to go and the contract
        // is silently broken.
        val approvalDir = File("src/main/java/com/aci/hermes/approval")
        if (!approvalDir.exists()) return // covered by the test above

        val mentions = approvalDir.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .count { it.readText().contains("ApprovalEventSink") }

        assertTrue(
            "expected at least one approval source file to reference " +
                "ApprovalEventSink — without it the cockpit has no outbound path",
            mentions >= 1,
        )
    }
}
