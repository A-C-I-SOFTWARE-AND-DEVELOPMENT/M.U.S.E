package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Request/response mapping for the job control + detail endpoints. Drives the
 * real [HermesCockpitClient]/[CockpitJobsRepository] over an injected executor
 * so the wire contract is exercised without a socket.
 */
class JobControlsClientTest {

    private val seen = mutableListOf<Pair<String, String>>() // method to path-suffix

    private fun client(exec: (CockpitRequest) -> CockpitRawResponse) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { "tok" },
        executor = CockpitHttpExecutor { req ->
            seen += req.method to req.url.substringAfter("/v1/cockpit/jobs")
            exec(req)
        },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun job(status: String = "RUNNING") = """
        {"id":"job_1","title":"T","worker_id":"codex_cli","status":"$status",
         "created_at":"2026-05-30T12:00:00Z","updated_at":"2026-05-30T12:00:00Z"}
    """.trimIndent()

    private fun jobsList() = """{"jobs":[${job()}],"next_cursor":null,"prev_cursor":null}"""

    /** A repo whose control POSTs succeed and whose refresh returns one job. */
    private fun repo(): CockpitJobsRepository = CockpitJobsRepository(
        client { req ->
            when {
                req.method == "GET" && req.url.endsWith("/jobs") -> CockpitRawResponse(200, jobsList())
                else -> CockpitRawResponse(200, job())
            }
        },
    )

    @Test
    fun `pause hits the pause route and refreshes`() = runTest {
        val res = repo().pause("job_1", reason = "hold")
        assertTrue(res is CockpitResult.Success)
        assertTrue(seen.any { it == "POST" to "/job_1/pause" })
        assertTrue(seen.any { it == "GET" to "" }) // refresh GET /jobs
    }

    @Test
    fun `resume hits the resume route`() = runTest {
        assertTrue(repo().resume("job_1") is CockpitResult.Success)
        assertTrue(seen.any { it == "POST" to "/job_1/resume" })
    }

    @Test
    fun `rerun hits the rerun route`() = runTest {
        assertTrue(repo().rerun("job_1") is CockpitResult.Success)
        assertTrue(seen.any { it == "POST" to "/job_1/rerun" })
    }

    @Test
    fun `approve hits the approve route carrying the owner phrase`() = runTest {
        var body: String? = null
        val repo = CockpitJobsRepository(
            client { req ->
                if (req.url.endsWith("/approve")) body = req.body
                if (req.method == "GET" && req.url.endsWith("/jobs")) {
                    CockpitRawResponse(200, jobsList())
                } else {
                    CockpitRawResponse(200, job())
                }
            },
        )
        assertTrue(repo.approve("job_1", authorization = "Yes, with authorization.") is CockpitResult.Success)
        assertTrue(seen.any { it == "POST" to "/job_1/approve" })
        assertTrue(body!!.contains("Yes, with authorization."))
    }

    @Test
    fun `detail decodes the ledger projection`() = runTest {
        val client = client {
            CockpitRawResponse(
                200,
                """
                {"id":"job_1","objective":"Do it","status":"RUNNING","plan":"",
                 "current_step":"running worker","workers":[{"id":"w","worker":"w","status":"RUNNING"}],
                 "timeline":[{"ts":"t","kind":"submit","phase":null,"actor":"owner","summary":"go"}],
                 "evidence":[],"files_touched":["a.kt"],"commands_run":[],
                 "test_results":null,"approvals":[],"rollback":null}
                """.trimIndent(),
            )
        }
        val res = CockpitJobsRepository(client).detail("job_1")
        assertTrue(res is CockpitResult.Success)
        val detail = (res as CockpitResult.Success).value
        assertEquals("Do it", detail.objective)
        assertEquals(1, detail.workers.size)
        assertEquals(1, detail.timeline.size)
        assertEquals(listOf("a.kt"), detail.filesTouched)
        assertTrue(seen.any { it == "GET" to "/job_1/ledger" })
    }

    @Test
    fun `diff decodes the patch snapshot`() = runTest {
        val client = client {
            CockpitRawResponse(
                200,
                """{"files":[{"path":"a.kt","additions":3,"deletions":1}],"diff":"@@ ...","truncated":false}""",
            )
        }
        val res = CockpitJobsRepository(client).diff("job_1")
        assertTrue(res is CockpitResult.Success)
        assertEquals(1, (res as CockpitResult.Success).value.files.size)
        assertTrue(seen.any { it == "GET" to "/job_1/diff" })
    }

    @Test
    fun `validate decodes the verification snapshot`() = runTest {
        val client = client {
            CockpitRawResponse(
                200,
                """{"gates":[{"id":"pytest","name":"pytest","status":"PASS"}],
                   "policy":{"all_must_pass":true,"override_requires_note":true}}""".trimIndent(),
            )
        }
        val res = CockpitJobsRepository(client).validate("job_1")
        assertTrue(res is CockpitResult.Success)
        assertEquals(1, (res as CockpitResult.Success).value.gates.size)
        assertTrue(seen.any { it == "POST" to "/job_1/validate" })
    }
}
