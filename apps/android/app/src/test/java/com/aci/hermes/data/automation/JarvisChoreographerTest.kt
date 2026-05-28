package com.aci.hermes.data.automation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisChoreographerTest {

    private val metrics = JarvisChoreographer.ScreenMetrics(
        width = 1080f,
        height = 2400f,
        avatarPosition = ScreenPoint(100f, 100f),
    )
    private val choreographer = JarvisChoreographer(metrics)

    @Test
    fun `open app runs then pushes then settles`() {
        val target = ResolvedTarget(
            label = "Facebook",
            bounds = ScreenRect(900f, 1800f, 1000f, 1900f),
            packageName = "com.facebook.katana",
        )
        val plan = choreographer.choreograph(AutomationIntent.OpenApp("facebook"), target)

        assertEquals(listOf(AvatarClip.RUN, AvatarClip.PUSH, AvatarClip.SETTLE), plan.steps.map { it.clip })
        // The real action fires on the PUSH step, and it's a package launch.
        assertEquals(1, plan.gestures.size)
        assertEquals(DeviceGesture.LaunchPackage("com.facebook.katana"), plan.gestures.single())
        // The avatar runs to the icon's center before pushing.
        assertEquals(target.bounds!!.center, plan.steps.first { it.clip == AvatarClip.PUSH }.moveTo)
    }

    @Test
    fun `open app without resolved package taps the icon center`() {
        val target = ResolvedTarget("Facebook", ScreenRect(900f, 1800f, 1000f, 1900f), packageName = null)
        val plan = choreographer.choreograph(AutomationIntent.OpenApp("facebook"), target)
        val gesture = plan.gestures.single()
        assertTrue(gesture is DeviceGesture.Tap)
        assertEquals(target.bounds!!.center, (gesture as DeviceGesture.Tap).point)
    }

    @Test
    fun `turn page left swipes from right edge to left edge`() {
        val plan = choreographer.choreograph(AutomationIntent.TurnPage(PageDirection.LEFT))
        val swipe = plan.gestures.single() as DeviceGesture.Swipe
        // right→left reveals the next (left) screen
        assertTrue("swipe should travel leftward", swipe.from.x > swipe.to.x)
        // both endpoints inset from the edges
        assertTrue(swipe.from.x > metrics.width / 2f)
        assertTrue(swipe.to.x < metrics.width / 2f)
        assertEquals(AvatarClip.PAGE_TURN, plan.steps[1].clip)
    }

    @Test
    fun `scroll down drags content upward`() {
        val plan = choreographer.choreograph(AutomationIntent.Scroll(ScrollDirection.DOWN))
        val swipe = plan.gestures.single() as DeviceGesture.Swipe
        assertTrue("scroll down means finger moves up", swipe.from.y > swipe.to.y)
    }

    @Test
    fun `navigate home emits a single global gesture and no run`() {
        val plan = choreographer.choreograph(AutomationIntent.Navigate(GlobalAction.HOME))
        assertEquals(DeviceGesture.Global(GlobalAction.HOME), plan.gestures.single())
        assertTrue(plan.steps.none { it.clip == AvatarClip.RUN })
    }

    @Test
    fun `run duration is clamped to the configured ceiling`() {
        // Far target → run time should not exceed maxRunMs.
        val plan = choreographer.choreograph(
            AutomationIntent.PushTarget("x"),
            ResolvedTarget("x", ScreenRect(1070f, 2390f, 1080f, 2400f), null),
        )
        val runMs = plan.steps.first { it.clip == AvatarClip.RUN }.approxDurationMs
        assertTrue(runMs <= JarvisChoreographer.Tuning().maxRunMs)
        assertTrue(runMs >= JarvisChoreographer.Tuning().minRunMs)
    }

    @Test
    fun `plan origin is the avatar position`() {
        val plan = choreographer.choreograph(AutomationIntent.Navigate(GlobalAction.BACK))
        assertSame(metrics.avatarPosition, plan.origin)
    }
}
