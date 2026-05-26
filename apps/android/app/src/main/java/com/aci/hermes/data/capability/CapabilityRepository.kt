package com.aci.hermes.data.capability

import com.aci.hermes.data.model.Capability
import com.aci.hermes.data.model.CapabilityCategory
import com.aci.hermes.data.model.CapabilityRoute

/**
 * Read-only access to the curated capability catalog plus search,
 * filter, and route-preview helpers.
 *
 * The repository is intentionally stateless — capabilities are
 * authored in [CapabilityCatalog], not stored on device. This keeps
 * the mobile surface in sync with whatever lanes the gateway side
 * actually exposes.
 */
class CapabilityRepository(
    private val source: List<Capability> = CapabilityCatalog.ALL,
) {

    fun all(): List<Capability> = source

    /**
     * Filter the catalog by free-text [query], optional [category],
     * and the user's "Advanced" toggle.
     *
     * - Empty query matches everything.
     * - When [includeAdvanced] is false, capabilities marked
     *   [Capability.isAdvanced] are excluded — that is the default
     *   "tip of the iceberg" presentation.
     * - Search is case-insensitive across name, summary, and tags.
     */
    fun search(
        query: String,
        category: CapabilityCategory? = null,
        includeAdvanced: Boolean = false,
    ): List<Capability> {
        val normalized = query.trim().lowercase()
        return source.asSequence()
            .filter { includeAdvanced || !it.isAdvanced }
            .filter { category == null || it.category == category }
            .filter { match(it, normalized) }
            .toList()
    }

    private fun match(capability: Capability, normalizedQuery: String): Boolean {
        if (normalizedQuery.isEmpty()) return true
        if (capability.name.lowercase().contains(normalizedQuery)) return true
        if (capability.summary.lowercase().contains(normalizedQuery)) return true
        if (capability.category.displayName.lowercase().contains(normalizedQuery)) return true
        return capability.tags.any { it.lowercase().contains(normalizedQuery) }
    }

    /**
     * Build a structured route preview for [capability]. The UI
     * renders this so the owner can see, before dispatching, which
     * surface and lane will see their words.
     */
    fun previewRoute(capability: Capability): RoutePreview {
        val route = capability.route
        val lines = mutableListOf<RoutePreviewLine>()
        lines += RoutePreviewLine("Surface", route.surface.displayName)
        lines += RoutePreviewLine("Lane", route.lane)
        lines += RoutePreviewLine(
            label = "Gateway",
            value = if (route.requiresGateway) "Required" else "Not required",
        )
        if (route.requiresOwnerAuth || capability.ownerGated) {
            lines += RoutePreviewLine("Owner gate", "Required")
        } else {
            lines += RoutePreviewLine("Owner gate", "Not required")
        }
        return RoutePreview(
            capabilityId = capability.id,
            ownerGated = route.requiresOwnerAuth || capability.ownerGated,
            requiresGateway = route.requiresGateway,
            note = route.notes,
            lines = lines,
            staged = buildStagedMessage(capability, route),
        )
    }

    /**
     * The exact text that will be sent over the chat / gateway
     * surface when the owner dispatches this capability. The route
     * header is part of the message so the gateway can audit-log
     * which lane the request came from.
     */
    private fun buildStagedMessage(capability: Capability, route: CapabilityRoute): String =
        buildString {
            append("[route] ")
            append(route.surface.name.lowercase())
            append(" :: ")
            append(route.lane)
            append('\n')
            append(capability.examplePrompt)
        }
}

/** Snapshot of the route preview, suitable for rendering and tests. */
data class RoutePreview(
    val capabilityId: String,
    val ownerGated: Boolean,
    val requiresGateway: Boolean,
    val note: String?,
    val lines: List<RoutePreviewLine>,
    val staged: String,
)

data class RoutePreviewLine(val label: String, val value: String)
