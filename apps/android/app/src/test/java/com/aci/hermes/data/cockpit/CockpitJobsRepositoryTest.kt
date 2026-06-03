package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitJobsRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun job(id: String, status: String = "RUNNING") = """
        {"id":"$id","title":"T","worker_id":"codex_cli","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z",
         "workspace_path":null,"branch":null,"base_branch":null,"remote":null,
         "validation_summary":null,"publish_state":null}
    """.trimIndent()

    @Test
    fun `refresh loads jobs when paired`() = runTest {
        val repo = CockpitJobsRepository(
            client { CockpitRawResponse(200, """{"jobs":[${job("job_1")}],"next_cursor":null,"prev_cursor":null}""") }
        )
        repo.refresh()
        assertEquals(1, repo.jobs.value.size)
        assertEquals("job_1", repo.jobs.value[0].id)
        assertEquals("RUNNING", repo.jobs.value[0].status)
        assertTrue(repo.sync.value is JobsSync.Loaded)
    }

    @Test
    fun `unpaired refresh yields empty list and NotPaired, no fake jobs`() = runTest {
        val repo = CockpitJobsRepository(client(token = null) { error("must not hit the wire") })
        repo.refresh()
        assertEquals(JobsSync.NotPaired, repo.sync.value)
        assertTrue(repo.jobs.value.isEmpty())
    }

    @Test
    fun `dispatch posts then refreshes the list`() = runTest {
        var dispatched = false
        val repo = CockpitJobsRepository(
            client { req ->
                when {
                    req.method == "POST" && req.url.endsWith("/jobs") -> {
                        dispatched = true
                        CockpitRawResponse(201, job("job_new", "QUEUED"))
                    }
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("job_new", "QUEUED")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            }
        )
        val res = repo.dispatch(title = "T", workerId = "codex_cli", prompt = "do it")
        assertTrue(res is CockpitResult.Success)
        assertTrue(dispatched)
        assertEquals(1, repo.jobs.value.size)
        assertEquals("job_new", repo.jobs.value[0].id)
    }

    @Test
    fun `cancel conflict surfaces as a Failure`() = runTest {
        val repo = CockpitJobsRepository(
            client { CockpitRawResponse(409, """{"error":{"code":"conflict","message":"already cancelled"}}""") }
        )
        val res = repo.cancel("job_1")
        assertTrue(res is CockpitResult.Failure)
        assertEquals(409, (res as CockpitResult.Failure).httpStatus)
    }

    @Test
    fun `run posts the owner phrase to the run route then refreshes`() = runTest {
        var runBody: String? = null
        var runUrl: String? = null
        val repo = CockpitJobsRepository(
            client { req ->
                when {
                    req.method == "POST" && req.url.endsWith("/jobs/job_1/run") -> {
                        runUrl = req.url
                        runBody = req.body
                        CockpitRawResponse(200, """{"job":${job("job_1", "RUNNING")},"worker_trail":[]}""")
                    }
                    else -> CockpitRawResponse(
                        200,
                        """{"jobs":[${job("job_1", "RUNNING")}],"next_cursor":null,"prev_cursor":null}""",
                    )
                }
            }
        )
        val res = repo.run("job_1", workerId = "codex-execute", authorization = "Yes, with authorization.")
        assertTrue(res is CockpitResult.Success)
        assertTrue(runUrl!!.endsWith("/jobs/job_1/run"))
        assertTrue(runBody!!.contains("\"worker_id\":\"codex-execute\""))
        assertTrue(runBody!!.contains("Yes, with authorization."))
        // refresh() ran after success.
        assertEquals(1, repo.jobs.value.size)
    }

    @Test
    fun `run without the owner phrase surfaces the gateway 403`() = runTest {
        val repo = CockpitJobsRepository(
            client {
                CockpitRawResponse(
                    403,
                    """{"error":{"code":"forbidden","message":"owner approval required to run an execute lane"}}""",
                )
            }
        )
        val res = repo.run("job_1", workerId = "codex-execute", authorization = null)
        assertTrue(res is CockpitResult.Failure)
        assertEquals(403, (res as CockpitResult.Failure).httpStatus)
    }
}
