package com.aci.hermes.ui.screens.jobs

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.JobLane
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
import org.junit.Assert.assertFalse
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
        {"id":"$id","title":"T","worker_id":"","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z"}
    """.trimIndent()

    private val lanesJson = """
        {"lanes":[
          {"id":"hermes-local-planner","display_name":"Planner","requires_approval":false},
          {"id":"codex-execute","display_name":"Codex (execute)","requires_approval":true}
        ]}
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
    fun `loads orchestrator jobs and runnable lanes when paired`() = runTest {
        val vm = CockpitJobsViewModel(
            repo { req ->
                when {
                    req.url.endsWith("/jobs/lanes") -> CockpitRawResponse(200, lanesJson)
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("orc-1", "RUNNING")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            },
            logBuffer,
        )
        advanceUntilIdle()
        assertEquals(1, vm.ui.value.jobs.size)
        assertTrue(vm.ui.value.sync is JobsSync.Loaded)
        assertEquals(listOf("hermes-local-planner", "codex-execute"), vm.ui.value.lanes.map { it.id })
    }

    @Test
    fun `unpaired shows NotPaired and no fabricated jobs`() = runTest {
        val vm = CockpitJobsViewModel(repo(token = null) { error("must not hit the wire") }, logBuffer)
        advanceUntilIdle()
        assertEquals(JobsSync.NotPaired, vm.ui.value.sync)
        assertTrue(vm.ui.value.jobs.isEmpty())
    }

    @Test
    fun `dispatch creates an orchestrator job via the orchestrate endpoint`() = runTest {
        var orchestrateUrl: String? = null
        val vm = CockpitJobsViewModel(
            repo { req ->
                when {
                    req.method == "POST" && req.url.endsWith("/orchestrate") -> {
                        orchestrateUrl = req.url
                        CockpitRawResponse(201, job("orc-new", "QUEUED"))
                    }
                    req.url.endsWith("/jobs/lanes") -> CockpitRawResponse(200, lanesJson)
                    else -> CockpitRawResponse(200, """{"jobs":[],"next_cursor":null,"prev_cursor":null}""")
                }
            },
            logBuffer,
        )
        advanceUntilIdle()
        vm.dispatch("edit the uploader")
        advanceUntilIdle()
        assertTrue(orchestrateUrl!!.endsWith("/v1/cockpit/orchestrate"))
        assertTrue(vm.ui.value.snackbar!!.contains("Created"))
    }

    @Test
    fun `run surfaces the gateway 403 hint when the owner phrase is missing`() = runTest {
        val vm = CockpitJobsViewModel(
            repo { req ->
                when {
                    req.url.contains("/run") -> CockpitRawResponse(
                        403,
                        """{"error":{"code":"forbidden","message":"owner approval required",
                           "details":{"hint":"send authorization exactly: 'Yes, with authorization.'"}}}""",
                    )
                    req.url.endsWith("/jobs/lanes") -> CockpitRawResponse(200, lanesJson)
                    else -> CockpitRawResponse(200, """{"jobs":[],"next_cursor":null,"prev_cursor":null}""")
                }
            },
            logBuffer,
        )
        advanceUntilIdle()
        vm.run("orc-1", workerId = "codex-execute", authorization = null)
        advanceUntilIdle()
        assertTrue(vm.ui.value.snackbar!!.contains("owner approval required"))
    }

    @Test
    fun `runRequiresAuthorization follows the lane's requires_approval flag`() {
        assertTrue(CockpitJobsViewModel.runRequiresAuthorization(JobLane("codex-execute", "Codex", true)))
        assertFalse(CockpitJobsViewModel.runRequiresAuthorization(JobLane("hermes-local-planner", "Planner", false)))
        // Null lane fails safe → authorization required.
        assertTrue(CockpitJobsViewModel.runRequiresAuthorization(null))
    }

    @Test
    fun `only orchestrator jobs are runnable`() {
        fun j(id: String) = com.aci.hermes.data.cockpit.CockpitJob(
            id = id, title = "t", workerId = "", status = "QUEUED",
            createdAt = "2026-01-01T00:00:00Z", updatedAt = "2026-01-01T00:00:00Z",
        )
        assertTrue(CockpitJobsViewModel.isRunnable(j("orc-abc")))
        assertFalse(CockpitJobsViewModel.isRunnable(j("job_abc")))
    }
}
