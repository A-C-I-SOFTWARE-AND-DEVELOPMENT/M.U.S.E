package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Drives [CockpitHomeRepository]'s fan-out through a fake executor that
 * routes each cockpit path to a scripted body. Covers the paired happy
 * path, the unpaired short-circuit (no wire, no fakes), and per-leg
 * degradation (one failing endpoint must not blank the rest).
 */
class CockpitHomeRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private fun ok(body: String) = CockpitRawResponse(200, body)

    private fun routed(req: CockpitRequest): CockpitRawResponse = when {
        req.url.contains("/runtime/status") -> ok(
            """{"gateway":{"version":"0.1.0","started_at":"t","pid":7,"mode":"local"},
               "host":{"platform":"Linux","arch":"x86_64","hostname":"h"},
               "queue":{"running":1,"queued":0,"waiting_approval":1}}""",
        )
        req.url.contains("/runtime/workers") -> ok(
            """{"workers":[{"id":"codex_cli","display_name":"Codex","kind":"external_cli","available":true}]}""",
        )
        req.url.contains("/models") -> ok(
            """{"routes":{"default":{"provider":"ollama","model":"llama3","enabled":true}},"free_first":true}""",
        )
        req.url.contains("/jobs") -> ok(
            """{"jobs":[{"id":"job_1","title":"Refactor","worker_id":"codex_cli","status":"RUNNING",
               "created_at":"t","updated_at":"t"}],"next_cursor":null,"prev_cursor":null}""",
        )
        req.url.contains("/approvals") -> ok(
            """{"approvals":[{"id":"a1","title":"Deploy","tier":"CRITICAL","status":"PENDING","proposed_action":"push"}]}""",
        )
        req.url.contains("/memory") -> ok(
            """{"items":[{"id":"m1","category":"pref","title":"free-first","content":"x",
               "durability":"LONG","confidence":"HIGH","provenance":{"source":"chat"}}]}""",
        )
        req.url.contains("/audit") -> ok(
            """{"records":[{"id":"au1","timestamp":"2026-05-30T12:00:00Z","action":"job_1 dispatched",
               "risk_tier":"LOW","route":{"destination":"CODEX"}}]}""",
        )
        req.url.contains("/research") -> ok(
            """{"items":[{"id":"r1","title":"Benchmark","evidence_strength":"strong","summary":"tops the board"}]}""",
        )
        else -> CockpitRawResponse(404, """{"error":{"code":"not_found","message":"no"}}""")
    }

    @Test
    fun `refresh fans out and loads every leg when paired`() = runTest {
        val repo = CockpitHomeRepository(client { routed(it) })
        repo.refresh()

        val snap = repo.snapshot.value
        assertEquals(HomeSync.Loaded, repo.sync.value)
        assertEquals(1, snap.runtime?.queue?.running)
        assertEquals(1, snap.workers?.workers?.size)
        assertEquals(true, snap.models?.freeFirst)
        assertEquals("job_1", snap.jobs?.jobs?.single()?.id)
        assertEquals("CRITICAL", snap.approvals?.approvals?.single()?.tier)
        assertEquals("m1", snap.memory?.items?.single()?.id)
        assertEquals("au1", snap.audit?.records?.single()?.id)
        assertEquals("r1", snap.research?.items?.single()?.id)
    }

    @Test
    fun `unpaired refresh yields empty snapshot and NotPaired, never hits the wire`() = runTest {
        val repo = CockpitHomeRepository(client(token = null) { error("must not hit the wire") })
        repo.refresh()
        assertEquals(HomeSync.NotPaired, repo.sync.value)
        assertTrue(repo.snapshot.value.isEmpty)
    }

    @Test
    fun `one failing leg still populates the rest`() = runTest {
        val repo = CockpitHomeRepository(
            client { req ->
                if (req.url.contains("/research")) CockpitRawResponse(500, """{"error":{"code":"x","message":"boom"}}""")
                else routed(req)
            }
        )
        repo.refresh()
        val snap = repo.snapshot.value
        assertEquals(HomeSync.Loaded, repo.sync.value)
        assertNull(snap.research) // failed leg degrades to null
        assertEquals("job_1", snap.jobs?.jobs?.single()?.id) // others intact
    }

    @Test
    fun `total unreachability reports an error rather than a blank loaded`() = runTest {
        val repo = CockpitHomeRepository(client { throw java.io.IOException("down") })
        repo.refresh()
        assertTrue(repo.sync.value is HomeSync.Error)
        assertTrue(repo.snapshot.value.isEmpty)
    }
}
