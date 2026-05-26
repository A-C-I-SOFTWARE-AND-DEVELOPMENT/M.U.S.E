package com.aci.hermes.ui.jarvis

import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertDoesNotExist
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.click
import androidx.compose.ui.test.doubleClick
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.swipeUp
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented Compose UI tests for [JarvisPrimeIcon]. Verifies:
 *   - every IconState renders without crash
 *   - every IconState exposes its accessibility label via
 *     `contentDescription`
 *   - tap / hold / long press / double tap / swipe-up gestures each
 *     fire their corresponding callback
 *   - reducedMotion=true renders the icon without the infinite pulse
 *     (asserted by the icon still being displayed and labeled
 *     correctly when the animation system is suppressed)
 */
@RunWith(AndroidJUnit4::class)
class JarvisPrimeIconTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun every_state_renders_with_its_accessibility_label() {
        // setContent can only be called once per test. We hoist the
        // state outside the composable so the test can flip it and
        // observe re-renders.
        val stateHolder = mutableStateOf(IconState.IDLE)
        composeRule.setContent {
            JarvisPrimeIcon(
                state = stateHolder.value,
                onTap = {},
                onHold = {},
                onLongPress = {},
                onDoubleTap = {},
                onSwipeUp = {},
            )
        }
        IconState.values().forEach { state ->
            composeRule.runOnUiThread { stateHolder.value = state }
            composeRule.waitForIdle()
            composeRule
                .onNodeWithContentDescription(state.accessibilityLabel())
                .assertIsDisplayed()
        }
    }

    @Test
    fun tap_fires_onTap() {
        var taps = 0
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.IDLE,
                onTap = { taps++ },
                onHold = {},
                onLongPress = {},
                onDoubleTap = {},
                onSwipeUp = {},
            )
        }
        composeRule.onNodeWithTag(JarvisIconTestTags.ROOT).performTouchInput { click() }
        composeRule.waitForIdle()
        assertEquals(1, taps)
    }

    @Test
    fun double_tap_fires_onDoubleTap() {
        var doubleTaps = 0
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.IDLE,
                onTap = {},
                onHold = {},
                onLongPress = {},
                onDoubleTap = { doubleTaps++ },
                onSwipeUp = {},
            )
        }
        composeRule
            .onNodeWithTag(JarvisIconTestTags.ROOT)
            .performTouchInput { doubleClick() }
        composeRule.waitForIdle()
        assertEquals(1, doubleTaps)
    }

    @Test
    fun long_press_fires_onLongPress_and_hold() {
        var holds = 0
        var longPresses = 0
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.IDLE,
                onTap = {},
                onHold = { holds++ },
                onLongPress = { longPresses++ },
                onDoubleTap = {},
                onSwipeUp = {},
            )
        }
        composeRule
            .onNodeWithTag(JarvisIconTestTags.ROOT)
            .performTouchInput { longClick(durationMillis = 2_000L) }
        composeRule.waitForIdle()
        // Hold fires first at 350ms; long press at 1500ms — both should
        // fire for a 2s press.
        assertTrue("onHold should fire once", holds >= 1)
        assertTrue("onLongPress should fire once", longPresses >= 1)
    }

    @Test
    fun swipe_up_fires_onSwipeUp() {
        var swipes = 0
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.IDLE,
                onTap = {},
                onHold = {},
                onLongPress = {},
                onDoubleTap = {},
                onSwipeUp = { swipes++ },
            )
        }
        composeRule
            .onNodeWithTag(JarvisIconTestTags.ROOT)
            .performTouchInput { swipeUp() }
        composeRule.waitForIdle()
        assertEquals(1, swipes)
    }

    @Test
    fun reduced_motion_still_renders_and_is_labeled() {
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.LISTENING,
                onTap = {},
                onHold = {},
                onLongPress = {},
                onDoubleTap = {},
                onSwipeUp = {},
                reducedMotion = true,
            )
        }
        composeRule
            .onNodeWithContentDescription(IconState.LISTENING.accessibilityLabel())
            .assertIsDisplayed()
    }

    @Test
    fun serious_and_critical_have_distinct_accessibility_labels() {
        // Verifies that two visually-similar "approval pending" states
        // are not collapsed into the same screen-reader announcement.
        composeRule.setContent {
            JarvisPrimeIcon(
                state = IconState.SERIOUS_ACTION_PENDING,
                onTap = {},
                onHold = {},
                onLongPress = {},
                onDoubleTap = {},
                onSwipeUp = {},
            )
        }
        composeRule
            .onNodeWithContentDescription(IconState.SERIOUS_ACTION_PENDING.accessibilityLabel())
            .assertIsDisplayed()
        composeRule
            .onNodeWithContentDescription(IconState.CRITICAL_ACTION_PENDING.accessibilityLabel())
            .assertDoesNotExist()
    }
}
