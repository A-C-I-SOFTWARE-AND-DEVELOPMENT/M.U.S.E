package com.aci.hermes.ui.screens.jobs

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The Jobs surface drives the orchestrate → run pipeline. These tests pin the
 * honest behaviors: a paired runtime lists real jobs, submit projects the new
 * job, and an execute lane without the owner phrase surfaces the 403 as a
 * clear "owner approval required" message (never a fake success).
 */
@OptIn(ExperimentalCoroutinesApi::class)
class JobsViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun job(id: String, status: String = "QUEUED") = """
        {"id":"$id","title":"T","worker_id":"","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z",
         "workspace_path":null,"branch":null,"base_branch":null,"remote":null,
         "validation_summary":null,"publish_state":null}
    """.trimIndent()

    @Test
    fun `init lists jobs when paired`() = runTest {
        val vm = JobsViewModel(
            client { CockpitRawResponse(200, """{"jobs":[${job("job_1")}],"next_cursor":null,"prev_cursor":null}""") }
        )
        assertEquals(1, vm.state.value.jobs.size)
        assertEquals("job_1", vm.state.value.jobs[0].id)
        assertFalse(vm.state.value.notPaired)
    }

    @Test
    fun `unreachable runtime flips notPaired, no fake jobs`() = runTest {
        val vm = JobsViewModel(client(token = null) { error("must not hit the wire") })
        assertTrue(vm.state.value.notPaired)
        assertTrue(vm.state.value.jobs.isEmpty())
    }

    @Test
    fun `submit projects the new job and reports it`() = runTest {
        val vm = JobsViewModel(
            client { req ->
                when {
                    req.method == "POST" && req.url.endsWith("/orchestrate") ->
                        CockpitRawResponse(201, job("job_new"))
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("job_new")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            }
        )
        vm.submit("add a worker-runs view")
        assertTrue(vm.state.value.message.contains("Submitted"))
        assertEquals("job_new", vm.state.value.jobs[0].id)
    }

    @Test
    fun `execute lane without phrase surfaces owner-approval message`() = runTest {
        val vm = JobsViewModel(
            client { req ->
                when {
                    req.url.contains("/run") ->
                        CockpitRawResponse(403, """{"error":"owner approval required"}""")
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("job_1")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            }
        )
        vm.run("job_1", "codex-execute", null)
        assertTrue(vm.state.value.message.contains("Owner approval required"))
    }
}
