package com.aci.hermes.data.coding

import com.aci.hermes.data.cockpit.CodingPacket
import com.aci.hermes.data.orchestrator.PromptBuilder
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CodingPromptBuilderTest {

    @Test
    fun `prompt with no packet still carries mission and safety block`() {
        val out = CodingPromptBuilder.build("Add retry to the upload client", packet = null)
        assertTrue(out.contains("## Mission"))
        assertTrue(out.contains("Add retry to the upload client"))
        // The invariant safety block must always be present, packet or not.
        assertTrue(out.contains("## Safety requirements"))
        assertTrue(out.contains(PromptBuilder.SAFETY_BLOCK.lineSequence().first()))
    }

    @Test
    fun `packet drives allowed files, acceptance, rollback, and owner gates`() {
        val packet = CodingPacket(
            mission = "Implement backoff",
            riskClass = "RC2",
            allowedFiles = listOf("src/net/Upload.kt"),
            forbiddenFiles = listOf("**/.env"),
            acceptanceCriteria = listOf("tests pass"),
            rollbackPlan = listOf("revert branch"),
            ownerGates = listOf("production_deploy"),
            primaryWorker = "claude-code",
        )
        val out = CodingPromptBuilder.build("ignored when packet has mission", packet)
        assertTrue(out.contains("Implement backoff"))
        assertTrue(out.contains("src/net/Upload.kt"))
        assertTrue(out.contains("## Do NOT touch"))
        assertTrue(out.contains("**/.env"))
        assertTrue(out.contains("## Acceptance criteria"))
        assertTrue(out.contains("## Rollback plan"))
        assertTrue(out.contains("## Owner-gated actions"))
        assertTrue(out.contains("production_deploy"))
    }

    @Test
    fun `never embeds the owner authorization phrase`() {
        val packet = CodingPacket(mission = "x", ownerGates = listOf("force_push"))
        val out = CodingPromptBuilder.build("x", packet)
        assertFalse(out.contains("Yes, with authorization."))
    }
}
