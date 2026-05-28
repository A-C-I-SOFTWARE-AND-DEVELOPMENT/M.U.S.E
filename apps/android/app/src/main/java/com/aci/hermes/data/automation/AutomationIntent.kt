package com.aci.hermes.data.automation

/**
 * High-level, device-driving intents the avatar can physically perform
 * from the floating overlay. These are deliberately coarse — the
 * choreographer turns each one into a [MotionPlan] of run/push/page
 * steps plus the real gesture the accessibility service dispatches.
 *
 * Pure data; no Android. The voice/chat layers classify a transcript
 * into one of these via [AutomationIntentParser].
 */
sealed interface AutomationIntent {
    /** "Open Facebook" — run to the icon, push it, app launches. */
    data class OpenApp(val query: String) : AutomationIntent

    /** "Next screen" / "swipe left" — run to the edge, turn the page. */
    data class TurnPage(val direction: PageDirection) : AutomationIntent

    /** "Scroll down" — drag the content area. */
    data class Scroll(val direction: ScrollDirection) : AutomationIntent

    /** "Tap that" / "press the blue button" — push a resolved target. */
    data class PushTarget(val query: String) : AutomationIntent

    /** "Go home" / "go back". */
    data class Navigate(val action: GlobalAction) : AutomationIntent
}

enum class PageDirection { LEFT, RIGHT }
enum class ScrollDirection { UP, DOWN }

/**
 * Deterministic transcript → [AutomationIntent] classifier. Follows the
 * same tight-ruleset philosophy as [com.aci.hermes.data.jarvis.JarvisIntentClassifier]
 * — no NLU, just a predictable mapping that's easy to unit-test and tune.
 *
 * Returns null when the utterance isn't a device-driving command (the
 * caller then falls back to the normal chat/task path).
 */
object AutomationIntentParser {

    fun parse(utterance: String): AutomationIntent? {
        val lower = utterance.trim().lowercase()
        if (lower.isEmpty()) return null

        navigate(lower)?.let { return it }
        page(lower)?.let { return it }
        scroll(lower)?.let { return it }
        open(lower)?.let { return it }
        push(lower)?.let { return it }
        return null
    }

    private fun navigate(lower: String): AutomationIntent? = when {
        lower == "go home" || lower == "home" || lower == "go to home" ->
            AutomationIntent.Navigate(GlobalAction.HOME)
        lower == "go back" || lower == "back" || lower == "navigate back" ->
            AutomationIntent.Navigate(GlobalAction.BACK)
        lower == "recents" || lower == "recent apps" || lower == "show recents" ->
            AutomationIntent.Navigate(GlobalAction.RECENTS)
        else -> null
    }

    private fun page(lower: String): AutomationIntent? = when {
        containsAny(lower, listOf("next screen", "next page", "swipe left", "turn the page")) ->
            AutomationIntent.TurnPage(PageDirection.LEFT)
        containsAny(lower, listOf("previous screen", "prev screen", "previous page", "swipe right", "go back a page")) ->
            AutomationIntent.TurnPage(PageDirection.RIGHT)
        else -> null
    }

    private fun scroll(lower: String): AutomationIntent? = when {
        containsAny(lower, listOf("scroll down", "scroll downwards", "page down")) ->
            AutomationIntent.Scroll(ScrollDirection.DOWN)
        containsAny(lower, listOf("scroll up", "scroll upwards", "page up")) ->
            AutomationIntent.Scroll(ScrollDirection.UP)
        else -> null
    }

    private fun open(lower: String): AutomationIntent? {
        val triggers = listOf("open ", "launch ", "start ", "go to ", "look at ", "show me ")
        val hit = triggers.firstOrNull { lower.startsWith(it) } ?: return null
        val query = lower.removePrefix(hit)
            .removePrefix("the ")
            .removeSuffix(" app")
            .removeSuffix(" please")
            .trim()
        if (query.isEmpty()) return null
        return AutomationIntent.OpenApp(query)
    }

    private fun push(lower: String): AutomationIntent? {
        val triggers = listOf("tap ", "press ", "click ", "push ")
        val hit = triggers.firstOrNull { lower.startsWith(it) } ?: return null
        val query = lower.removePrefix(hit)
            .removePrefix("the ")
            .removePrefix("on ")
            .trim()
        if (query.isEmpty()) return null
        return AutomationIntent.PushTarget(query)
    }

    private fun containsAny(haystack: String, needles: List<String>): Boolean =
        needles.any { it in haystack }
}
