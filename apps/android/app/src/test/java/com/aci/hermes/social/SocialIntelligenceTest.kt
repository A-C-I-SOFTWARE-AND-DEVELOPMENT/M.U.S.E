package com.aci.hermes.social

import com.aci.hermes.conversation.ConversationTurn
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SocialIntelligenceTest {

    @Test fun compose_with_no_history_reports_only_topic_count() {
        val s = SocialIntelligence.compose(knownTopics = 0, pinnedTopics = 0, ownerTurns = 0, lastIntent = null)
        assertTrue(s.contains("knows 0 topic(s)"))
        assertFalse(s.contains("pinned"))
        assertFalse(s.contains("turn"))
    }

    @Test fun pinned_appears_only_when_positive() {
        val noPin = SocialIntelligence.compose(2, 0, 1, ConversationTurn.Intent.SMALL_TALK)
        assertFalse(noPin.contains("pinned"))
        val withPin = SocialIntelligence.compose(2, 1, 1, ConversationTurn.Intent.SMALL_TALK)
        assertTrue(withPin.contains("1 pinned"))
    }

    @Test fun emergency_intent_surfaces_explicitly() {
        val s = SocialIntelligence.compose(0, 0, 1, ConversationTurn.Intent.EMERGENCY_STOP)
        assertTrue(s.contains("emergency stop"))
    }

    @Test fun status_intent_surfaces_explicitly() {
        val s = SocialIntelligence.compose(0, 0, 1, ConversationTurn.Intent.STATUS_QUERY)
        assertTrue(s.contains("runtime status"))
    }
}
