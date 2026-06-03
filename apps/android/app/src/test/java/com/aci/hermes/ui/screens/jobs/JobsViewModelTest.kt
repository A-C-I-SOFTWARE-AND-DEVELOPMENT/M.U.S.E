package com.aci.hermes.ui.screens.jobs

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.JobsSync
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class JobsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)

    @After fun tearDown() = Dispatchers.resetMain()

    private fun repo(body: String, token: String? = "tok") = CockpitJobsRepository(
        HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { CockpitRawResponse(200, body) },
            ioDispatcher = dispatcher,
        ),
    )

    private fun job(id: String, status: String) = """
        {"id":"$id","title":"$id","worker_id":"w","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z"}
    """.trimIndent()

    @Test
    fun `buckets jobs into the five sections`() = runTest(dispatcher) {
        val body = """{"jobs":[
            ${job("a", "RUNNING")},
            ${job("b", "BLOCKED")},
            ${job("c", "COMPLETED")},
            ${job("d", "FAILED")},
            ${job("e", "CANCELLED")}
        ],"next_cursor":null,"prev_cursor":null}""".trimIndent()
        val repo = repo(body)
        val vm = JobsViewModel(repo, notifier = null)
        repo.refresh()
        advanceUntilIdle()

        val s = vm.state.value
        assertEquals(listOf("a"), s.active.map { it.id })
        assertEquals(listOf("b"), s.blocked.map { it.id })
        assertEquals(listOf("c"), s.completed.map { it.id })
        assertEquals(listOf("d"), s.failed.map { it.id })
        assertEquals(listOf("e"), s.cancelled.map { it.id })
        assertTrue(s.hasActiveWork)
    }

    @Test
    fun `unpaired shows an honest empty state, no fake jobs`() = runTest(dispatcher) {
        val repo = repo("""{"jobs":[],"next_cursor":null,"prev_cursor":null}""", token = null)
        val vm = JobsViewModel(repo, notifier = null)
        repo.refresh()
        advanceUntilIdle()

        assertEquals(JobsSync.NotPaired, vm.state.value.sync)
        assertTrue(vm.state.value.isEmpty)
    }
}
