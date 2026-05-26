package com.aci.hermes.ui.components.icon

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Test

/**
 * Pins the [JarvisIconEvent] surface. The event model is the binary
 * contract the caller binds to — silent additions or refactors break
 * exhaustive `when` blocks downstream, so this test guards both the
 * shape and the count.
 */
class JarvisIconEventModelTest {

    @Test
    fun `every event subclass is a singleton object`() {
        assertSame(JarvisIconEvent.Tap, JarvisIconEvent.Tap)
        assertSame(JarvisIconEvent.LongPress, JarvisIconEvent.LongPress)
        assertSame(JarvisIconEvent.DoubleTap, JarvisIconEvent.DoubleTap)
        assertSame(JarvisIconEvent.SwipeUp, JarvisIconEvent.SwipeUp)
        assertSame(JarvisIconEvent.SwipeDown, JarvisIconEvent.SwipeDown)
    }

    @Test
    fun `exhaustive when covers every event`() {
        val all = listOf(
            JarvisIconEvent.Tap,
            JarvisIconEvent.LongPress,
            JarvisIconEvent.DoubleTap,
            JarvisIconEvent.SwipeUp,
            JarvisIconEvent.SwipeDown,
        )
        // Exhaustive `when` — compiler enforces every branch is handled.
        val names: List<String> = all.map { event ->
            when (event) {
                JarvisIconEvent.Tap -> "tap"
                JarvisIconEvent.LongPress -> "long_press"
                JarvisIconEvent.DoubleTap -> "double_tap"
                JarvisIconEvent.SwipeUp -> "swipe_up"
                JarvisIconEvent.SwipeDown -> "swipe_down"
            }
        }
        assertEquals(
            listOf("tap", "long_press", "double_tap", "swipe_up", "swipe_down"),
            names,
        )
        assertEquals("no duplicate events", names.size, names.toSet().size)
    }

    @Test
    fun `handler funnel receives the exact event instance`() {
        val received = mutableListOf<JarvisIconEvent>()
        val handler = JarvisIconEventHandler { received += it }
        handler.onEvent(JarvisIconEvent.LongPress)
        handler.onEvent(JarvisIconEvent.SwipeUp)
        assertEquals(2, received.size)
        assertSame(JarvisIconEvent.LongPress, received[0])
        assertSame(JarvisIconEvent.SwipeUp, received[1])
    }

    @Test
    fun `each event class name matches the mission gesture vocabulary`() {
        // The mission contract is: tap, long_press, double_tap, swipe_up, swipe_down.
        // We pin the simple names without reflection (kotlin-reflect is not on
        // the test classpath) — `javaClass.simpleName` works with just stdlib.
        assertEquals("Tap", JarvisIconEvent.Tap.javaClass.simpleName)
        assertEquals("LongPress", JarvisIconEvent.LongPress.javaClass.simpleName)
        assertEquals("DoubleTap", JarvisIconEvent.DoubleTap.javaClass.simpleName)
        assertEquals("SwipeUp", JarvisIconEvent.SwipeUp.javaClass.simpleName)
        assertEquals("SwipeDown", JarvisIconEvent.SwipeDown.javaClass.simpleName)
    }
}
