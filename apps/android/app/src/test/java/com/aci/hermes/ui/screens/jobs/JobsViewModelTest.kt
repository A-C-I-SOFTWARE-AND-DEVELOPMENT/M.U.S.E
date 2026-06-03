package com.aci.hermes.ui.screens.jobs

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.JobsSync
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Tests for [JobsViewModel]. Drives the real [CockpitJobsRepository] through a
 * fake [CockpitHttpExecutor] (same approach as CockpitJobsRepositoryTest) so
 * the ViewModel's projection of the repository state is exercised end-to-end
 * without an emulator or a socket.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class JobsViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        // viewModelScope dispatches on Dispatchers.Main, absent on the JVM.
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun repo(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = CockpitJobsRepository(
        HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        ),
    )

    private fun job(id: String, status: String = "RUNNING") = """
        {"id":"$id","title":"T","worker_id":"codex_cli","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z",
         "workspace_path":null,"branch":null,"base_branch":null,"remote":null,
         "validation_summary":null,"publish_state":null}
    """.trimIndent()

    private fun jobList(vararg jobs: String) =
        """{"jobs":[${jobs.joinToString(",")}],"next_cursor":null,"prev_cursor":null}"""

    @Test
    fun `init loads jobs when paired`() = runTest {
        val vm = JobsViewModel(repo { CockpitRawResponse(200, jobList(job("job_1"))) })

        assertEquals(1, vm.jobs.value.size)
        assertEquals("job_1", vm.jobs.value[0].id)
        assertTrue(vm.sync.value is JobsSync.Loaded)
    }

    @Test
    fun `unpaired init yields NotPaired and no fake jobs`() = runTest {
        val vm = JobsViewModel(repo(token = null) { error("must not hit the wire") })

        assertEquals(JobsSync.NotPaired, vm.sync.value)
        assertTrue(vm.jobs.value.isEmpty())
    }

    @Test
    fun `gateway error surfaces JobsSync_Error`() = runTest {
        val vm = JobsViewModel(
            repo { CockpitRawResponse(500, """{"error":{"code":"boom","message":"kaboom"}}""") },
        )

        assertTrue(vm.sync.value is JobsSync.Error)
        assertTrue(vm.jobs.value.isEmpty())
    }

    @Test
    fun `cancel posts then refreshes the list`() = runTest {
        var cancelled = false
        val vm = JobsViewModel(
            repo { req ->
                when {
                    req.method == "POST" && req.url.contains("/cancel") -> {
                        cancelled = true
                        CockpitRawResponse(200, job("job_1", "CANCELLED"))
                    }
                    else -> CockpitRawResponse(200, jobList(job("job_1", "CANCELLED")))
                }
            },
        )

        vm.cancel("job_1")

        assertTrue("cancel must POST to the gateway", cancelled)
        assertEquals("CANCELLED", vm.jobs.value.firstOrNull()?.status)
    }
}
