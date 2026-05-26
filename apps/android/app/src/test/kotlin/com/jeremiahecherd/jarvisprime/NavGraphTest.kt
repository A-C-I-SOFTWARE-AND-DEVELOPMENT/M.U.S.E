package com.jeremiahecherd.jarvisprime

import com.jeremiahecherd.jarvisprime.nav.ONBOARDING_ROUTES
import com.jeremiahecherd.jarvisprime.nav.Routes
import org.junit.Assert.assertEquals
import org.junit.Test

class NavGraphTest {

    @Test
    fun onboardingHasAllNineSpecifiedScreensInOrder() {
        val expected = listOf(
            Routes.WELCOME,
            Routes.WHAT,
            Routes.OWNER,
            Routes.MODE,
            Routes.NOTIFICATION,
            Routes.VOICE,
            Routes.ICON,
            Routes.EMERGENCY_STOP,
            Routes.FINISH,
        )
        assertEquals(expected, ONBOARDING_ROUTES)
    }
}
