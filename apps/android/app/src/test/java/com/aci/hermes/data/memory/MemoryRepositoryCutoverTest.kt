package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Memory off-mocks cutover: when paired, the repository serves the
 * real gateway list (mapped to the domain), deletes through the gateway,
 * and surfaces honest errors — never fake data.
 */
class MemoryRepositoryCutoverTest {

    private fun client(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { token },
        executor = CockpitHttpExecutor { exec(it) },
        ioDispatcher = Dispatchers.Unconfined,
    )

    private val listJson = """
        {"items":[
          {"id":"deploy","category":"OWNER_PREFERENCE","title":"deploy","content":"after 6pm",
           "durability":"PERMANENT","confidence":"HIGH",
           "provenance":{"source":"agent","session_id":null,"recorded_at":"2026-05-30T12:00:00+00:00","note":null},
           "created_at":"2026-05-30T12:00:00+00:00","updated_at":"2026-05-30T12:00:00+00:00",
           "last_accessed_at":null,"tags":["ops"],"redacted":false,"hidden":false}
        ]}
    """.trimIndent()

    @Test
    fun `refresh loads and maps live items when paired`() = runTest {
        val repo = MemoryRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(200, listJson) },
            paired = { true },
        )
        repo.refresh()
        val items = repo.items.value
        assertEquals(1, items.size)
        assertEquals(MemoryCategory.OWNER_PREFERENCE, items[0].category)
        assertEquals(MemoryDurability.PERMANENT, items[0].durability)
        assertEquals("ops", items[0].tags.first())
        assertTrue(repo.sync.value is MemorySync.Loaded)
        assertTrue(repo.isLive)
    }

    @Test
    fun `unpaired refresh stays mock-only and keeps the seed`() = runTest {
        val seed = MockMemorySeed.items
        val repo = MemoryRepository(
            seed = seed,
            client = client(token = null) { error("must not hit the wire when unpaired") },
            paired = { false },
        )
        repo.refresh()
        assertEquals(MemorySync.MockOnly, repo.sync.value)
        assertEquals(seed.size, repo.items.value.size)
    }

    @Test
    fun `gateway error surfaces honest error, never fake data`() = runTest {
        val repo = MemoryRepository(
            seed = emptyList(),
            client = client { CockpitRawResponse(500, "boom") },
            paired = { true },
        )
        repo.refresh()
        assertTrue(repo.sync.value is MemorySync.Error)
        assertTrue(repo.items.value.isEmpty())
    }

    @Test
    fun `delete goes through the gateway when paired`() = runTest {
        var deleteHit = false
        val repo = MemoryRepository(
            seed = emptyList(),
            client = client { req ->
                if (req.method == "DELETE") {
                    deleteHit = true
                    CockpitRawResponse(200, """{"removed":1}""")
                } else {
                    CockpitRawResponse(200, listJson)
                }
            },
            paired = { true },
        )
        repo.refresh()
        assertEquals(1, repo.items.value.size)
        repo.delete("deploy", reason = null)
        assertTrue(deleteHit)
        assertTrue(repo.items.value.isEmpty())
    }
}
