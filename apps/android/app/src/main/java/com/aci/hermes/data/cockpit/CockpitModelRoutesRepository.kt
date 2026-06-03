package com.aci.hermes.data.cockpit

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Sync state of the model-routes view against the cockpit gateway. */
sealed interface ModelRoutesSync {
    data object Idle : ModelRoutesSync
    data object Loading : ModelRoutesSync
    /** No gateway paired — nothing real to show (no fabricated routes). */
    data object NotPaired : ModelRoutesSync
    data class Loaded(val count: Int) : ModelRoutesSync
    data class Error(val message: String) : ModelRoutesSync
}

/**
 * Repository over the evidence-backed model-routing API
 * (`/v1/cockpit/model-routes`), backed by the real `task_router` through
 * [HermesCockpitClient]. There is **no mock seed**: an unpaired or unreachable
 * gateway yields an empty list + an honest [sync] state, never fabricated
 * routes. Overrides flow back through [setOverride] / [setPaidEnabled] and a
 * refresh, so the UI always reflects the server's truth.
 */
class CockpitModelRoutesRepository(
    private val client: HermesCockpitClient,
) {
    private val _routes = MutableStateFlow(ModelRouteList())
    val routes: StateFlow<ModelRouteList> = _routes.asStateFlow()

    private val _sync = MutableStateFlow<ModelRoutesSync>(ModelRoutesSync.Idle)
    val sync: StateFlow<ModelRoutesSync> = _sync.asStateFlow()

    suspend fun refresh() {
        if (!client.isPaired()) {
            _routes.value = ModelRouteList()
            _sync.value = ModelRoutesSync.NotPaired
            return
        }
        _sync.value = ModelRoutesSync.Loading
        when (val res = client.modelRoutes()) {
            is CockpitResult.Success -> {
                _routes.value = res.value
                _sync.value = ModelRoutesSync.Loaded(res.value.routes.size)
            }
            is CockpitResult.Failure ->
                _sync.value = ModelRoutesSync.Error(
                    "Gateway error ${res.httpStatus}: ${res.error.message}",
                )
            is CockpitResult.Unreachable ->
                _sync.value = ModelRoutesSync.Error(res.message)
        }
    }

    /** Pin (or, with a null/blank [model], clear) a task class's model. */
    suspend fun setOverride(
        taskClass: String,
        model: String?,
    ): CockpitResult<ModelRouteOverrideResponse> {
        val res = client.modelRouteOverride(
            ModelRouteOverrideRequest(taskClass = taskClass, model = model?.ifBlank { null }),
        )
        if (res is CockpitResult.Success) refresh()
        return res
    }

    /**
     * Flip paid routing. [authorization] must be the exact owner phrase or the
     * gateway refuses with 403 — this is a money-spend gate, kept owner-gated.
     */
    suspend fun setPaidEnabled(
        enabled: Boolean,
        authorization: String,
    ): CockpitResult<ModelRouteOverrideResponse> {
        val res = client.modelRouteOverride(
            ModelRouteOverrideRequest(paidEnabled = enabled, authorization = authorization),
        )
        if (res is CockpitResult.Success) refresh()
        return res
    }
}
