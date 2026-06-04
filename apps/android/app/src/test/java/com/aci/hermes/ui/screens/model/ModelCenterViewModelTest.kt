package com.aci.hermes.ui.screens.model

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ModelCenterViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    private val statusJson = """
        {"ollama_base":"http://127.0.0.1:11434","runtime_status":"runtime_reachable",
         "reachable":true,"reach_error":null,
         "runtimes":[{"name":"ollama","available":true,"path":"/usr/bin/ollama"}],
         "installed":[{"name":"gemma3:latest","promoted_for":["coding_build"],
                       "fallback_for":[],"status":"promoted_for_task"}],
         "promotions":{"coding_build":"gemma3"}}
    """.trimIndent()

    private fun vm(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): ModelCenterViewModel {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        return ModelCenterViewModel(client)
    }

    @Test
    fun `refresh loads installed local models when paired`() = runTest {
        val m = vm { CockpitRawResponse(200, statusJson) }
        advanceUntilIdle()
        val s = m.state.value
        assertEquals(1, s.status?.installed?.size)
        assertEquals("gemma3:latest", s.status?.installed?.first()?.name)
        assertNull(s.unavailable)
    }

    @Test
    fun `unpaired refresh degrades to an honest hint with no status`() = runTest {
        val m = vm(token = null) { error("must not hit the wire") }
        advanceUntilIdle()
        assertNull(m.state.value.status)
        assertTrue(m.state.value.unavailable != null)
    }

    @Test
    fun `smoke success marks the model smoke-tested`() = runTest {
        val m = vm { req ->
            if (req.url.endsWith("/smoke")) {
                CockpitRawResponse(200, """{"ok":true,"model":"gemma3:latest","reply_excerpt":"ok","latency_ms":42}""")
            } else {
                CockpitRawResponse(200, statusJson)
            }
        }
        advanceUntilIdle()
        m.smoke("gemma3:latest")
        advanceUntilIdle()
        assertTrue("gemma3:latest" in m.state.value.smokeTested)
    }

    @Test
    fun `smoke failure is recorded honestly, never marked ready`() = runTest {
        val m = vm { req ->
            if (req.url.endsWith("/smoke")) {
                CockpitRawResponse(200, """{"ok":false,"model":"gemma3:latest","error":"no local Ollama chat model installed"}""")
            } else {
                CockpitRawResponse(200, statusJson)
            }
        }
        advanceUntilIdle()
        m.smoke("gemma3:latest")
        advanceUntilIdle()
        assertTrue("gemma3:latest" !in m.state.value.smokeTested)
        assertTrue(m.state.value.smokeFailed.containsKey("gemma3:latest"))
    }
}
