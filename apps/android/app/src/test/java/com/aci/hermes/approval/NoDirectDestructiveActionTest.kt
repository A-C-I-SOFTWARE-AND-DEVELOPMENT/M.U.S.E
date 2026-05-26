package com.aci.hermes.approval

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The approval surface is structurally forbidden from performing destructive
 * actions itself — every decision exits through the [com.aci.hermes.approval.event.ApprovalEventSink].
 *
 * This test scans the approval source tree for symptoms of direct execution
 * and fails the build if any leak in. The rest of the cockpit (orchestrator,
 * settings, diagnostics) is intentionally NOT scanned — it has legitimate
 * reasons to talk to the network and filesystem (foreground service,
 * preference DataStore, etc).
 */
class NoDirectDestructiveActionTest {

    private val forbiddenPatterns = listOf(
        Regex("""Runtime\.getRuntime\(\)\.exec\b"""),
        Regex("""ProcessBuilder\b"""),
        Regex("""HttpURLConnection\b"""),
        Regex("""OkHttpClient\b"""),
        Regex("""\bRetrofit\b"""),
        Regex("""ContentResolver.*\.delete\("""),
        Regex("""SQLiteDatabase\b"""),
        Regex("""\.execSQL\("""),
        Regex("""\.deleteRecursively\("""),
        Regex("""Class\.forName\(.*\.getMethod\b""")
    )

    @Test
    fun approval_sources_only_emit_events_never_execute() {
        val approvalDir = File("src/main/java/com/aci/hermes/approval")
        assertTrue("approval source tree missing at ${approvalDir.absolutePath}", approvalDir.exists())

        val violations = mutableListOf<String>()
        approvalDir.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .forEach { file ->
                file.readLines().forEachIndexed { i, line ->
                    val stripped = line.substringBefore("//").trim()
                    if (stripped.isEmpty()) return@forEachIndexed
                    for (pattern in forbiddenPatterns) {
                        if (pattern.containsMatchIn(stripped)) {
                            violations += "${file.path}:${i + 1}  $stripped  matches $pattern"
                        }
                    }
                }
            }

        assertEquals(
            "Approval surface must never perform destructive actions directly; found:\n" +
                violations.joinToString("\n"),
            0,
            violations.size
        )
    }
}
