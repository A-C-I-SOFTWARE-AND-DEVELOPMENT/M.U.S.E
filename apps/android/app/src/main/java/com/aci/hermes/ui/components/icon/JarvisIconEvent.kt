package com.aci.hermes.ui.components.icon

/**
 * Stable, finite set of user-driven events the interactive Jarvis Prime
 * icon emits. Sealed so callers can exhaustive-`when` over it and the
 * binary surface is locked — adding a new event is an explicit break.
 *
 * Semantics:
 *  - [Tap] — primary action (e.g. open chat).
 *  - [LongPress] — secondary action (e.g. emergency-stop confirm).
 *  - [DoubleTap] — meta action (e.g. announce current status / re-arm).
 *  - [SwipeUp] — escalate / expand (e.g. open Tasks).
 *  - [SwipeDown] — dismiss / collapse (e.g. mute briefly).
 *
 * The icon owns gesture *detection*; the caller owns gesture *meaning*.
 */
sealed class JarvisIconEvent {
    object Tap : JarvisIconEvent()
    object LongPress : JarvisIconEvent()
    object DoubleTap : JarvisIconEvent()
    object SwipeUp : JarvisIconEvent()
    object SwipeDown : JarvisIconEvent()
}

/**
 * Single funnel for icon events. Declared as a `fun interface` so
 * call sites can pass a lambda or a method reference without ceremony:
 *
 * ```kotlin
 * JarvisInteractiveIcon(state = state) { event -> handle(event) }
 * ```
 */
fun interface JarvisIconEventHandler {
    fun onEvent(event: JarvisIconEvent)
}
