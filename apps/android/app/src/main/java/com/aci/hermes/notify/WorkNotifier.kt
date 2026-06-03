package com.aci.hermes.notify

/**
 * Sink for [WorkEvent]s. Kept as an interface so [WorkWatcher] can be unit
 * tested with a recording fake — the real [JarvisNotifier] posts to the
 * Android shade.
 */
fun interface WorkNotifier {
    fun post(event: WorkEvent)
}
