package com.aci.hermes.data.life

import org.junit.Assert.assertEquals
import org.junit.Test
import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes
import kotlin.time.Duration.Companion.seconds

class BehaviorSchedulerTest {

    private val scheduler = BehaviorScheduler()

    private fun tick(
        idleFor: Duration = 0.seconds,
        localHour: Int = 12,
        hasPendingRecommendation: Boolean = false,
        sinceLastRecommendation: Duration = Duration.INFINITE,
        agentBusy: Boolean = false,
        ambientMuted: Boolean = false,
    ) = BehaviorScheduler.Tick(
        idleFor, localHour, hasPendingRecommendation, sinceLastRecommendation, agentBusy, ambientMuted,
    )

    @Test
    fun `agent busy holds the body idle`() {
        assertEquals(AvatarBehavior.IDLE, scheduler.decide(tick(idleFor = 30.minutes, agentBusy = true)))
    }

    @Test
    fun `fresh idle is plain idle`() {
        assertEquals(AvatarBehavior.IDLE, scheduler.decide(tick(idleFor = 5.seconds)))
    }

    @Test
    fun `boredom drifts into wander`() {
        assertEquals(AvatarBehavior.WANDER, scheduler.decide(tick(idleFor = 1.minutes)))
    }

    @Test
    fun `night-time means sleep regardless of idle`() {
        assertEquals(AvatarBehavior.SLEEP, scheduler.decide(tick(idleFor = 5.seconds, localHour = 2)))
        // window wraps past midnight: 23:00 is inside [23,6)
        assertEquals(AvatarBehavior.SLEEP, scheduler.decide(tick(idleFor = 5.seconds, localHour = 23)))
    }

    @Test
    fun `deep inactivity sleeps even during the day`() {
        assertEquals(AvatarBehavior.SLEEP, scheduler.decide(tick(idleFor = 30.minutes, localHour = 14)))
    }

    @Test
    fun `ready recommendation after cooldown leans in`() {
        val t = tick(
            idleFor = 1.minutes,
            localHour = 14,
            hasPendingRecommendation = true,
            sinceLastRecommendation = 10.minutes,
        )
        assertEquals(AvatarBehavior.RECOMMEND, scheduler.decide(t))
    }

    @Test
    fun `recommendation suppressed inside cooldown`() {
        val t = tick(
            idleFor = 1.minutes,
            localHour = 14,
            hasPendingRecommendation = true,
            sinceLastRecommendation = 1.minutes,
        )
        // falls through to wander, not recommend
        assertEquals(AvatarBehavior.WANDER, scheduler.decide(t))
    }

    @Test
    fun `night-time beats a pending recommendation`() {
        val t = tick(
            localHour = 3,
            hasPendingRecommendation = true,
            sinceLastRecommendation = 1.minutes,
        )
        assertEquals(AvatarBehavior.SLEEP, scheduler.decide(t))
    }

    @Test
    fun `ambient mute pins idle`() {
        assertEquals(AvatarBehavior.IDLE, scheduler.decide(tick(idleFor = 30.minutes, ambientMuted = true)))
    }
}
