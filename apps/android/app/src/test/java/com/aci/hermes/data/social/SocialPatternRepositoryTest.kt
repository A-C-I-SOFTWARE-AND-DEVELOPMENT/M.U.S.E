package com.aci.hermes.data.social

import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

class SocialPatternRepositoryTest {

    private lateinit var dir: File

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("jarvis-social-test").toFile()
    }

    @After
    fun tearDown() {
        dir.deleteRecursively()
    }

    @Test
    fun `upsert sanitizes identity before storage`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        val saved = repo.upsert(
            SocialPattern(
                title = "How @alice replies",
                kind = SocialPatternKind.MOBILE_REPLY,
                summary = "Talked to bob@example.com",
                safeUsage = "x",
                unsafeUsage = "y",
            ),
        )
        assertFalse(saved.title.contains("@alice"))
        assertFalse(saved.summary.contains("bob@example.com"))
        assertEquals(PrivacyRisk.HIGH, saved.privacyRisk)
        assertTrue(saved.identityFlags.contains("handle"))
        assertTrue(saved.identityFlags.contains("email"))
    }

    @Test
    fun `delete removes the pattern`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        val saved = repo.upsert(samplePattern())
        assertNotNull(repo.byId(saved.id))
        repo.delete(saved.id)
        assertNull(repo.byId(saved.id))
    }

    @Test
    fun `correct replaces fields and records correctedFrom`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        val saved = repo.upsert(samplePattern())
        val updated = repo.correct(
            id = saved.id,
            title = "Corrected title",
            summary = "Corrected summary",
            safeUsage = "Corrected safe",
            unsafeUsage = "Corrected unsafe",
        )
        assertNotNull(updated)
        assertEquals("Corrected title", updated!!.title)
        assertEquals("Corrected summary", updated.summary)
        assertEquals("Corrected safe", updated.safeUsage)
        assertEquals("Corrected unsafe", updated.unsafeUsage)
        assertEquals(saved.id, updated.correctedFrom)
    }

    @Test
    fun `correct re-runs sanitization`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        val saved = repo.upsert(samplePattern())
        val updated = repo.correct(
            id = saved.id,
            title = "How @alice replies",
            summary = "see bob@example.com",
            safeUsage = "x",
            unsafeUsage = "y",
        )
        assertNotNull(updated)
        assertFalse(updated!!.title.contains("@alice"))
        assertFalse(updated.summary.contains("bob@example.com"))
        assertEquals(PrivacyRisk.HIGH, updated.privacyRisk)
    }

    @Test
    fun `correct returns null when id missing`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        val result = repo.correct(
            id = "does-not-exist",
            title = "x",
            summary = "y",
            safeUsage = "z",
            unsafeUsage = "w",
        )
        assertNull(result)
    }

    @Test
    fun `deleteAll empties the store`() = runBlocking {
        val repo = SocialPatternRepository(dir)
        repo.upsert(samplePattern())
        repo.upsert(samplePattern())
        repo.deleteAll()
        assertEquals(0, repo.patterns.value.size)
    }

    private fun samplePattern() = SocialPattern(
        title = "Engineers reply short on mobile",
        kind = SocialPatternKind.MOBILE_REPLY,
        summary = "Phones invite brevity.",
        safeUsage = "Mirror brevity on mobile.",
        unsafeUsage = "Never impersonate any specific person.",
    )
}
