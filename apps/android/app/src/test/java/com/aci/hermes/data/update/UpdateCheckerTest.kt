package com.aci.hermes.data.update

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-logic tests for the update decision. JSON parsing (`UpdateManifest.parse`)
 * uses `org.json`, which is stubbed under this module's
 * `unitTests.isReturnDefaultValues`, so it is exercised on-device rather than
 * here — these tests cover the version comparison and the unreachable path,
 * which is where the actual decision lives.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class UpdateCheckerTest {

    private fun manifest(versionCode: Int) = UpdateManifest(
        versionCode = versionCode,
        versionName = "v$versionCode",
        apkUrl = "https://example.invalid/app.apk",
        notes = "notes",
    )

    @Test
    fun `newer versionCode is offered as available`() {
        val state = UpdateState.evaluate(
            currentVersionCode = 10,
            currentVersionName = "v10",
            manifest = manifest(11),
        )
        assertTrue(state is UpdateState.Available)
        assertEquals("v11", (state as UpdateState.Available).versionName)
        assertEquals("https://example.invalid/app.apk", state.apkUrl)
    }

    @Test
    fun `equal versionCode is up to date`() {
        val state = UpdateState.evaluate(10, "v10", manifest(10))
        assertTrue(state is UpdateState.UpToDate)
        assertEquals("v10", (state as UpdateState.UpToDate).versionName)
    }

    @Test
    fun `older manifest versionCode is up to date (never downgrades)`() {
        val state = UpdateState.evaluate(10, "v10", manifest(9))
        assertTrue(state is UpdateState.UpToDate)
    }

    @Test
    fun `null manifest is unknown, not an update`() {
        val state = UpdateState.evaluate(10, "v10", manifest = null)
        assertTrue(state is UpdateState.Unknown)
    }

    @Test
    fun `check maps an unreachable channel to unknown`() = runTest {
        val checker = UpdateChecker(
            currentVersionCode = 10,
            currentVersionName = "v10",
            fetch = { null },
            dispatcher = Dispatchers.Unconfined,
        )
        assertTrue(checker.check() is UpdateState.Unknown)
    }
}
