package com.aci.hermes.data.automation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AutomationIntentParserTest {

    @Test
    fun `open app strips chrome words`() {
        val intent = AutomationIntentParser.parse("open the Facebook app please")
        assertEquals(AutomationIntent.OpenApp("facebook"), intent)
    }

    @Test
    fun `look at fb is an open intent`() {
        val intent = AutomationIntentParser.parse("look at fb")
        assertEquals(AutomationIntent.OpenApp("fb"), intent)
    }

    @Test
    fun `next screen turns the page left`() {
        assertEquals(
            AutomationIntent.TurnPage(PageDirection.LEFT),
            AutomationIntentParser.parse("next screen"),
        )
    }

    @Test
    fun `swipe right turns the page right`() {
        assertEquals(
            AutomationIntent.TurnPage(PageDirection.RIGHT),
            AutomationIntentParser.parse("swipe right"),
        )
    }

    @Test
    fun `scroll down is parsed`() {
        assertEquals(
            AutomationIntent.Scroll(ScrollDirection.DOWN),
            AutomationIntentParser.parse("scroll down"),
        )
    }

    @Test
    fun `go home maps to a global navigate`() {
        assertEquals(
            AutomationIntent.Navigate(GlobalAction.HOME),
            AutomationIntentParser.parse("go home"),
        )
    }

    @Test
    fun `press the blue button is a push target`() {
        val intent = AutomationIntentParser.parse("press the blue button")
        assertTrue(intent is AutomationIntent.PushTarget)
        assertEquals("blue button", (intent as AutomationIntent.PushTarget).query)
    }

    @Test
    fun `non-command utterance returns null`() {
        assertNull(AutomationIntentParser.parse("what's the weather like tomorrow"))
        assertNull(AutomationIntentParser.parse(""))
    }
}
