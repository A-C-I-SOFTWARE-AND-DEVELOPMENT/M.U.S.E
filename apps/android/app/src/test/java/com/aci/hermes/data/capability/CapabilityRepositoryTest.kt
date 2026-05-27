package com.aci.hermes.data.capability

import com.aci.hermes.data.model.Capability
import com.aci.hermes.data.model.CapabilityCategory
import com.aci.hermes.data.model.CapabilityRoute
import com.aci.hermes.data.model.RouteSurface
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Search, filter, owner-gate and route-preview behavior for the
 * repository. These tests double as the safe-invocation contract:
 * a route preview MUST exist for every capability, and an
 * owner-gated card MUST surface the gate to the UI.
 */
class CapabilityRepositoryTest {

    private val sample = listOf(
        cap("cap.alpha", "Alpha", CapabilityCategory.BUILD, tags = listOf("foo", "bar")),
        cap("cap.beta", "Beta", CapabilityCategory.REVIEW, tags = listOf("baz")),
        cap("cap.gamma", "Gamma", CapabilityCategory.RESEARCH, isAdvanced = true),
        cap(
            "cap.gated",
            "Gated",
            CapabilityCategory.SAFETY,
            ownerGated = true,
            requiresOwnerAuth = true,
        ),
    )

    private val repo = CapabilityRepository(source = sample)

    @Test
    fun empty_query_returns_curated_set() {
        val results = repo.search(query = "", includeAdvanced = false)
        assertEquals(3, results.size)  // alpha + beta + gated, no advanced
        assertFalse(results.any { it.isAdvanced })
    }

    @Test
    fun empty_query_with_advanced_returns_everything() {
        val results = repo.search(query = "", includeAdvanced = true)
        assertEquals(sample.size, results.size)
    }

    @Test
    fun search_is_case_insensitive_and_matches_name() {
        val results = repo.search(query = "BETA", includeAdvanced = false)
        assertEquals(1, results.size)
        assertEquals("cap.beta", results.first().id)
    }

    @Test
    fun search_matches_tags() {
        val results = repo.search(query = "foo", includeAdvanced = false)
        assertEquals(1, results.size)
        assertEquals("cap.alpha", results.first().id)
    }

    @Test
    fun search_filters_by_category() {
        val results = repo.search(
            query = "",
            category = CapabilityCategory.REVIEW,
            includeAdvanced = true,
        )
        assertEquals(1, results.size)
        assertEquals("cap.beta", results.first().id)
    }

    @Test
    fun search_with_no_matches_returns_empty() {
        val results = repo.search(query = "zzzzz-no-match", includeAdvanced = true)
        assertTrue(results.isEmpty())
    }

    @Test
    fun advanced_results_are_hidden_until_toggled() {
        val curated = repo.search(query = "", category = CapabilityCategory.RESEARCH, includeAdvanced = false)
        assertTrue("Curated default must hide advanced capabilities", curated.isEmpty())
        val advanced = repo.search(query = "", category = CapabilityCategory.RESEARCH, includeAdvanced = true)
        assertEquals(1, advanced.size)
        assertEquals("cap.gamma", advanced.first().id)
    }

    @Test
    fun route_preview_includes_required_lines() {
        val cap = sample.first { it.id == "cap.alpha" }
        val preview = repo.previewRoute(cap)
        val labels = preview.lines.map { it.label }
        assertTrue("Preview must list the surface", labels.contains("Surface"))
        assertTrue("Preview must list the lane", labels.contains("Lane"))
        assertTrue("Preview must list the gateway requirement", labels.contains("Gateway"))
        assertTrue("Preview must list the owner gate state", labels.contains("Owner gate"))
    }

    @Test
    fun route_preview_marks_owner_gate_when_capability_is_gated() {
        val cap = sample.first { it.id == "cap.gated" }
        val preview = repo.previewRoute(cap)
        assertTrue("Owner-gated capability must produce ownerGated preview", preview.ownerGated)
        val gateLine = preview.lines.firstOrNull { it.label == "Owner gate" }
        assertNotNull(gateLine)
        assertEquals("Required", gateLine!!.value)
    }

    @Test
    fun route_preview_does_not_mark_owner_gate_for_open_capabilities() {
        val cap = sample.first { it.id == "cap.alpha" }
        val preview = repo.previewRoute(cap)
        assertFalse(preview.ownerGated)
        val gateLine = preview.lines.firstOrNull { it.label == "Owner gate" }
        assertNotNull(gateLine)
        assertEquals("Not required", gateLine!!.value)
    }

    @Test
    fun staged_prompt_includes_route_header_and_example() {
        val cap = sample.first { it.id == "cap.alpha" }
        val preview = repo.previewRoute(cap)
        assertTrue(
            "Staged prompt must embed the route header for gateway audit-logging",
            preview.staged.startsWith("[route] chat ::"),
        )
        assertTrue(
            "Staged prompt must end with the example prompt body",
            preview.staged.trim().endsWith(cap.examplePrompt),
        )
    }

    @Test
    fun staged_prompt_never_invokes_a_tool_directly() {
        // Contract: the only output of "preview" is text staged for the
        // owner. It must never contain a directive that bypasses the
        // chat / gateway surface — no shell commands, no API calls.
        sample.forEach { cap ->
            val preview = repo.previewRoute(cap)
            assertFalse(
                "Staged prompt for ${cap.id} must not invoke shell directly",
                preview.staged.contains("\$(") || preview.staged.contains("`bash"),
            )
            assertFalse(
                "Staged prompt for ${cap.id} must not embed an outbound HTTP call",
                preview.staged.contains("curl -X") || preview.staged.contains("http://"),
            )
        }
    }

    @Test
    fun null_category_filter_matches_anything() {
        val results = repo.search(query = "", category = null, includeAdvanced = true)
        assertEquals(sample.size, results.size)
    }

    @Test
    fun category_fromIdOrNull_handles_unknown() {
        assertNull(CapabilityCategory.fromIdOrNull("NOT_A_REAL_CATEGORY"))
        assertNull(CapabilityCategory.fromIdOrNull(null))
        assertEquals(
            CapabilityCategory.BUILD,
            CapabilityCategory.fromIdOrNull("BUILD"),
        )
    }

    private fun cap(
        id: String,
        name: String,
        category: CapabilityCategory,
        ownerGated: Boolean = false,
        isAdvanced: Boolean = false,
        requiresOwnerAuth: Boolean = false,
        tags: List<String> = emptyList(),
    ): Capability = Capability(
        id = id,
        name = name,
        category = category,
        summary = "$name summary",
        examplePrompt = "JARVIS, run $name with: <input>.",
        route = CapabilityRoute(
            surface = RouteSurface.CHAT,
            lane = "jarvis-prime: $id",
            requiresGateway = true,
            requiresOwnerAuth = requiresOwnerAuth,
        ),
        ownerGated = ownerGated,
        isAdvanced = isAdvanced,
        tags = tags,
    )
}
