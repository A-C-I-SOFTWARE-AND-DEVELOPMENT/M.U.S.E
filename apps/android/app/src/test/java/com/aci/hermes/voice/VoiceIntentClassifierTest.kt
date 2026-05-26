package com.aci.hermes.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceIntentClassifierTest {

    private val classifier = VoiceIntentClassifier()

    @Test fun `empty transcript is safe text`() {
        val result = classifier.classify("")
        assertEquals(VoiceCommandCategory.SAFE_TEXT, result.category)
    }

    @Test fun `simple note is safe text`() {
        val result = classifier.classify("remind me to call Jamie about the spec review tomorrow")
        assertEquals(VoiceCommandCategory.SAFE_TEXT, result.category)
    }

    @Test fun `delete verb requires approval`() {
        val result = classifier.classify("delete the staging database now")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertEquals("delete", result.matchedTrigger)
    }

    @Test fun `deploy verb requires approval`() {
        val result = classifier.classify("deploy the new release to production")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertEquals("deploy", result.matchedTrigger)
    }

    @Test fun `publish verb requires approval`() {
        val result = classifier.classify("publish the blog post about voice capture")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertEquals("publish", result.matchedTrigger)
    }

    @Test fun `vague scope requires approval`() {
        val result = classifier.classify("fix everything you can find in the repo")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertNotNull(result.matchedTrigger)
    }

    @Test fun `cancel phrase routes to cancel`() {
        val result = classifier.classify("never mind, forget it")
        assertEquals(VoiceCommandCategory.CANCEL, result.category)
    }

    @Test fun `cancel beats subsequent serious verb`() {
        val result = classifier.classify("cancel, do not delete anything")
        assertEquals(VoiceCommandCategory.CANCEL, result.category)
    }

    @Test fun `serious verb buried mid sentence still escalates`() {
        val result = classifier.classify("please go ahead and ship it to the customers")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertTrue(setOf("ship").contains(result.matchedTrigger))
    }

    @Test fun `serious verb with question mark still escalates`() {
        val result = classifier.classify("Spend $500 on Datadog upgrade?")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, result.category)
        assertEquals("spend", result.matchedTrigger)
    }
}
