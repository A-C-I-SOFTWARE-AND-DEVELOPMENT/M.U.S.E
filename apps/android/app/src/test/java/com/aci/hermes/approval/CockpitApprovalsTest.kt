package com.aci.hermes.approval

import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus
import com.aci.hermes.approval.state.ApprovalsSync
import com.aci.hermes.approval.state.CockpitApprovalsRepository
import com.aci.hermes.approval.state.toCard
import com.aci.hermes.data.cockpit.CockpitApprovalCard
import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitApprovalsTest {

    // ── mapping ──────────────────────────────────────────────────────────

    @Test
    fun `wire card maps to domain ApprovalCard`() {
        val card = CockpitApprovalCard(
            id = "p1",
            title = "Self-update: skill_update (SKILL.md)",
            summary = "improve the foo skill",
            requester = "jarvis",
            tier = "SERIOUS",
            status = "PENDING",
            createdAt = "2026-05-30T12:00:00Z",
            expiresAt = null,
            proposedAction = "skill_update skills/foo/SKILL.md",
        ).toCard()
        assertEquals("p1", card.id)
        assertEquals(ApprovalRiskTier.SERIOUS, card.tier)
        assertEquals(ApprovalStatus.PENDING, card.status)
        assertEquals("jarvis", card.requester)
        assertTrue(card.createdAtMillis > 0L)
        // null expires_at → never expires
        assertEquals(Long.MAX_VALUE, card.expiresAtMillis)
        assertFalse(card.isExpired(System.currentTimeMillis()))
    }

    @Test
    fun `unknown tier and status fall back honestly`() {
        val card = CockpitApprovalCard(id = "x", tier = "???", status = "???").toCard()
        assertEquals(ApprovalRiskTier.RISKY, card.tier)
        assertEquals(ApprovalStatus.PENDING, card.status)
    }

    // ── repository ───────────────────────────────────────────────────────

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
        {"approvals":[{"id":"p1","title":"Self-update","summary":"s","requester":"jarvis",
          "tier":"RISKY","status":"PENDING","created_at":"2026-05-30T12:00:00Z",
          "expires_at":null,"proposed_action":"do","edited_note":null}]}
    """.trimIndent()

    @Test
    fun `refresh loads real pending cards when paired`() = runTest {
        val repo = CockpitApprovalsRepository(client { CockpitRawResponse(200, listJson) })
        repo.refresh()
        assertEquals(1, repo.cards.value.size)
        assertEquals("p1", repo.cards.value[0].id)
        assertTrue(repo.sync.value is ApprovalsSync.Loaded)
    }

    @Test
    fun `unpaired yields empty and NotPaired, no fabricated cards`() = runTest {
        val repo = CockpitApprovalsRepository(client(token = null) { error("must not hit the wire") })
        repo.refresh()
        assertEquals(ApprovalsSync.NotPaired, repo.sync.value)
        assertTrue(repo.cards.value.isEmpty())
    }

    @Test
    fun `approve submits the owner phrase (gate never bypassed)`() = runTest {
        var approveBody: String? = null
        val repo = CockpitApprovalsRepository(
            client { req ->
                if (req.method == "POST") {
                    approveBody = req.body
                    CockpitRawResponse(200, """{"id":"p1","status":"approve"}""")
                } else {
                    CockpitRawResponse(200, listJson)
                }
            },
        )
        val res = repo.approve("p1")
        assertTrue(res is CockpitResult.Success)
        assertTrue(approveBody!!.contains("approve"))
        assertTrue(approveBody!!.contains("Yes, with authorization."))
    }

    @Test
    fun `reject does not send the owner phrase`() = runTest {
        var rejectBody: String? = null
        val repo = CockpitApprovalsRepository(
            client { req ->
                if (req.method == "POST") {
                    rejectBody = req.body
                    CockpitRawResponse(200, """{"id":"p1","status":"reject"}""")
                } else {
                    CockpitRawResponse(200, listJson)
                }
            },
        )
        repo.reject("p1", notes = "not now")
        assertTrue(rejectBody!!.contains("reject"))
        assertFalse(rejectBody!!.contains("Yes, with authorization."))
    }
}
