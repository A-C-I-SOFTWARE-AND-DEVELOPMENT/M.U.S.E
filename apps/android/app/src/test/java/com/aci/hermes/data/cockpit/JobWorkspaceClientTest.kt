package com.aci.hermes.data.cockpit

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Request/response mapping for the job-workspace browse + publish + templates
 * routes (contract §6/§7/§8/§3). Drives the real [HermesCockpitClient] over an
 * injected executor so the wire contract — route, method, and the exact decoded
 * DTO shape (including null/empty and the publish two-shape response) — is
 * exercised without a socket, on a plain JVM. Mirrors [JobControlsClientTest].
 */
class JobWorkspaceClientTest {

    private val seen = mutableListOf<Pair<String, String>>() // method to path-suffix
    private val json = CockpitHttp.json

    private fun client(exec: (CockpitRequest) -> CockpitRawResponse) = HermesCockpitClient(
        endpointProvider = { "http://127.0.0.1:8765" },
        tokenProvider = { "tok" },
        executor = CockpitHttpExecutor { req ->
            seen += req.method to req.url.substringAfter("/v1/cockpit")
            exec(req)
        },
        ioDispatcher = Dispatchers.Unconfined,
    )

    // ─── files-changed ────────────────────────────────────────────────────

    @Test
    fun `files-changed hits the route and decodes numstat files`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"files":[{"path":"a.kt","additions":3,"deletions":1},
                            {"path":"b.kt","additions":0,"deletions":7}]}""".trimIndent(),
            )
        }
        val res = c.jobFilesChanged("job_1")
        assertTrue(res is CockpitResult.Success)
        val files = (res as CockpitResult.Success).value.files
        assertEquals(2, files.size)
        assertEquals("a.kt", files[0].path)
        assertEquals(3, files[0].additions)
        assertEquals(7, files[1].deletions)
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/files-changed" })
    }

    @Test
    fun `files-changed tolerates an honest-empty workspace`() = runTest {
        val c = client { CockpitRawResponse(200, """{"files":[]}""") }
        val res = c.jobFilesChanged("job_1")
        assertTrue(res is CockpitResult.Success)
        assertTrue((res as CockpitResult.Success).value.files.isEmpty())
    }

    // ─── validation (GET — the read companion to POST validate) ─────────────

    @Test
    fun `validation GET decodes gates and policy`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"gates":[{"id":"pytest","name":"pytest","status":"PASS",
                             "summary":"all green","log_excerpt":"...","override_allowed":true}],
                   "policy":{"all_must_pass":true,"override_requires_note":true}}""".trimIndent(),
            )
        }
        val res = c.jobValidation("job_1")
        assertTrue(res is CockpitResult.Success)
        val snap = (res as CockpitResult.Success).value
        assertEquals(1, snap.gates.size)
        assertEquals("pytest", snap.gates[0].id)
        assertEquals("PASS", snap.gates[0].status)
        assertTrue(snap.gates[0].overrideAllowed)
        assertTrue(snap.policy.allMustPass)
        assertTrue(snap.policy.overrideRequiresNote)
        // GET, not the POST /validate route.
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/validation" })
    }

    @Test
    fun `validation GET tolerates honest-empty gates with optional fields absent`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"gates":[{"id":"g","name":"g","status":"PENDING"}],
                   "policy":{"all_must_pass":true,"override_requires_note":false}}""".trimIndent(),
            )
        }
        val res = c.jobValidation("job_1")
        assertTrue(res is CockpitResult.Success)
        val gate = (res as CockpitResult.Success).value.gates.single()
        assertNull(gate.summary)
        assertNull(gate.logExcerpt)
        assertFalse(gate.overrideAllowed) // defaulted false when absent
        // The override-only fields default when the gate didn't come from an override.
        assertFalse(gate.overrideApplied)
        assertNull(gate.overrideNote)
    }

    // ─── revalidate (POST — re-runs the gates) ──────────────────────────────

    @Test
    fun `revalidate POSTs an empty body and decodes the fresh snapshot`() = runTest {
        var body: String? = null
        val c = client { req ->
            body = req.body
            CockpitRawResponse(
                200,
                """{"gates":[{"id":"pytest","name":"pytest","status":"PASS"}],
                   "policy":{"all_must_pass":true,"override_requires_note":true}}""".trimIndent(),
            )
        }
        val res = c.jobRevalidate("job_1")
        assertTrue(res is CockpitResult.Success)
        val snap = (res as CockpitResult.Success).value
        assertEquals("PASS", snap.gates.single().status)
        assertTrue(seen.any { it == "POST" to "/jobs/job_1/revalidate" })
        assertEquals("{}", body)
    }

    // ─── override (POST — owner gate override) ───────────────────────────────

    @Test
    fun `override POSTs gate_ids and note and decodes the applied override`() = runTest {
        var body: String? = null
        val c = client { req ->
            body = req.body
            CockpitRawResponse(
                200,
                """{"gates":[{"id":"pytest","name":"pytest","status":"FAIL",
                             "override_allowed":true,"override_applied":true,
                             "override_note":"flaky on CI"}],
                   "policy":{"all_must_pass":true,"override_requires_note":true}}""".trimIndent(),
            )
        }
        val res = c.jobOverride("job_1", listOf("pytest"), "flaky on CI")
        assertTrue(res is CockpitResult.Success)
        val gate = (res as CockpitResult.Success).value.gates.single()
        assertTrue(gate.overrideApplied)
        assertEquals("flaky on CI", gate.overrideNote)
        assertTrue(seen.any { it == "POST" to "/jobs/job_1/override" })
        // Snake-case keys carried in the request body.
        assertTrue(body!!.contains("\"gate_ids\":[\"pytest\"]"))
        assertTrue(body!!.contains("\"note\":\"flaky on CI\""))
    }

    // ─── tree ──────────────────────────────────────────────────────────────

    @Test
    fun `tree without a path lists the workspace root`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"path":".","entries":[
                     {"name":"src","kind":"dir","size":null,"mtime":"2026-06-01T00:00:00Z"},
                     {"name":"a.kt","kind":"file","size":12,"mtime":"2026-06-01T00:00:00Z"}]}""".trimIndent(),
            )
        }
        val res = c.jobTree("job_1")
        assertTrue(res is CockpitResult.Success)
        val listing = (res as CockpitResult.Success).value
        assertEquals(".", listing.path)
        assertEquals(2, listing.entries.size)
        assertEquals("dir", listing.entries[0].kind)
        assertNull(listing.entries[0].size) // dirs carry a null size
        assertEquals(12L, listing.entries[1].size)
        // No ?path= query when none is passed.
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/tree" })
    }

    @Test
    fun `tree with a path encodes it as a query parameter`() = runTest {
        val c = client { CockpitRawResponse(200, """{"path":"src/main","entries":[]}""") }
        val res = c.jobTree("job_1", "src/main")
        assertTrue(res is CockpitResult.Success)
        assertEquals("src/main", (res as CockpitResult.Success).value.path)
        // URLEncoder encodes the slash as %2F.
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/tree?path=src%2Fmain" })
    }

    // ─── file ──────────────────────────────────────────────────────────────

    @Test
    fun `file decodes a readable preview`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"path":"a.kt","size":12,"truncated":false,"content":"hello","encoding":"utf-8"}""",
            )
        }
        val res = c.jobFile("job_1", "a.kt")
        assertTrue(res is CockpitResult.Success)
        val snap = (res as CockpitResult.Success).value
        assertEquals("a.kt", snap.path)
        assertEquals(12L, snap.size)
        assertFalse(snap.truncated)
        assertEquals("hello", snap.content)
        assertEquals("utf-8", snap.encoding)
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/file?path=a.kt" })
    }

    @Test
    fun `file decodes a truncated binary preview with null content`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"path":"big.bin","size":2000000,"truncated":true,"content":null,"encoding":"utf-8"}""",
            )
        }
        val res = c.jobFile("job_1", "big.bin")
        assertTrue(res is CockpitResult.Success)
        val snap = (res as CockpitResult.Success).value
        assertTrue(snap.truncated)
        assertNull(snap.content)
        assertEquals(2_000_000L, snap.size)
    }

    // ─── publish/preview ────────────────────────────────────────────────────

    @Test
    fun `publish preview decodes commits and defaults`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"remote":"origin","branch":"feat/x","base":"main",
                    "commits":[{"sha":"abc123","subject":"do x"}],
                    "default_title":"do x","default_body":"## Summary\n",
                    "existing_pr_url":null}""".trimIndent(),
            )
        }
        val res = c.jobPublishPreview("job_1")
        assertTrue(res is CockpitResult.Success)
        val p = (res as CockpitResult.Success).value
        assertEquals("origin", p.remote)
        assertEquals("feat/x", p.branch)
        assertEquals("main", p.base)
        assertEquals(1, p.commits.size)
        assertEquals("abc123", p.commits[0].sha)
        assertEquals("do x", p.defaultTitle)
        assertNull(p.existingPrUrl)
        assertTrue(seen.any { it == "GET" to "/jobs/job_1/publish/preview" })
    }

    @Test
    fun `publish preview tolerates all-null fields without a workspace`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"remote":null,"branch":null,"base":null,"commits":[],
                    "default_title":null,"default_body":null,"existing_pr_url":null}""".trimIndent(),
            )
        }
        val res = c.jobPublishPreview("job_1")
        assertTrue(res is CockpitResult.Success)
        val p = (res as CockpitResult.Success).value
        assertNull(p.remote)
        assertNull(p.branch)
        assertNull(p.base)
        assertNull(p.defaultTitle)
        assertNull(p.defaultBody)
        assertTrue(p.commits.isEmpty())
    }

    // ─── publish (POST — the two-shape response) ────────────────────────────

    @Test
    fun `publish without the owner phrase decodes the approval_required shape`() = runTest {
        var body: String? = null
        val c = client { req ->
            body = req.body
            CockpitRawResponse(
                200,
                """{"status":"approval_required",
                    "preview":{"remote":"origin","branch":"feat/x","base":"main","commits":[],
                               "default_title":"do x","default_body":null,"existing_pr_url":null},
                    "authorization_required":true,
                    "authorization_hint":"send authorization exactly: 'Yes, with authorization.'"}""".trimIndent(),
            )
        }
        val res = c.jobPublish("job_1", PublishRequest(title = "do x"))
        assertTrue(res is CockpitResult.Success)
        val r = (res as CockpitResult.Success).value
        assertEquals("approval_required", r.status)
        assertTrue(r.authorizationRequired)
        assertTrue(r.isApprovalRequired)
        assertFalse(r.isPublished)
        assertEquals("feat/x", r.preview?.branch)
        assertNull(r.prUrl)
        assertTrue(seen.any { it == "POST" to "/jobs/job_1/publish" })
        // The optional title is carried in the request body; absent fields are omitted.
        assertTrue(body!!.contains("\"title\":\"do x\""))
        assertFalse(body!!.contains("\"authorization\""))
    }

    @Test
    fun `publish with the owner phrase decodes the published PR shape`() = runTest {
        var body: String? = null
        val c = client { req ->
            body = req.body
            CockpitRawResponse(
                200,
                """{"pr_url":"https://github.com/o/r/pull/7","pr_number":7,
                    "branch":"feat/x","remote":"origin","state":"open","is_draft":true}""".trimIndent(),
            )
        }
        val res = c.jobPublish(
            "job_1",
            PublishRequest(authorization = "Yes, with authorization.", draft = true),
        )
        assertTrue(res is CockpitResult.Success)
        val r = (res as CockpitResult.Success).value
        assertEquals("https://github.com/o/r/pull/7", r.prUrl)
        assertEquals(7, r.prNumber)
        assertEquals("open", r.state)
        assertEquals(true, r.isDraft)
        assertTrue(r.isPublished)
        assertFalse(r.isApprovalRequired)
        assertTrue(body!!.contains("Yes, with authorization."))
    }

    @Test
    fun `publish decodes an error-envelope folded into a 200 body`() = runTest {
        // The gateway returns github_not_configured as a 403 envelope; this also
        // covers the few error shapes it folds into the JSON body it answers with.
        val c = client {
            CockpitRawResponse(
                200,
                """{"error":"github_not_configured",
                    "message":"set GITHUB_PERSONAL_ACCESS_TOKEN in ~/.hermes/.env to publish"}""".trimIndent(),
            )
        }
        val res = c.jobPublish("job_1", PublishRequest(authorization = "Yes, with authorization."))
        assertTrue(res is CockpitResult.Success)
        val r = (res as CockpitResult.Success).value
        assertEquals("github_not_configured", r.error)
        assertFalse(r.isPublished)
        assertFalse(r.isApprovalRequired)
    }

    @Test
    fun `publish surfaces a non-2xx error envelope as a Failure`() = runTest {
        val c = client {
            CockpitRawResponse(403, """{"error":{"code":"forbidden","message":"loopback only"}}""")
        }
        val res = c.jobPublish("job_1", PublishRequest())
        assertTrue(res is CockpitResult.Failure)
        assertEquals(403, (res as CockpitResult.Failure).httpStatus)
        assertEquals("forbidden", res.error.code)
    }

    // ─── templates ──────────────────────────────────────────────────────────

    @Test
    fun `templates decodes the list`() = runTest {
        val c = client {
            CockpitRawResponse(
                200,
                """{"templates":[{"id":"bug","title":"Bug fix","body":"Fix: "},
                                 {"id":"feat","title":"Feature","body":"Add: "}]}""".trimIndent(),
            )
        }
        val res = c.templates()
        assertTrue(res is CockpitResult.Success)
        val list = (res as CockpitResult.Success).value.templates
        assertEquals(2, list.size)
        assertEquals("bug", list[0].id)
        assertEquals("Bug fix", list[0].title)
        assertEquals("Add: ", list[1].body)
        assertTrue(seen.any { it == "GET" to "/templates" })
    }

    @Test
    fun `templates tolerates an honest-empty list`() = runTest {
        val c = client { CockpitRawResponse(200, """{"templates":[]}""") }
        val res = c.templates()
        assertTrue(res is CockpitResult.Success)
        assertTrue((res as CockpitResult.Success).value.templates.isEmpty())
    }
}
