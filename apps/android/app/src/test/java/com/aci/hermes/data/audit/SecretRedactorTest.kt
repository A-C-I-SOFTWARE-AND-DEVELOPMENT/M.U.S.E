package com.aci.hermes.data.audit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SecretRedactorTest {

    @Test
    fun `redacts assignment to API key`() {
        val input = "Loaded OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123"
        val out = SecretRedactor.redact(input)
        assertFalse("must not contain raw secret value", out.contains("sk-proj-abcdefghijklmnopqrstuvwxyz0123"))
        assertTrue("must mark the redacted spot", out.contains(SecretRedactor.REDACTION_MARKER))
    }

    @Test
    fun `redacts password and token style assignments`() {
        val input = """
            password: "hunter2-very-secret"
            token=abcdef1234567890abcdef1234567890
            access_key='AKIAIOSFODNN7EXAMPLE'
        """.trimIndent()
        val out = SecretRedactor.redact(input)
        assertFalse(out.contains("hunter2-very-secret"))
        assertFalse(out.contains("abcdef1234567890abcdef1234567890"))
        assertFalse(out.contains("AKIAIOSFODNN7EXAMPLE"))
    }

    @Test
    fun `redacts authorization header`() {
        val input = "Authorization: Bearer abcdefghij1234567890ZXCVBN"
        val out = SecretRedactor.redact(input)
        assertFalse(out.contains("abcdefghij1234567890ZXCVBN"))
        assertTrue(out.startsWith("Authorization:"))
    }

    @Test
    fun `redacts standalone provider tokens`() {
        val cases = listOf(
            "sk-proj-thisIsAFakeOpenAIKeyValue12345678",
            "ghp_abc123def456ghi789jkl012mno345pqr678",
            "AKIAABCDEFGHIJKLMNOP",
            "AIzaSyA1234567890abcdefghijklmnopqrstuvwx",
        )
        cases.forEach { tok ->
            val out = SecretRedactor.redact("token was $tok in the log")
            assertFalse("must redact $tok", out.contains(tok))
            assertTrue(out.contains(SecretRedactor.REDACTION_MARKER))
        }
    }

    @Test
    fun `redacts JWT tokens`() {
        val jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturepartishere1234"
        val out = SecretRedactor.redact("Set-Cookie: session=$jwt; Path=/")
        assertFalse(out.contains(jwt))
    }

    @Test
    fun `redacts PEM private key blocks`() {
        val pem = """
            -----BEGIN RSA PRIVATE KEY-----
            MIIEpAIBAAKCAQEAxxx
            -----END RSA PRIVATE KEY-----
        """.trimIndent()
        val out = SecretRedactor.redact("Found key:\n$pem")
        assertFalse(out.contains("MIIEpAIBAAKCAQEAxxx"))
        assertEquals("Found key:\n${SecretRedactor.REDACTION_MARKER}", out)
    }

    @Test
    fun `leaves harmless content untouched`() {
        val input = "Refactor: rename Banner.tsx and add tests"
        assertEquals(input, SecretRedactor.redact(input))
        assertFalse(SecretRedactor.containsSecret(input))
    }

    @Test
    fun `containsSecret flags only secret-bearing input`() {
        assertTrue(SecretRedactor.containsSecret("DATABASE_PASSWORD=supersecret123"))
        assertFalse(SecretRedactor.containsSecret("No credentials in this string"))
    }

    @Test
    fun `redact handles null and blank`() {
        assertEquals("", SecretRedactor.redact(null))
        assertEquals("", SecretRedactor.redact(""))
    }
}
