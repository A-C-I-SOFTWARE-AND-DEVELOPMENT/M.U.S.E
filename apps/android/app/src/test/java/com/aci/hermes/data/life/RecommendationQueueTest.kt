package com.aci.hermes.data.life

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RecommendationQueueTest {

    private fun rec(id: String, priority: Recommendation.Priority = Recommendation.Priority.NORMAL) =
        Recommendation(id = id, title = "t-$id", detail = "d-$id", priority = priority)

    @Test
    fun `offer then take preserves FIFO for same priority`() {
        val q = RecommendationQueue()
        q.offer(rec("a"))
        q.offer(rec("b"))
        assertEquals("a", q.take()?.id)
        assertEquals("b", q.take()?.id)
        assertNull(q.take())
    }

    @Test
    fun `high priority jumps the queue`() {
        val q = RecommendationQueue()
        q.offer(rec("a"))
        q.offer(rec("urgent", Recommendation.Priority.HIGH))
        assertEquals("urgent", q.peek()?.id)
    }

    @Test
    fun `duplicate ids are rejected`() {
        val q = RecommendationQueue()
        assertTrue(q.offer(rec("a")))
        assertFalse(q.offer(rec("a")))
        assertEquals(1, q.size)
    }

    @Test
    fun `taken ids are not re-offered`() {
        val q = RecommendationQueue()
        q.offer(rec("a"))
        q.take()
        assertFalse("already-seen id must not re-enter", q.offer(rec("a")))
    }

    @Test
    fun `dismiss head removes and remembers it`() {
        val q = RecommendationQueue()
        q.offer(rec("a"))
        q.offer(rec("b"))
        q.dismissHead()
        assertEquals("b", q.peek()?.id)
        assertFalse(q.offer(rec("a")))
    }

    @Test
    fun `actionable flag tracks the prompt`() {
        assertFalse(rec("a").isActionable)
        assertTrue(rec("a").copy(actionPrompt = "do the thing").isActionable)
    }
}
