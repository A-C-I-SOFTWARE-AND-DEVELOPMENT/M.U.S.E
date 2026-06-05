package com.aci.hermes.ui.screens.modelroute

import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitModelRoutesRepository
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.cockpit.ModelRoutesSync
import com.aci.hermes.testutil.MainDispatcherRule
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ModelRouteViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(StandardTestDispatcher())

    private val routesJson = """
        {"routes":[
          {"task_class":"mobile_chat","chosen":"qwen3:8b","route_tier":"local_oss",
           "risk_class":"RC1","fallback_chain":["qwen3:8b"],"why":"local-first",
           "evidence":[],"local_first":true,"paid_allowed":false,"paid_enabled":false,
           "owner_override":null}],
         "task_classes":["mobile_chat"],"paid_enabled":false,
         "overrides":{"task_overrides":{},"paid_enabled":null,"updated_at":null}}
    """.trimIndent()

    private fun repo(
        token: String? = "tok",
        exec: (CockpitRequest) -> CockpitRawResponse,
    ): CockpitModelRoutesRepository {
        val client = HermesCockpitClient(
            endpointProvider = { "http://127.0.0.1:8765" },
            tokenProvider = { token },
            executor = CockpitHttpExecutor { exec(it) },
            ioDispatcher = Dispatchers.Unconfined,
        )
        return CockpitModelRoutesRepository(client)
    }

    @Test
    fun `loads routes on init`() = runTest {
        val vm = mainDispatcherRule.register(ModelRouteViewModel(repo { CockpitRawResponse(200, routesJson) }))
        advanceUntilIdle()
        val s = vm.state.value
        assertEquals(1, s.routes.size)
        assertEquals("qwen3:8b", s.routes[0].chosen)
        assertTrue(s.sync is ModelRoutesSync.Loaded)
    }

    @Test
    fun `unpaired shows NotPaired and no fabricated routes`() = runTest {
        val vm = mainDispatcherRule.register(ModelRouteViewModel(repo(token = null) { error("must not hit wire") }))
        advanceUntilIdle()
        assertEquals(ModelRoutesSync.NotPaired, vm.state.value.sync)
        assertTrue(vm.state.value.routes.isEmpty())
    }

    @Test
    fun `override posts then reflects refreshed routes`() = runTest {
        var posted = false
        val vm = mainDispatcherRule.register(ModelRouteViewModel(
            repo { req ->
                if (req.method == "POST") {
                    posted = true
                    CockpitRawResponse(200, """{"ok":true,"overrides":{"task_overrides":{"mobile_chat":"pinned"}}}""")
                } else {
                    CockpitRawResponse(200, routesJson)
                }
            },
        ))
        advanceUntilIdle()
        vm.setOverride("mobile_chat", "pinned")
        advanceUntilIdle()
        assertTrue(posted)
        assertEquals("Override updated", vm.state.value.message)
    }

    @Test
    fun `paid toggle is rejected without owner authorization`() = runTest {
        val vm = mainDispatcherRule.register(ModelRouteViewModel(
            repo { req ->
                if (req.method == "POST") {
                    CockpitRawResponse(403, """{"error":"owner authorization required"}""")
                } else {
                    CockpitRawResponse(200, routesJson)
                }
            },
        ))
        advanceUntilIdle()
        vm.setPaidEnabled(enabled = true, authorization = "wrong phrase")
        advanceUntilIdle()
        assertTrue(
            "403 must surface as an authorization message, paid routing unchanged",
            vm.state.value.message!!.contains("authorization", ignoreCase = true),
        )
    }

    @Test
    fun `owner authorization phrase is the exact server gate`() {
        assertEquals("Yes, with authorization.", ModelRouteViewModel.OWNER_AUTHORIZATION_PHRASE)
    }
}
