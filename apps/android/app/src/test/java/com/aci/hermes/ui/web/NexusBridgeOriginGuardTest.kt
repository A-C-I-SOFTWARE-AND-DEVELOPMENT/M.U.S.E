package com.aci.hermes.ui.web

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The bridge is the one path from web content to native authority, so its
 * trust decision is security-critical. These cases pin the allow-list: the
 * hosted PWA over HTTPS and loopback over HTTP — nothing else.
 */
class NexusBridgeOriginGuardTest {

    @Test
    fun `hosted PWA over https is trusted`() {
        assertTrue(
            NexusBridgeOriginGuard.isTrusted(
                "https://a-c-i-software-and-development.github.io/M.U.S.E/",
            ),
        )
        // Sub-paths / hash routes on the same host stay trusted.
        assertTrue(
            NexusBridgeOriginGuard.isTrusted(
                "https://a-c-i-software-and-development.github.io/M.U.S.E/#/approvals",
            ),
        )
    }

    @Test
    fun `loopback gateway over http is trusted`() {
        assertTrue(NexusBridgeOriginGuard.isTrusted("http://127.0.0.1:8765/nexus/"))
        assertTrue(NexusBridgeOriginGuard.isTrusted("http://localhost:8765/nexus/"))
    }

    @Test
    fun `hosted host over plain http is not trusted`() {
        // Downgrade attack: our host must be HTTPS.
        assertFalse(
            NexusBridgeOriginGuard.isTrusted(
                "http://a-c-i-software-and-development.github.io/M.U.S.E/",
            ),
        )
    }

    @Test
    fun `non-loopback http is not trusted`() {
        assertFalse(NexusBridgeOriginGuard.isTrusted("http://192.168.1.50:8765/nexus/"))
        assertFalse(NexusBridgeOriginGuard.isTrusted("http://example.com/"))
    }

    @Test
    fun `look-alike and sub-domain hosts are not trusted`() {
        assertFalse(
            NexusBridgeOriginGuard.isTrusted(
                "https://a-c-i-software-and-development.github.io.evil.com/M.U.S.E/",
            ),
        )
        assertFalse(
            NexusBridgeOriginGuard.isTrusted(
                "https://evil.a-c-i-software-and-development.github.io/",
            ),
        )
    }

    @Test
    fun `null blank and malformed urls are not trusted`() {
        assertFalse(NexusBridgeOriginGuard.isTrusted(null))
        assertFalse(NexusBridgeOriginGuard.isTrusted(""))
        assertFalse(NexusBridgeOriginGuard.isTrusted("not a url"))
        assertFalse(NexusBridgeOriginGuard.isTrusted("javascript:alert(1)"))
        assertFalse(NexusBridgeOriginGuard.isTrusted("file:///data/local/tmp/x.html"))
    }
}
