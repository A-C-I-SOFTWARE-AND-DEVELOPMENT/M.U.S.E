package com.aci.hermes.termux

import com.aci.hermes.data.termux.TermuxBridgeAction
import com.aci.hermes.data.termux.TermuxIntentBridge
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pinned-constants test for the Termux RUN_COMMAND wire contract.
 *
 * Every constant here matches Termux's published RUN_COMMAND envelope.
 * If a future refactor renames any of these, this test fires before
 * shipping a build that would silently fail to invoke Termux.
 *
 * The test deliberately does NOT exercise `buildHermesIntent` or
 * `buildOpenJobFolderIntent` — those construct real `android.content.Intent`
 * and `android.net.Uri` instances, which require Robolectric or an
 * instrumented run. The contract surface those builders depend on is
 * pinned here instead.
 */
class TermuxIntentBridgeConstantsTest {

    @Test
    fun `package names match Termux's published values`() {
        assertEquals("com.termux", TermuxIntentBridge.TERMUX_PACKAGE)
        assertEquals("com.termux.files", TermuxIntentBridge.TERMUX_FILES_PACKAGE)
    }

    @Test
    fun `RUN_COMMAND service and action match Termux's published values`() {
        assertEquals(
            "com.termux.app.RunCommandService",
            TermuxIntentBridge.RUN_COMMAND_SERVICE,
        )
        assertEquals("com.termux.RUN_COMMAND", TermuxIntentBridge.ACTION_RUN_COMMAND)
    }

    @Test
    fun `RUN_COMMAND extras match Termux's published values`() {
        assertEquals("com.termux.RUN_COMMAND_PATH", TermuxIntentBridge.EXTRA_PATH)
        assertEquals("com.termux.RUN_COMMAND_ARGUMENTS", TermuxIntentBridge.EXTRA_ARGUMENTS)
        assertEquals("com.termux.RUN_COMMAND_WORKDIR", TermuxIntentBridge.EXTRA_WORKDIR)
        assertEquals("com.termux.RUN_COMMAND_BACKGROUND", TermuxIntentBridge.EXTRA_BACKGROUND)
        assertEquals(
            "com.termux.RUN_COMMAND_SESSION_ACTION",
            TermuxIntentBridge.EXTRA_SESSION_ACTION,
        )
    }

    @Test
    fun `session-action values match Termux's published values`() {
        assertEquals("0", TermuxIntentBridge.SESSION_BACKGROUND)
        assertEquals("1", TermuxIntentBridge.SESSION_OPEN)
    }

    @Test
    fun `termux on-device paths match what pkg install hermes produces`() {
        assertEquals(
            "/data/data/com.termux/files/usr",
            TermuxIntentBridge.TERMUX_PREFIX,
        )
        assertEquals(
            "/data/data/com.termux/files/home",
            TermuxIntentBridge.TERMUX_HOME,
        )
        assertEquals(
            "/data/data/com.termux/files/usr/bin/hermes",
            TermuxIntentBridge.HERMES_BIN,
        )
    }

    @Test
    fun `local gateway sentinel binds to loopback only`() {
        // The cockpit's Settings screen may override this, but the
        // baked-in default is loopback-only. A 0.0.0.0 default here
        // would silently expose the on-device gateway to the LAN.
        assertEquals(
            "http://127.0.0.1:8080",
            TermuxIntentBridge.LOCAL_GATEWAY_URL,
        )
        assertTrue(
            "Local gateway sentinel must point at loopback",
            TermuxIntentBridge.LOCAL_GATEWAY_URL.contains("127.0.0.1"),
        )
    }

    @Test
    fun `bridge action enum lists every panel control without duplicates`() {
        val expected = setOf(
            TermuxBridgeAction.START_GATEWAY,
            TermuxBridgeAction.STOP_GATEWAY,
            TermuxBridgeAction.RESTART_GATEWAY,
            TermuxBridgeAction.OPEN_TERMUX,
            TermuxBridgeAction.OPEN_JOB_FOLDER,
            TermuxBridgeAction.TAIL_LOGS,
        )
        assertEquals(expected, TermuxBridgeAction.values().toSet())
        assertEquals(
            "TermuxBridgeAction had duplicate values",
            expected.size,
            TermuxBridgeAction.values().size,
        )
    }
}
