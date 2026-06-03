package com.aci.hermes.testutil

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Run a suspend [block] to completion and return its value, bounded by
 * [timeoutMs]. The block runs on its own `Dispatchers.Unconfined` scope and the
 * caller parks on a latch — unlike `runBlocking`, this never blocks the thread
 * indefinitely. That matters under Robolectric: a `runBlocking` against the
 * process-shared settings DataStore can deadlock once the singleton has been
 * initialised by a *prior* test class, whereas coroutine-based access keeps
 * working. A timeout surfaces as a bounded test failure, never an infinite hang
 * (which would wedge the whole `testDebugUnitTest` task in CI).
 */
fun <T> awaitValue(timeoutMs: Long = 5_000, block: suspend () -> T): T {
    val latch = CountDownLatch(1)
    val ref = AtomicReference<Result<T>>()
    CoroutineScope(Dispatchers.Unconfined).launch {
        ref.set(runCatching { block() })
        latch.countDown()
    }
    if (!latch.await(timeoutMs, TimeUnit.MILLISECONDS)) {
        throw AssertionError("Timed out after ${timeoutMs}ms awaiting suspend value")
    }
    return ref.get().getOrThrow()
}

/**
 * Poll [condition] until it is true or [timeoutMs] elapses.
 *
 * ViewModels here drive real DataStore / file IO on `Dispatchers.IO`, which a
 * `TestScheduler` cannot virtually advance. With `Dispatchers.Main` bound to the
 * real `Dispatchers.Unconfined`, those continuations resume inline on the IO
 * thread, so a short real-time poll is the deterministic way to wait for the
 * resulting state — no flaky fixed sleeps.
 */
fun awaitUntil(timeoutMs: Long = 5_000, intervalMs: Long = 20, message: String = "condition", condition: () -> Boolean) {
    val deadline = System.currentTimeMillis() + timeoutMs
    while (System.currentTimeMillis() < deadline) {
        if (condition()) return
        Thread.sleep(intervalMs)
    }
    if (!condition()) throw AssertionError("Timed out after ${timeoutMs}ms waiting for: $message")
}
