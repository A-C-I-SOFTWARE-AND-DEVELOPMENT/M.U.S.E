package com.aci.hermes.ui.components

import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.data.model.TaskStatus
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The chip tone mappings are pure (no Compose), so the semantic contract —
 * "complete reads success, needs-revision reads danger, risk escalates to
 * danger" — is verified without rendering. The composable `color()` resolver
 * is intentionally not exercised here.
 */
class StatusChipMappingTest {

    @Test
    fun `every task status maps to a tone`() {
        // Totality: a missing branch would not compile, but this guards a
        // future enum value being added without a tone.
        TaskStatus.entries.forEach { it.chipTone() }
    }

    @Test
    fun `task lifecycle tones carry the right valence`() {
        assertEquals(ChipTone.NEUTRAL, TaskStatus.DRAFT.chipTone())
        assertEquals(ChipTone.ACTIVE, TaskStatus.HANDED_TO_CODEX.chipTone())
        assertEquals(ChipTone.ACTIVE, TaskStatus.HANDED_TO_CLAUDE.chipTone())
        assertEquals(ChipTone.DANGER, TaskStatus.NEEDS_REVISION.chipTone())
        assertEquals(ChipTone.SUCCESS, TaskStatus.COMPLETE.chipTone())
    }

    @Test
    fun `every risk tier maps to a tone`() {
        ApprovalRiskTier.entries.forEach { it.chipTone() }
    }

    @Test
    fun `risk escalates from success to danger`() {
        assertEquals(ChipTone.SUCCESS, ApprovalRiskTier.SAFE.chipTone())
        assertEquals(ChipTone.SUCCESS, ApprovalRiskTier.LOW.chipTone())
        assertEquals(ChipTone.WARN, ApprovalRiskTier.RISKY.chipTone())
        assertEquals(ChipTone.DANGER, ApprovalRiskTier.SERIOUS.chipTone())
        assertEquals(ChipTone.DANGER, ApprovalRiskTier.CRITICAL.chipTone())
        assertEquals(ChipTone.DANGER, ApprovalRiskTier.FORBIDDEN.chipTone())
    }
}
