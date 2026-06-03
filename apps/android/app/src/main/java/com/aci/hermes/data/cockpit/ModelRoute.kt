package com.aci.hermes.data.cockpit

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Kotlin mirror of the evidence-backed model-routing API
 * (`GET /v1/cockpit/model-routes` and `POST /v1/cockpit/model-routes/override`,
 * backed by `hermes_cli/jarvis_prime/task_router.py`).
 *
 * One decision per mobile-first task class: the chosen model, its route tier,
 * the fallback chain, a human-readable `why`, and the scorecard evidence
 * behind it. Nothing here makes network calls or carries secrets — the live
 * [HermesCockpitClient] performs the transport; the server never accepts or
 * returns API keys.
 */
@Serializable
data class ModelRouteEvidence(
    val model: String,
    val score: Double = 0.0,
    val samples: Int = 0,
)

@Serializable
data class ModelRouteDecision(
    @SerialName("task_class") val taskClass: String,
    val chosen: String? = null,
    @SerialName("route_tier") val routeTier: String? = null,
    @SerialName("risk_class") val riskClass: String = "RC1",
    @SerialName("fallback_chain") val fallbackChain: List<String> = emptyList(),
    val why: String = "",
    val evidence: List<ModelRouteEvidence> = emptyList(),
    @SerialName("local_first") val localFirst: Boolean = false,
    @SerialName("paid_allowed") val paidAllowed: Boolean = false,
    @SerialName("paid_enabled") val paidEnabled: Boolean = false,
    @SerialName("owner_override") val ownerOverride: String? = null,
) {
    /** True when the owner has pinned this task class to a specific model. */
    val isOverridden: Boolean get() = ownerOverride != null
}

@Serializable
data class ModelRouteOverrides(
    @SerialName("task_overrides") val taskOverrides: Map<String, String> = emptyMap(),
    @SerialName("paid_enabled") val paidEnabled: Boolean? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class ModelRouteList(
    val routes: List<ModelRouteDecision> = emptyList(),
    @SerialName("task_classes") val taskClasses: List<String> = emptyList(),
    @SerialName("paid_enabled") val paidEnabled: Boolean = false,
    val overrides: ModelRouteOverrides = ModelRouteOverrides(),
    @SerialName("generated_at") val generatedAt: String? = null,
    // Honest-empty contract: a degraded server returns an error string here.
    val error: String? = null,
)

/**
 * Body for `POST /v1/cockpit/model-routes/override`.
 *
 * Pin a task to a model ([taskClass] + [model]; a null/blank [model] clears
 * it) and/or flip paid routing ([paidEnabled]) — flipping paid is a
 * money-spend gate that REQUIRES the exact owner [authorization] phrase.
 */
@Serializable
data class ModelRouteOverrideRequest(
    @SerialName("task_class") val taskClass: String? = null,
    val model: String? = null,
    @SerialName("paid_enabled") val paidEnabled: Boolean? = null,
    val authorization: String? = null,
)

@Serializable
data class ModelRouteOverrideResponse(
    val ok: Boolean = false,
    val overrides: ModelRouteOverrides = ModelRouteOverrides(),
)
