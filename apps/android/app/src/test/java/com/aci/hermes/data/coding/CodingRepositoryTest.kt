package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class CodingRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse = { error("no wire expected") },
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun repo(
        paired: Boolean,
        mock: Boolean = false,
        scope: kotlinx.coroutines.CoroutineScope,
        exec: (CockpitRequest) -> CockpitRawResponse = { error("no wire expected") },
    ): CodingRepository {
        val store = CodingTaskStore(
            Files.createTempDirectory("coding-repo").toFile(),
            scope = scope,
            ioDispatcher = Dispatchers.Unconfined,
        )
        return CodingRepository(
            client = client(token = if (paired) "tok" else null, exec = exec),
            store = store,
            paired = { paired },
            mockMode = { mock },
        )
    }

    @Test
    fun `mock mode plans a demo packet without any backend`() = runTest {
        val r = repo(paired = false, mock = true, scope = this)
        val draft = r.createDraft("add a feature", "")
        val res = r.runPlan(draft.id)
        assertTrue(res is CodingActionResult.Ok)
        val task = (res as CodingActionResult.Ok).task
        assertEquals(CodingHandoffState.PLANNED, task.state)
        assertTrue(task.demo)
        assertTrue(task.packet!!.acceptanceCriteria.isNotEmpty())
    }

    @Test
    fun `unpaired audit queues offline and never hits the wire`() = runTest {
        val r = repo(paired = false, mock = false, scope = this) { error("must not hit wire") }
        val draft = r.createDraft("do a thing", "")
        val res = r.runAudit(draft.id)
        assertTrue(res is CodingActionResult.NeedsPairing)
        assertEquals(CodingHandoffState.QUEUED_OFFLINE, r.byId(draft.id)?.state)
    }

    @Test
    fun `paired audit and plan map backend results`() = runTest {
        val r = repo(paired = true, scope = this) { req ->
            when {
                req.url.endsWith("/coding/audit") -> CockpitRawResponse(
                    200,
                    """{"intent":"implement","risk_class":"RC2","primary_worker":"claude-code",
                        "owner_gates":[],"blocked":false,"rationale":"scoped"}""",
                )
                req.url.endsWith("/coding/plan") -> CockpitRawResponse(
                    200,
                    """{"packet":{"mission":"Implement","risk_class":"RC2",
                        "allowed_files":["a.kt"],"acceptance_criteria":["tests pass"],
                        "rollback_plan":["revert"]},
                        "validation":{"ok":true,"findings":[]},"owner_gate_required":false}""",
                )
                else -> error("unexpected ${req.url}")
            }
        }
        val draft = r.createDraft("Implement X", "/repo")
        assertEquals("RC2", (r.runAudit(draft.id) as CodingActionResult.Ok).task.audit?.riskClass)
        val planned = r.runPlan(draft.id) as CodingActionResult.Ok
        assertEquals(CodingHandoffState.PLANNED, planned.task.state)
        assertTrue(planned.task.validationOk)
        assertEquals("Implement", planned.task.packet?.mission)
    }

    @Test
    fun `execute without phrase surfaces the owner gate and stages the job`() = runTest {
        val r = repo(paired = true, scope = this) { req ->
            CockpitRawResponse(
                200,
                """{"status":"approval_required","authorization_required":true,
                    "authorization_hint":"Reply: Yes, with authorization.",
                    "job":{"id":"job-9","status":"WAITING_FOR_APPROVAL","prompt":"x"}}""",
            )
        }
        val draft = r.createDraft("ship it", "/repo")
        val res = r.runExecute(draft.id, authorization = null)
        assertTrue(res is CodingActionResult.OwnerGateRequired)
        assertEquals(CodingHandoffState.BLOCKED_OWNER, r.byId(draft.id)?.state)
        assertEquals("job-9", r.byId(draft.id)?.jobId)
    }

    @Test
    fun `execute dispatched moves the task to executing`() = runTest {
        val r = repo(paired = true, scope = this) { _ ->
            CockpitRawResponse(
                200,
                """{"status":"dispatched","job":{"id":"job-1","status":"RUNNING","prompt":"x"}}""",
            )
        }
        val draft = r.createDraft("go", "/repo")
        val res = r.runExecute(draft.id, authorization = "Yes, with authorization.")
        assertTrue(res is CodingActionResult.Ok)
        assertEquals(CodingHandoffState.EXECUTING, r.byId(draft.id)?.state)
    }

    @Test
    fun `execute retry resumes the staged job id`() = runTest {
        val bodies = mutableListOf<String>()
        val r = repo(paired = true, scope = this) { req ->
            bodies += req.body.orEmpty()
            CockpitRawResponse(
                200,
                """{"status":"approval_required","authorization_required":true,
                    "authorization_hint":"phrase","job":{"id":"job-7","status":"WAITING_FOR_APPROVAL","prompt":"x"}}""",
            )
        }
        val draft = r.createDraft("ship", "/repo")
        r.runExecute(draft.id, authorization = null) // stages job-7
        r.runExecute(draft.id, authorization = "Yes, with authorization.") // authorize retry
        // First call carries no job id; the retry resumes the staged job
        // (so the backend won't create — and leak — a second one).
        assertFalse(bodies[0].contains("job-7"))
        assertTrue(bodies[1].contains("job-7"))
    }

    @Test
    fun `backend failure surfaces as Failure with an error state`() = runTest {
        val r = repo(paired = true, scope = this) { _ ->
            CockpitRawResponse(422, """{"error":{"code":"unprocessable","message":"bad packet"}}""")
        }
        val draft = r.createDraft("nope", "/repo")
        val res = r.runPlan(draft.id)
        assertTrue(res is CodingActionResult.Failure)
        assertEquals(CodingHandoffState.ERROR, r.byId(draft.id)?.state)
    }
}
