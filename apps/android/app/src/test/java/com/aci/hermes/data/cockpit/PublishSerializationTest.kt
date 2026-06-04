package com.aci.hermes.data.cockpit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure DTO round-trips for the publish + files-changed + templates shapes —
 * the contract pin between these Kotlin models and the JSON the gateway emits
 * (`gateway/cockpit/handlers.py`). No socket, no Android. Mirrors
 * [ModelRouteSerializationTest]: decode the exact server JSON, and prove the
 * request body encodes only the fields that were set.
 */
class PublishSerializationTest {

    private val json = CockpitHttp.json

    @Test
    fun `publish request encodes only the fields set`() {
        // explicitNulls=false: absent optionals are omitted, not sent as null.
        val staged = json.encodeToString(PublishRequest.serializer(), PublishRequest(title = "do x"))
        assertTrue(staged.contains("\"title\":\"do x\""))
        assertFalse(staged.contains("authorization"))
        assertFalse(staged.contains("draft"))

        val authorized = json.encodeToString(
            PublishRequest.serializer(),
            PublishRequest(authorization = "Yes, with authorization.", draft = true),
        )
        assertTrue(authorized.contains("\"authorization\":\"Yes, with authorization.\""))
        assertTrue(authorized.contains("\"draft\":true"))
    }

    @Test
    fun `publish result decodes the approval_required shape`() {
        val r = json.decodeFromString(
            PublishResult.serializer(),
            """{"status":"approval_required",
                "preview":{"remote":"origin","branch":"feat/x","base":"main","commits":[],
                           "default_title":"do x","default_body":null,"existing_pr_url":null},
                "authorization_required":true,
                "authorization_hint":"send authorization exactly: 'Yes, with authorization.'"}""".trimIndent(),
        )
        assertTrue(r.isApprovalRequired)
        assertFalse(r.isPublished)
        assertEquals("feat/x", r.preview?.branch)
        assertNull(r.prUrl)
        assertEquals(
            "send authorization exactly: 'Yes, with authorization.'",
            r.authorizationHint,
        )
    }

    @Test
    fun `publish result decodes the published PR shape`() {
        val r = json.decodeFromString(
            PublishResult.serializer(),
            """{"pr_url":"https://github.com/o/r/pull/7","pr_number":7,
                "branch":"feat/x","remote":"origin","state":"open","is_draft":false}""".trimIndent(),
        )
        assertTrue(r.isPublished)
        assertFalse(r.isApprovalRequired)
        assertEquals(7, r.prNumber)
        assertEquals("open", r.state)
        assertEquals(false, r.isDraft)
        assertNull(r.status)
    }

    @Test
    fun `publish result decodes the error shape carrying an existing pr url`() {
        // 409 pr_already_exists is folded with a pr_url; the error field wins
        // over isPublished so the UI never treats it as a fresh PR.
        val r = json.decodeFromString(
            PublishResult.serializer(),
            """{"error":"pr_already_exists","pr_url":"https://github.com/o/r/pull/3"}""",
        )
        assertEquals("pr_already_exists", r.error)
        assertEquals("https://github.com/o/r/pull/3", r.prUrl)
        assertFalse(r.isPublished)
        assertFalse(r.isApprovalRequired)
    }

    @Test
    fun `files changed snapshot decodes numstat entries`() {
        val snap = json.decodeFromString(
            FilesChangedSnapshot.serializer(),
            """{"files":[{"path":"a.kt","additions":3,"deletions":1}]}""",
        )
        assertEquals(1, snap.files.size)
        assertEquals("a.kt", snap.files[0].path)
        assertEquals(3, snap.files[0].additions)
        assertEquals(1, snap.files[0].deletions)
    }

    @Test
    fun `files changed snapshot tolerates a missing files key`() {
        // Honest-empty: an older/degraded payload without the key still decodes.
        val snap = json.decodeFromString(FilesChangedSnapshot.serializer(), """{}""")
        assertTrue(snap.files.isEmpty())
    }

    @Test
    fun `template list decodes entries and tolerates empty`() {
        val list = json.decodeFromString(
            TemplateList.serializer(),
            """{"templates":[{"id":"bug","title":"Bug fix","body":"Fix: "}]}""",
        )
        assertEquals(1, list.templates.size)
        assertEquals("bug", list.templates[0].id)
        assertEquals("Bug fix", list.templates[0].title)

        val empty = json.decodeFromString(TemplateList.serializer(), """{"templates":[]}""")
        assertTrue(empty.templates.isEmpty())
    }
}
