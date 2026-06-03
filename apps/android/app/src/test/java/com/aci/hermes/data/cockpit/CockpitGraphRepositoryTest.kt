package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Exercises the GraphRAG client request-building + DTO deserialization through
 * a fake [CockpitHttpExecutor], mirroring CockpitJobsRepositoryTest. No socket,
 * no device — pure JVM unit test.
 */
class CockpitGraphRepositoryTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    @Test
    fun `relatedForJob builds the job_id query and maps items`() = runTest {
        var seenUrl = ""
        val repo = CockpitGraphRepository(
            client { req ->
                seenUrl = req.url
                CockpitRawResponse(
                    200,
                    """
                    {"node":"task:abc","origin":"orc-1","related":[
                      {"kind":"FILE","node_type":"file","title":"run_agent.py",
                       "ref":"run_agent.py","relation":"depends_on","source_backed":true,
                       "sources":[{"uri":"orc-1","kind":"job_ledger"}]},
                      {"kind":"DECISION","node_type":"decision","title":"Localization",
                       "ref":"memory:x","relation":"cites","source_backed":true,"sources":[]}
                    ]}
                    """.trimIndent(),
                )
            },
        )
        val res = repo.relatedForJob("orc-1")
        assertTrue(res is CockpitResult.Success)
        val list = (res as CockpitResult.Success).value
        assertTrue(seenUrl.contains("/v1/cockpit/graph/related"))
        assertTrue(seenUrl.contains("job_id=orc-1"))
        assertEquals(2, list.related.size)
        assertEquals(RelatedKind.FILE, list.related[0].bucket)
        assertEquals("depends_on", list.related[0].relation)
        assertTrue(list.related[0].sourceBacked)
        assertEquals(RelatedKind.DECISION, list.related[1].bucket)
    }

    @Test
    fun `query maps a coding GraphAnswer`() = runTest {
        val repo = CockpitGraphRepository(
            client { req ->
                assertTrue(req.url.contains("mode=coding"))
                assertTrue(req.url.contains("q="))
                CockpitRawResponse(
                    200,
                    """
                    {"mode":"coding","question":"add function","nodes":[
                       {"id":"file:1","type":"file","title":"calc.py","key":"calc.py"}],
                     "edges":[{"src":"file:1","dst":"function:2","type":"owns"}],
                     "citations":[{"uri":"calc.py","kind":"repo"}],
                     "communities":[]}
                    """.trimIndent(),
                )
            },
        )
        val res = repo.query("add function", "coding")
        assertTrue(res is CockpitResult.Success)
        val answer = (res as CockpitResult.Success).value
        assertEquals("coding", answer.mode)
        assertEquals(1, answer.nodes.size)
        assertEquals("file", answer.nodes[0].type)
        assertEquals(1, answer.citations.size)
    }

    @Test
    fun `build maps the rebuild stats`() = runTest {
        val repo = CockpitGraphRepository(
            client { req ->
                assertEquals("POST", req.method)
                assertTrue(req.url.endsWith("/v1/cockpit/graph/build"))
                CockpitRawResponse(
                    200,
                    """{"saved":"/h/graph.json","nodes":42,"edges":99,
                        "by_node_type":{"file":10},"by_edge_type":{"owns":20}}""".trimIndent(),
                )
            },
        )
        val res = repo.build()
        assertTrue(res is CockpitResult.Success)
        val stats = (res as CockpitResult.Success).value
        assertEquals(42, stats.nodes)
        assertEquals(99, stats.edges)
        assertEquals(10, stats.byNodeType["file"])
    }

    @Test
    fun `unknown related kind falls back to UNKNOWN bucket`() = runTest {
        val repo = CockpitGraphRepository(
            client { CockpitRawResponse(200, """{"node":"","related":[
                {"kind":"WEIRD","title":"x","ref":"x","relation":"related"}]}""") },
        )
        val res = repo.relatedForMemory("m1")
        val item = (res as CockpitResult.Success).value.related.first()
        assertEquals(RelatedKind.UNKNOWN, item.bucket)
        assertFalse(item.sourceBacked)
    }
}
