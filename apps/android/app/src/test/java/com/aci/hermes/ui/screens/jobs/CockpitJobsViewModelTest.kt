package com.aci.hermes.ui.screens.jobs

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.DetectedWorker
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.JobsSync
import com.aci.hermes.util.LogBuffer
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
class CockpitJobsViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val logBuffer = LogBuffer()

    @Before fun setUp() { Dispatchers.setMain(testDispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun job(id: String, status: String = "QUEUED") = """
        {"id":"$id","title":"T","worker_id":"codex-execute","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z"}
    """.trimIndent()

    private fun repo(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): CockpitJobsRepository = CockpitJobsRepository(
        HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        ),
    )

    @Test
    fun `loads jobs and available workers when paired`() = runTest {
        val vm = CockpitJobsViewModel(
            repo { req ->
                when {
                    req.url.endsWith("/runtime/workers") -> CockpitRawResponse(
                        200,
                        """{"workers":[{"id":"codex-execute","display_name":"Codex","kind":"cli","available":true},
                           {"id":"old","display_name":"Old","kind":"cli","available":false}]}""",
                    )
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("job_1", "RUNNING")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            },
            logBuffer,
        )
        advanceUntilIdle()
        assertEquals(1, vm.ui.value.jobs.size)
        assertTrue(vm.ui.value.sync is JobsSync.Loaded)
        // Only the available worker is offered to the dispatch picker.
        assertEquals(listOf("codex-execute"), vm.ui.value.workers.map { it.id })
    }

    @Test
    fun `unpaired shows NotPaired and no fabricated jobs`() = runTest {
        val vm = CockpitJobsViewModel(repo(token = null) { error("must not hit the wire") }, logBuffer)
        advanceUntilIdle()
        assertEquals(JobsSync.NotPaired, vm.ui.value.sync)
        assertTrue(vm.ui.value.jobs.isEmpty())
    }

    @Test
    fun `run surfaces the gateway 403 hint when the owner phrase is missing`() = runTest {
        val vm = CockpitJobsViewModel(
            repo { req ->
                if (req.url.contains("/run")) {
                    CockpitRawResponse(
                        403,
                        """{"error":{"code":"forbidden","message":"owner approval required",
                           "details":{"hint":"send authorization exactly: 'Yes, with authorization.'"}}}""",
                    )
                } else {
                    CockpitRawResponse(200, """{"jobs":[],"next_cursor":null,"prev_cursor":null}""")
                }
            },
            logBuffer,
        )
        advanceUntilIdle()
        vm.run("job_1", workerId = "codex-execute", authorization = null)
        advanceUntilIdle()
        assertTrue(vm.ui.value.snackbar!!.contains("owner approval required"))
    }

    @Test
    fun `runRequiresAuthorization is false for local planner and handoff lanes only`() {
        fun w(id: String) = DetectedWorker(id = id, displayName = id, kind = "cli", available = true)
        assertTrue(CockpitJobsViewModel.runRequiresAuthorization(w("codex-execute")))
        assertTrue(CockpitJobsViewModel.runRequiresAuthorization(w("claude-execute")))
        assertTrue(!CockpitJobsViewModel.runRequiresAuthorization(w("hermes-local-planner")))
        assertTrue(!CockpitJobsViewModel.runRequiresAuthorization(w("clipboard-handoff")))
    }
}
