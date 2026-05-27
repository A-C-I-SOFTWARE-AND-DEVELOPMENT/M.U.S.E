package com.aci.hermes.data.capability

import com.aci.hermes.data.model.CapabilityCategory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The catalog is the source of truth for what the mobile UI exposes.
 * These tests guard the curated-by-default contract so a regression
 * doesn't dump 200+ agents into the picker.
 */
class CapabilityCatalogTest {

    @Test
    fun every_category_has_at_least_one_capability() {
        val coverage = CapabilityCategory.values().associateWith { cat ->
            CapabilityCatalog.byCategory(cat)
        }
        val missing = coverage.filterValues { it.isEmpty() }.keys
        assertTrue("Missing capabilities for categories: $missing", missing.isEmpty())
    }

    @Test
    fun catalog_ids_are_unique() {
        val ids = CapabilityCatalog.ALL.map { it.id }
        assertEquals("Duplicate capability ids: ${ids - ids.distinct().toSet()}", ids.size, ids.distinct().size)
    }

    @Test
    fun curated_default_excludes_advanced() {
        val repo = CapabilityRepository()
        val curated = repo.search(query = "", includeAdvanced = false)
        val advanced = repo.search(query = "", includeAdvanced = true)
        assertTrue(curated.isNotEmpty())
        assertTrue(
            "Advanced toggle must expand visible capability count",
            advanced.size > curated.size,
        )
        assertFalse(
            "Curated default must not leak any advanced capability",
            curated.any { it.isAdvanced },
        )
    }

    @Test
    fun owner_gated_capabilities_are_marked() {
        val gated = CapabilityCatalog.ALL.filter { it.ownerGated }
        assertTrue("At least one capability must be owner-gated", gated.isNotEmpty())
        // Every owner-gated capability MUST also have requiresOwnerAuth on its route.
        // We do not allow a card to be marked owner-gated while routing as if it isn't.
        gated.forEach { cap ->
            assertTrue(
                "Owner-gated capability ${cap.id} must require owner auth in its route",
                cap.route.requiresOwnerAuth,
            )
        }
    }

    @Test
    fun every_capability_has_an_example_prompt() {
        CapabilityCatalog.ALL.forEach { cap ->
            assertNotNull(cap.examplePrompt)
            assertTrue(
                "Capability ${cap.id} must ship with an example prompt",
                cap.examplePrompt.isNotBlank(),
            )
        }
    }

    @Test
    fun every_capability_has_a_lane() {
        CapabilityCatalog.ALL.forEach { cap ->
            assertTrue(
                "Capability ${cap.id} must declare a routing lane",
                cap.route.lane.isNotBlank(),
            )
        }
    }

    @Test
    fun by_id_round_trips() {
        CapabilityCatalog.ALL.forEach { cap ->
            assertEquals(cap, CapabilityCatalog.byId(cap.id))
        }
    }
}
