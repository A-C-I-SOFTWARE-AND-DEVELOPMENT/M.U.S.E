package com.aci.hermes.data.cockpit

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Phase 18 cockpit API contract — Kotlin mirror.
 *
 * One-to-one with the JSON shapes in
 * docs/android/hermes-apk-api-contract.md. Adding fields here without
 * updating that doc (and vice versa) is the failure mode this file
 * exists to prevent.
 *
 * Nothing here makes network calls. The live `HermesCockpitClient` is
 * a separate class that lands with the cockpit-screen implementation.
 */

// ─── Health ───────────────────────────────────────────────────────────

/**
 * Response of `GET /v1/health` — the negotiation entrypoint (contract
 * §2/§11). Fields are tolerant of contract drift: the live gateway
 * (`gateway/cockpit/handlers.py`) returns `service` / `api_version` /
 * `gateway_version`, while the older spec variant used `version` /
 * `message`. Both are accepted; absent fields stay null.
 */
@Serializable
data class HealthStatus(
    val ok: Boolean = false,
    val service: String? = null,
    @SerialName("api_version") val apiVersion: String? = null,
    @SerialName("gateway_version") val gatewayVersion: String? = null,
    val time: String? = null,
    // Older spec variant (kept so a pre-cockpit gateway still negotiates).
    val version: String? = null,
    val message: String? = null,
) {
    /** Best-effort gateway version across both response variants. */
    val resolvedVersion: String?
        get() = gatewayVersion ?: version
}

// ─── Runtime ──────────────────────────────────────────────────────────

@Serializable
data class RuntimeStatus(
    val gateway: GatewayRuntime,
    val host: HostInfo,
    val queue: QueueSnapshot,
)

@Serializable
data class GatewayRuntime(
    val version: String,
    @SerialName("started_at") val startedAt: String,
    val pid: Long? = null,
    val mode: String,
)

@Serializable
data class HostInfo(
    val platform: String,
    val arch: String,
    val hostname: String,
)

@Serializable
data class QueueSnapshot(
    val running: Int,
    val queued: Int,
    @SerialName("waiting_approval") val waitingApproval: Int,
)

@Serializable
data class WorkerDetectionList(val workers: List<DetectedWorker>)

@Serializable
data class DetectedWorker(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val kind: String,
    val available: Boolean,
    val version: String? = null,
    val path: String? = null,
    val notes: String? = null,
)

// ─── Jobs ─────────────────────────────────────────────────────────────

@Serializable
data class CockpitJob(
    val id: String,
    val title: String,
    @SerialName("worker_id") val workerId: String,
    val status: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("workspace_path") val workspacePath: String? = null,
    val branch: String? = null,
    @SerialName("base_branch") val baseBranch: String? = null,
    val remote: String? = null,
    @SerialName("validation_summary") val validationSummary: ValidationSummary? = null,
    @SerialName("publish_state") val publishState: String? = null,
)

@Serializable
data class ValidationSummary(
    val pass: Int,
    val fail: Int,
    val pending: Int,
)

@Serializable
data class JobList(
    val jobs: List<CockpitJob>,
    @SerialName("next_cursor") val nextCursor: String? = null,
    @SerialName("prev_cursor") val prevCursor: String? = null,
)

@Serializable
data class DispatchJobRequest(
    val title: String,
    @SerialName("worker_id") val workerId: String,
    val prompt: String,
    @SerialName("workspace_path") val workspacePath: String? = null,
    @SerialName("branch_hint") val branchHint: String? = null,
    val watch: Boolean = false,
)

@Serializable
data class CancelJobRequest(val reason: String? = null)

/**
 * POST body for `jobs/{id}/run`. An execute lane (one whose worker
 * `requires_approval`) only runs when [authorization] equals the exact owner
 * phrase; the gateway returns `403` otherwise — and refuses entirely on a
 * non-loopback cockpit. Non-gated lanes (local planner / handoff) ignore it.
 */
@Serializable
data class RunJobRequest(
    @SerialName("worker_id") val workerId: String,
    val authorization: String? = null,
)

/**
 * Result of `jobs/{id}/run` — the (advanced) job plus the tail of its worker
 * ledger trail. `worker_trail` entries are free-form ledger dicts; only the
 * fields the cockpit renders are modelled (the tolerant decoder ignores the
 * rest).
 */
@Serializable
data class RunJobResult(
    val job: CockpitJob? = null,
    @SerialName("worker_trail") val workerTrail: List<WorkerTrailEntry> = emptyList(),
)

@Serializable
data class WorkerTrailEntry(
    val kind: String = "",
    @SerialName("worker_id") val workerId: String? = null,
    val summary: String? = null,
)

/**
 * A **runnable** worker lane (`GET /v1/cockpit/jobs/lanes`) — the ids
 * `job_run` actually accepts (e.g. `codex-execute`, `hermes-local-planner`),
 * NOT the detection lanes from `runtime/workers`. [requiresApproval] tells the
 * UI which lanes need the owner phrase before running.
 */
@Serializable
data class JobLane(
    val id: String,
    @SerialName("display_name") val displayName: String = "",
    @SerialName("requires_approval") val requiresApproval: Boolean = true,
)

@Serializable
data class JobLaneList(val lanes: List<JobLane> = emptyList())

/** POST body for `/v1/cockpit/orchestrate` — create a runnable orchestrator job. */
@Serializable
data class OrchestrateRequest(val prompt: String)
// ─── Job detail / ledger (contract §4 — GET /jobs/{id}/ledger) ─────────

/**
 * Read-only execution story for the Job Detail screen — the canonical
 * mirror of `gateway/cockpit/contract.py::orchestrator_job_detail` /
 * `queue_job_detail`. Reuses the audit-section wire models
 * ([CockpitEvidenceItem], [CockpitApprovalHistoryItem], [CockpitRollbackPlan])
 * so there is one shape per concept. Honest absences arrive as empty/null.
 */
@Serializable
data class JobDetail(
    val id: String,
    val objective: String = "",
    val status: String = "QUEUED",
    val plan: String = "",
    @SerialName("current_step") val currentStep: String? = null,
    val workers: List<JobWorkerRef> = emptyList(),
    val timeline: List<JobTimelineEntry> = emptyList(),
    val evidence: List<CockpitEvidenceItem> = emptyList(),
    @SerialName("files_touched") val filesTouched: List<String> = emptyList(),
    @SerialName("commands_run") val commandsRun: List<String> = emptyList(),
    @SerialName("test_results") val testResults: ValidationSummary? = null,
    val approvals: List<CockpitApprovalHistoryItem> = emptyList(),
    val rollback: CockpitRollbackPlan? = null,
) {
    /** Resolved [JobStatus], or null if the gateway sent an unknown value. */
    val jobStatus: JobStatus? get() = JobStatus.fromWire(status)
}

@Serializable
data class JobWorkerRef(
    val id: String = "",
    val worker: String = "",
    val status: String = "PENDING",
    val summary: String = "",
    val error: String? = null,
    val attempts: Int = 0,
)

@Serializable
data class JobTimelineEntry(
    val ts: String = "",
    val kind: String = "",
    val phase: String? = null,
    val actor: String = "controller",
    val summary: String = "",
)

/** POST body for `/jobs/{id}/approve` — owner phrase gates the grant. */
@Serializable
data class ApprovePhaseRequest(
    val phase: String = "execute",
    val authorization: String? = null,
)

/** POST body for `/jobs/{id}/rerun` — optional explicit worker to retry. */
@Serializable
data class RerunJobRequest(@SerialName("worker_id") val workerId: String? = null)

// ─── Backend diagnostics (launch doctor) ──────────────────────────────

/**
 * `GET /v1/cockpit/diagnostics` — the backend's own launch-readiness report
 * (the JARVIS launch doctor), so the cockpit can show *backend* health, not
 * just on-device logs. Tolerant: an unreachable/older gateway leaves fields
 * at their honest defaults.
 */
@Serializable
data class CockpitDiagnostics(
    val ok: Boolean = false,
    val checks: List<DiagnosticCheck> = emptyList(),
    @SerialName("generated_at") val generatedAt: String? = null,
    val error: String? = null,
)

@Serializable
data class DiagnosticCheck(
    val name: String = "",
    val status: String = "",   // pass | warn | fail
    val detail: String = "",
    val hard: Boolean = true,
)

// ─── Sessions (decision-ledger activity) ──────────────────────────────

/**
 * Wire model for `GET /v1/cockpit/sessions` — decision-ledger sessions
 * (recent backend activity), grouped by session id with a decision count.
 * Read-only; honest empty when the ledger is empty.
 */
@Serializable
data class CockpitSession(
    val id: String = "",
    @SerialName("decision_count") val decisionCount: Int = 0,
    @SerialName("last_updated") val lastUpdated: String? = null,
)

@Serializable
data class CockpitSessionList(val sessions: List<CockpitSession> = emptyList())

// ─── Files ────────────────────────────────────────────────────────────

@Serializable
data class TreeListing(
    val path: String,
    val entries: List<TreeEntry>,
)

@Serializable
data class TreeEntry(
    val name: String,
    val kind: String,
    val size: Long? = null,
    val mtime: String? = null,
)

@Serializable
data class FileSnapshot(
    val path: String,
    val size: Long,
    val truncated: Boolean,
    val content: String? = null,
    val encoding: String? = null,
)

// ─── Diff and approval ────────────────────────────────────────────────

@Serializable
data class DiffSnapshot(
    val files: List<DiffFile>,
    val diff: String,
    val truncated: Boolean,
)

@Serializable
data class DiffFile(
    val path: String,
    val additions: Int,
    val deletions: Int,
)

@Serializable
data class ApproveJobRequest(
    val decision: String,
    val notes: String? = null,
    @SerialName("decided_at") val decidedAt: String,
    @SerialName("decided_by") val decidedBy: String = "cockpit",
)

// ─── Validation ───────────────────────────────────────────────────────

@Serializable
data class ValidationSnapshot(
    val gates: List<ValidationGate>,
    val policy: ValidationPolicy,
)

@Serializable
data class ValidationGate(
    val id: String,
    val name: String,
    val status: String,
    val summary: String? = null,
    @SerialName("log_excerpt") val logExcerpt: String? = null,
    @SerialName("override_allowed") val overrideAllowed: Boolean = false,
    // Present only on gates carried back by an override response; absent (and so
    // defaulted) on plain validation/revalidate snapshots.
    @SerialName("override_applied") val overrideApplied: Boolean = false,
    @SerialName("override_note") val overrideNote: String? = null,
)

@Serializable
data class ValidationPolicy(
    @SerialName("all_must_pass") val allMustPass: Boolean,
    @SerialName("override_requires_note") val overrideRequiresNote: Boolean,
)

@Serializable
data class OverrideValidationRequest(
    @SerialName("gate_ids") val gateIds: List<String>,
    val note: String,
)

// ─── Publishing ───────────────────────────────────────────────────────

/**
 * Read-only preview of `GET /v1/cockpit/jobs/{id}/publish/preview` (and the
 * `preview` block of the `approval_required` publish response). Every field is
 * nullable/defaulted because the gateway emits honest nulls/empty when the job
 * has no git workspace or no commits ahead of its base
 * (`gateway/cockpit/handlers.py::_publish_preview_payload`).
 */
@Serializable
data class PublishPreview(
    val remote: String? = null,
    val branch: String? = null,
    val base: String? = null,
    val commits: List<PublishCommit> = emptyList(),
    @SerialName("default_title") val defaultTitle: String? = null,
    @SerialName("default_body") val defaultBody: String? = null,
    @SerialName("existing_pr_url") val existingPrUrl: String? = null,
)

@Serializable
data class PublishCommit(
    val sha: String,
    val subject: String,
)

/**
 * POST body for `/v1/cockpit/jobs/{id}/publish`. Every field is optional: the
 * owner [authorization] phrase gates the real PR open (absent → a staged
 * `approval_required` response), and title/body/base/draft fall back to the
 * preview defaults server-side when omitted.
 */
@Serializable
data class PublishRequest(
    val authorization: String? = null,
    val title: String? = null,
    val body: String? = null,
    val base: String? = null,
    val draft: Boolean? = null,
)

/**
 * Tolerant union for `POST /v1/cockpit/jobs/{id}/publish`. The gateway returns
 * one of three shapes (`gateway/cockpit/handlers.py::job_publish`), all decoded
 * here so a single typed result covers them:
 *  - **approval_required** — [status] == `"approval_required"`,
 *    [authorizationRequired] true, [preview] populated (no GitHub call made);
 *  - **published** — [prUrl]/[prNumber]/[state]/[isDraft] populated;
 *  - **error** — [error] populated (e.g. `github_not_configured`, plus a
 *    [prUrl] when a PR already exists). Most non-2xx errors arrive as a
 *    [CockpitResult.Failure] envelope instead; this field captures the few the
 *    gateway folds into a 200/JSON body.
 *
 * Disjoint fields stay null for the shapes that don't carry them.
 */
@Serializable
data class PublishResult(
    val status: String? = null,
    val preview: PublishPreview? = null,
    @SerialName("authorization_required") val authorizationRequired: Boolean = false,
    @SerialName("authorization_hint") val authorizationHint: String? = null,
    @SerialName("pr_url") val prUrl: String? = null,
    @SerialName("pr_number") val prNumber: Int? = null,
    val branch: String? = null,
    val remote: String? = null,
    val state: String? = null,
    @SerialName("is_draft") val isDraft: Boolean? = null,
    val error: String? = null,
    val message: String? = null,
) {
    /** True when the gateway staged the publish behind the owner phrase. */
    val isApprovalRequired: Boolean get() = status == "approval_required" || authorizationRequired

    /** True once a real PR was opened (a resolvable PR url with no error). */
    val isPublished: Boolean get() = error == null && !prUrl.isNullOrBlank() && !isApprovalRequired
}

// ─── Files changed (numstat only) ─────────────────────────────────────

/**
 * Response of `GET /v1/cockpit/jobs/{id}/files-changed` — the per-file
 * additions/deletions ([DiffFile]) without the patch body. Honest empty when
 * the job has no git workspace
 * (`gateway/cockpit/handlers.py::job_files_changed`).
 */
@Serializable
data class FilesChangedSnapshot(
    val files: List<DiffFile> = emptyList(),
)

// ─── Prompt templates ─────────────────────────────────────────────────

/**
 * One owner-defined prompt template from `GET /v1/cockpit/templates`
 * (`gateway/cockpit/handlers.py::templates_list`). The gateway only emits
 * entries with all three fields populated; honest-empty list when none exist.
 */
@Serializable
data class PromptTemplate(
    val id: String,
    val title: String,
    val body: String,
)

@Serializable
data class TemplateList(val templates: List<PromptTemplate> = emptyList())

// ─── Events ───────────────────────────────────────────────────────────

@Serializable
data class EventBatch(
    val events: List<CockpitEvent>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

@Serializable
data class CockpitEvent(
    val ts: String,
    val level: String,
    val source: String,
    @SerialName("job_id") val jobId: String? = null,
    val message: String,
    val attributes: Map<String, String>? = null,
)

// ─── Skills (real installed gateway skills) ───────────────────────────

/**
 * Wire model for `GET /v1/cockpit/skills` — the gateway's **real** installed
 * skills (the live skill scanner), so the Capability screen can show what the
 * backend actually has, not just the curated in-app catalog. Honest empty when
 * none are installed; never fabricated.
 */
@Serializable
data class CockpitSkill(
    val id: String = "",
    val command: String = "",
    val name: String = "",
    val description: String = "",
)

@Serializable
data class CockpitSkillList(val skills: List<CockpitSkill> = emptyList())

// ─── Navigation (HyperAgent pre-dispatch "where to look") ─────────────

/**
 * Wire model for `GET /v1/cockpit/navigation` — the HyperAgent navigator's
 * pre-dispatch decision for an orchestrate job: the ranked candidate files it
 * chose to look at (with rationale) before any worker ran. Read-only
 * transparency; honest empty when a job never navigated.
 */
@Serializable
data class CockpitNavigation(
    @SerialName("job_id") val jobId: String = "",
    val objective: String = "",
    @SerialName("created_at") val createdAt: String = "",
    val method: String = "",
    @SerialName("candidate_files") val candidateFiles: List<NavCandidate> = emptyList(),
    @SerialName("verify_with") val verifyWith: List<String> = emptyList(),
)

@Serializable
data class NavCandidate(
    val path: String = "",
    val rank: Int = 0,
    val confidence: Float = 0f,
    val rationale: String = "",
)

@Serializable
data class CockpitNavigationList(val navigations: List<CockpitNavigation> = emptyList())

// ─── Models / router policy ───────────────────────────────────────────

/**
 * Wire model for `GET /v1/cockpit/models` — the free-first router policy
 * surfaced by `gateway/cockpit/handlers.py::models` (which returns the raw
 * `model_bootstrap.load_policy()` dict). The server shape is intentionally
 * loose, so every field here is defaulted/nullable and unknown keys are
 * ignored by the tolerant [CockpitHttp.json] config — an evolving policy
 * shape never crashes the home screen. The home repository maps this to a
 * small display summary.
 */
@Serializable
data class ModelPolicy(
    val routes: Map<String, ModelRoute> = emptyMap(),
    @SerialName("free_first") val freeFirst: Boolean? = null,
    @SerialName("paid_opt_in") val paidOptIn: Boolean? = null,
    @SerialName("default_route") val defaultRoute: String? = null,
    @SerialName("_note") val note: String? = null,
    val error: String? = null,
)

/**
 * One route entry. The server emits per-route objects whose exact keys vary
 * by provider; only the commonly-present descriptive fields are modelled and
 * everything else is ignored. Kept nullable so a sparse entry still decodes.
 */
@Serializable
data class ModelRoute(
    val provider: String? = null,
    val model: String? = null,
    val tier: String? = null,
    val enabled: Boolean? = null,
)

// ─── Local models (Gemma / Ollama) — honest status ────────────────────
//
// Mirrors `GET /v1/cockpit/models/local`. The Model Center renders these with
// the honest label vocabulary (see apps/android/docs/GEMMA_LOCAL_MODE.md): a
// GET never reports "smoke-tested" / "ready" — that is earned only by the
// explicit `models/local/smoke` POST.

@Serializable
data class LocalModelsStatus(
    @SerialName("ollama_base") val ollamaBase: String = "",
    /** not_configured | configured | runtime_reachable */
    @SerialName("runtime_status") val runtimeStatus: String = "not_configured",
    val reachable: Boolean = false,
    @SerialName("reach_error") val reachError: String? = null,
    val runtimes: List<LocalRuntime> = emptyList(),
    val installed: List<LocalModelEntry> = emptyList(),
    /** task_class -> chosen local model. */
    val promotions: Map<String, String> = emptyMap(),
    @SerialName("generated_at") val generatedAt: String? = null,
    val error: String? = null,
)

@Serializable
data class LocalRuntime(
    val name: String = "",
    val available: Boolean = false,
    val path: String? = null,
)

@Serializable
data class LocalModelEntry(
    val name: String = "",
    @SerialName("promoted_for") val promotedFor: List<String> = emptyList(),
    @SerialName("fallback_for") val fallbackFor: List<String> = emptyList(),
    /** promoted_for_task | fallback_only | variant_installed */
    val status: String = "variant_installed",
)

@Serializable
data class LocalModelSmokeRequest(val model: String? = null)

@Serializable
data class LocalModelSmokeResult(
    val ok: Boolean = false,
    val model: String = "",
    @SerialName("reply_excerpt") val replyExcerpt: String = "",
    @SerialName("latency_ms") val latencyMs: Long = 0,
    val error: String? = null,
)

// ─── Research Vault (evidence store) ──────────────────────────────────

/**
 * Wire model for `GET /v1/cockpit/research` — one item from the JARVIS
 * Research Vault (`muse_cli/jarvis_prime/research_vault.py`). One-to-one
 * with `ResearchArtifact.to_dict()`. Recent-first; the gateway returns an
 * honest empty list (never fabricated evidence) when the vault is missing.
 */
@Serializable
data class CockpitResearchItem(
    val id: String,
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "manual",
    @SerialName("evidence_strength") val evidenceStrength: String = "moderate",
    val summary: String = "",
    val excerpt: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("freshness_due") val freshnessDue: String? = null,
    @SerialName("added_at") val addedAt: String? = null,
)

@Serializable
data class CockpitResearchList(
    val items: List<CockpitResearchItem> = emptyList(),
    val error: String? = null,
)

// ─── Destructive approvals ────────────────────────────────────────────

@Serializable
data class ApprovalList(val approvals: List<PendingApproval>)

@Serializable
data class PendingApproval(
    val id: String,
    @SerialName("job_id") val jobId: String,
    val kind: String,
    val summary: String,
    val details: Map<String, String>? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
)

@Serializable
data class DecideApprovalRequest(
    val decision: String,
    val notes: String? = null,
)

// ─── Memory ───────────────────────────────────────────────────────────

/**
 * Wire model for a cockpit memory item (contract §10a). One-to-one with
 * the server's canonical `MemoryItem`. Enum-like fields are raw Strings
 * here so an unknown future value never crashes deserialisation; the
 * repository maps them to the typed domain
 * [com.aci.hermes.data.memory.MemoryItem]. Timestamps are ISO-8601 UTC.
 */
@Serializable
data class CockpitMemoryItem(
    val id: String,
    val category: String,
    val title: String,
    val content: String,
    val durability: String,
    val confidence: String,
    val provenance: CockpitMemoryProvenance,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("last_accessed_at") val lastAccessedAt: String? = null,
    val tags: List<String> = emptyList(),
    val redacted: Boolean = false,
    val hidden: Boolean = false,
)

@Serializable
data class CockpitMemoryProvenance(
    val source: String,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("recorded_at") val recordedAt: String? = null,
    val note: String? = null,
)

@Serializable
data class CockpitMemoryList(val items: List<CockpitMemoryItem> = emptyList())

/** POST body for creating memory (canonical fields). */
@Serializable
data class CreateMemoryRequest(
    val title: String,
    val content: String,
    val category: String? = null,
    val durability: String? = null,
    val confidence: String? = null,
    val tags: List<String> = emptyList(),
    val hidden: Boolean = false,
)

@Serializable
data class CreateMemoryResponse(
    val stored: Boolean = false,
    val item: CockpitMemoryItem? = null,
    val reason: String? = null,
)

@Serializable
data class DeleteMemoryResponse(val removed: Int = 0)

// ─── Evidence Engine (contract §10d) ──────────────────────────────────

/**
 * Wire model for a cockpit evidence artifact (contract §10d). One-to-one
 * with the server's `evidence_card` projection of a Research Vault
 * `ResearchArtifact`. Distinct from [CockpitEvidenceItem] (which is an
 * audit-proof sub-record). Enum-like fields are raw Strings so an unknown
 * future value never crashes deserialisation; timestamps are ISO-8601 UTC.
 */
@Serializable
data class CockpitEvidenceCard(
    val id: String,
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("evidence_strength") val evidenceStrength: String = "",
    val trust: String = "unverified",
    val excerpt: String = "",
    val summary: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("license_notes") val licenseNotes: String = "",
    @SerialName("retrieved_at") val retrievedAt: String? = null,
    @SerialName("freshness_due") val freshnessDue: String? = null,
    val checksum: String = "",
    @SerialName("citation_anchors") val citationAnchors: List<String> = emptyList(),
    @SerialName("added_at") val addedAt: String? = null,
)

@Serializable
data class CockpitEvidenceList(
    val items: List<CockpitEvidenceCard> = emptyList(),
    val hits: List<CockpitEvidenceHit> = emptyList(),
)

@Serializable
data class CockpitEvidenceDetail(val item: CockpitEvidenceCard? = null)

/** One ranked retrieval hit from `GET /evidence?q=` or the verify endpoint. */
@Serializable
data class CockpitEvidenceHit(
    val kind: String = "",
    val title: String = "",
    val uri: String = "",
    val excerpt: String = "",
    val trust: String = "unverified",
    val score: Float = 0f,
    @SerialName("artifact_id") val artifactId: String? = null,
    @SerialName("citation_anchors") val citationAnchors: List<String> = emptyList(),
)

@Serializable
data class EvidenceVerifyRequest(
    val claims: List<String>,
    val query: String? = null,
)

@Serializable
data class CockpitEvidenceVerifyResult(
    val citations: List<CockpitClaimCitation> = emptyList(),
    val uncertain: List<String> = emptyList(),
    val contradictions: List<CockpitEvidenceContradiction> = emptyList(),
    val rejected: List<String> = emptyList(),
)

@Serializable
data class CockpitClaimCitation(
    val claim: String = "",
    val supported: Boolean = false,
    val hits: List<CockpitEvidenceHit> = emptyList(),
)

@Serializable
data class CockpitEvidenceContradiction(
    val subject: String = "",
    val a: String = "",
    val b: String = "",
    val reason: String = "",
)

/** POST body for `evidence/{id}/promote` — owner phrase gates durable writes. */
@Serializable
data class PromoteEvidenceRequest(val authorization: String? = null)

@Serializable
data class PromoteEvidenceResponse(
    val promoted: Boolean = false,
    @SerialName("node_id") val nodeId: String? = null,
    val reasons: List<String> = emptyList(),
    val hint: String? = null,
)

// ─── Memory Tree (MEM-2): provenance-first cognition plane ──────────────
//
// Distinct from CockpitMemoryItem: a tree node carries layer / approval /
// contradiction / freshness so the cockpit can run the proposed-inbox,
// contradiction, and freshness-review flows the flat store can't express.

@Serializable
data class CockpitMemoryNode(
    val id: String,
    val namespace: String,
    val layer: String,
    val title: String,
    val summary: String = "",
    val content: String = "",
    val sources: List<String> = emptyList(),
    val confidence: Float = 0f,
    val trust: String = "unverified",
    val sensitivity: String = "internal",
    @SerialName("approval_state") val approvalState: String = "proposed",
    @SerialName("contradiction_status") val contradictionStatus: String = "none",
    val contested: Boolean = false,
    val subject: String? = null,
    @SerialName("superseded_by") val supersededBy: String? = null,
    val supersedes: List<String> = emptyList(),
    @SerialName("freshness_due") val freshnessDue: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    val tags: List<String> = emptyList(),
)

@Serializable
data class CockpitMemoryNodeList(val nodes: List<CockpitMemoryNode> = emptyList())

@Serializable
data class CockpitContradiction(
    val id: String,
    val namespace: String = "",
    val subject: String = "",
    @SerialName("node_a_id") val nodeAId: String,
    @SerialName("node_b_id") val nodeBId: String,
    val reason: String = "",
    val status: String = "contested",
    @SerialName("winner_id") val winnerId: String? = null,
    @SerialName("resolution_note") val resolutionNote: String = "",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
)

@Serializable
data class CockpitContradictionList(
    val contradictions: List<CockpitContradiction> = emptyList(),
)

/** POST body for an owner decision on a proposed node. */
@Serializable
data class MemoryDecisionRequest(
    val decision: String, // approve | reject | supersede
    @SerialName("supersedes_id") val supersedesId: String? = null,
    val note: String? = null,
)

@Serializable
data class MemoryDecisionResponse(
    val decided: String = "",
    val node: CockpitMemoryNode? = null,
    val winner: CockpitMemoryNode? = null,
    val superseded: CockpitMemoryNode? = null,
    val contradiction: CockpitContradiction? = null,
)

/** POST body for resolving a contradiction. */
@Serializable
data class ResolveContradictionRequest(
    @SerialName("winner_id") val winnerId: String,
    val note: String? = null,
)

@Serializable
data class ResolveContradictionResponse(
    val resolved: CockpitContradiction? = null,
)

// ─── Audit ────────────────────────────────────────────────────────────

/**
 * Wire models for the cockpit audit surface (contract §10b). One-to-one
 * with the server's canonical `AuditRecord` / `ProofRecord`. Enum-like
 * fields are raw Strings; the repository maps them to the typed domain
 * models in `com.aci.hermes.data.model.audit`. Timestamps are ISO-8601.
 */
@Serializable
data class CockpitAuditList(val records: List<CockpitAuditRecord> = emptyList())

@Serializable
data class CockpitAuditRecord(
    val id: String,
    val timestamp: String? = null,
    @SerialName("user_request") val userRequest: String = "",
    val action: String = "",
    @SerialName("risk_tier") val riskTier: String = "LOW",
    val route: CockpitRouteSummary = CockpitRouteSummary(),
    @SerialName("approval_state") val approvalState: String = "UNNECESSARY",
    val result: String = "SUCCESS",
    val confidence: Float = 0f,
    @SerialName("proof_id") val proofId: String = "",
)

@Serializable
data class CockpitRouteSummary(
    val destination: String = "HUMAN_ONLY",
    val model: String? = null,
    val reason: String = "",
    @SerialName("duration_ms") val durationMs: Long = 0,
)

@Serializable
data class CockpitProofRecord(
    val id: String = "",
    @SerialName("audit_id") val auditId: String,
    val rationale: String = "",
    val evidence: List<CockpitEvidenceItem> = emptyList(),
    @SerialName("tests_run") val testsRun: List<String> = emptyList(),
    @SerialName("files_changed") val filesChanged: List<String> = emptyList(),
    val verification: CockpitVerificationResult = CockpitVerificationResult(),
    val approvals: List<CockpitApprovalHistoryItem> = emptyList(),
    val rollback: CockpitRollbackPlan? = null,
    @SerialName("impact_report") val impactReport: String? = null,
    @SerialName("worker_runs") val workerRuns: List<CockpitWorkerRun> = emptyList(),
)

@Serializable
data class CockpitEvidenceItem(
    val id: String = "",
    val kind: String = "LOG",
    val title: String = "",
    val body: String = "",
    @SerialName("source_path") val sourcePath: String? = null,
)

@Serializable
data class CockpitVerificationResult(
    val status: String = "SKIPPED",
    val summary: String = "",
    @SerialName("failing_checks") val failingChecks: List<String> = emptyList(),
    @SerialName("passed_checks") val passedChecks: List<String> = emptyList(),
)

@Serializable
data class CockpitApprovalHistoryItem(
    val id: String = "",
    val timestamp: String? = null,
    val approver: String = "",
    val state: String = "PENDING",
    val comment: String? = null,
)

@Serializable
data class CockpitRollbackPlan(
    val id: String = "",
    val summary: String = "",
    val steps: List<String> = emptyList(),
    val automatic: Boolean = false,
    val executed: Boolean = false,
)

@Serializable
data class CockpitWorkerRun(
    val id: String = "",
    val worker: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("finished_at") val finishedAt: String? = null,
    val status: String = "SUCCESS",
    val notes: String = "",
)

// ─── Approval cards (canonical) ───────────────────────────────────────

/**
 * Wire model for the canonical owner-approval queue (contract §10c) —
 * one-to-one with the server's `ApprovalCard`. Enum-like fields are raw
 * Strings (mapped to `approval.model` enums by the repository); timestamps
 * are ISO-8601 (null `expires_at` = never expires). Multi-step
 * serious/critical state is UI-runtime and defaulted client-side.
 */
@Serializable
data class CockpitApprovalCardList(val approvals: List<CockpitApprovalCard> = emptyList())

@Serializable
data class CockpitApprovalCard(
    val id: String,
    val title: String = "",
    val summary: String = "",
    val requester: String = "",
    val tier: String = "RISKY",
    val status: String = "PENDING",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    @SerialName("proposed_action") val proposedAction: String = "",
    @SerialName("edited_note") val editedNote: String? = null,
)

/** POST body for `approvals/{id}` — approve requires the owner phrase. */
@Serializable
data class CockpitApprovalDecision(
    val decision: String,
    val authorization: String? = null,
    val notes: String? = null,
)

@Serializable
data class CockpitApprovalDecisionResult(
    val id: String = "",
    val status: String? = null,
    val error: String? = null,
    val hint: String? = null,
)

// ─── Learning Queue (learning-dataset candidate review) ───────────────
//
// Provenance-first cards for the owner Learning Queue. The gateway projects
// learning-dataset candidates (already secret-scrubbed at write time); the
// list never carries the raw trace payload.

@Serializable
data class CockpitLearningList(val learning: List<CockpitLearningCard> = emptyList())

@Serializable
data class CockpitLearningCard(
    val id: String,
    val title: String = "",
    @SerialName("trace_type") val traceType: String = "",
    val status: String = "pending",
    val labels: List<String> = emptyList(),
    @SerialName("is_negative") val isNegative: Boolean = false,
    val quality: CockpitLearningQuality = CockpitLearningQuality(),
    val provenance: CockpitLearningProvenance = CockpitLearningProvenance(),
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class CockpitLearningQuality(
    @SerialName("tests_passed") val testsPassed: Boolean = false,
    @SerialName("citations_verified") val citationsVerified: Boolean = false,
    @SerialName("owner_approved") val ownerApproved: Boolean = false,
    @SerialName("reviewer_passed") val reviewerPassed: Boolean = false,
    @SerialName("rollback_available") val rollbackAvailable: Boolean = false,
)

@Serializable
data class CockpitLearningProvenance(
    @SerialName("source_kind") val sourceKind: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    val citations: List<String> = emptyList(),
)

// ─── Voice intake (mobile-native, hands-free) ─────────────────────────
//
// Mirrors the canonical pipeline exposed by gateway/cockpit (which wraps
// muse_cli.voice_intake). The app sends an already-transcribed string and
// the backend owns read-back / classification / the driving-mode safety
// veto — the client never reimplements them.

/** POST body for `voice/intake`. */
@Serializable
data class VoiceIntakeRequest(
    val transcript: String,
    val mode: String? = null,
)

@Serializable
data class VoiceDraftView(
    val intent: String = "unknown",
    val summary: String = "",
    @SerialName("publish_action") val publishAction: Boolean = false,
    @SerialName("requires_implementation") val requiresImplementation: Boolean = false,
)

/** Response from `voice/intake` — the read-back the user must hear/confirm. */
@Serializable
data class VoiceIntakeResult(
    val id: String = "",
    val mode: String = "push_to_talk",
    val readback: String = "",
    @SerialName("approval_state") val approvalState: String = "pending_readback",
    val draft: VoiceDraftView = VoiceDraftView(),
)

/** POST body for `voice/{id}/decide` — the explicit spoken/typed phrase. */
@Serializable
data class VoiceDecisionRequest(
    val phrase: String? = null,
)

/** Response from `voice/{id}/decide`. A `409` Failure carries the driving
 *  veto / confirmation-required hint (parsed from the error envelope). */
@Serializable
data class VoiceDecisionResult(
    val id: String = "",
    val state: String = "pending_readback",
    @SerialName("job_id") val jobId: String? = null,
    val notes: List<String> = emptyList(),
)

// ─── Error envelope ───────────────────────────────────────────────────

@Serializable
data class CockpitErrorEnvelope(val error: CockpitError)

@Serializable
data class CockpitError(
    val code: String,
    val message: String,
    val details: Map<String, String>? = null,
)

/**
 * Job status lifecycle. Mirrors the canonical contract (§4) — a superset
 * of the JARVIS-Prime queue's execution states and the cockpit's
 * publish-workflow states. Wire values are the enum constant names
 * (UPPER_SNAKE, per §1); [fromWire] is case-insensitive so a legacy
 * lowercase gateway still maps. Kept string-valued so an unknown future
 * value never crashes deserialisation.
 */
enum class JobStatus(val wire: String) {
    DRAFT("DRAFT"),
    QUEUED("QUEUED"),
    RUNNING("RUNNING"),
    PAUSED("PAUSED"),
    BLOCKED("BLOCKED"),
    DISCONNECTED("DISCONNECTED"),
    COMPLETED("COMPLETED"),
    WAITING_FOR_APPROVAL("WAITING_FOR_APPROVAL"),
    APPROVED("APPROVED"),
    PUBLISHING("PUBLISHING"),
    PUBLISHED("PUBLISHED"),
    FAILED("FAILED"),
    CANCELLED("CANCELLED");

    /** Terminal states never auto-advance. */
    val isTerminal: Boolean
        get() = this == PUBLISHED || this == FAILED || this == CANCELLED || this == COMPLETED

    companion object {
        fun fromWire(value: String?): JobStatus? =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) }
    }
}

enum class PublishState(val wire: String) {
    NOT_STARTED("NOT_STARTED"),
    IN_PROGRESS("IN_PROGRESS"),
    SUCCEEDED("SUCCEEDED"),
    FAILED("FAILED");

    companion object {
        fun fromWire(value: String?): PublishState? =
            entries.firstOrNull { it.wire.equals(value, ignoreCase = true) }
    }
}

// ─── Avatar persona ("make my avatar Goku") ──────────────────────────────

@Serializable
data class CockpitPersona(
    val name: String = "",
    val description: String = "",
    @SerialName("persona_prompt") val personaPrompt: String = "",
    val generated: Boolean = false,
)

@Serializable
data class SetPersonaRequest(
    val description: String,
    val name: String = "",
)

// ─── Room editor (AI-generated furniture) ─────────────────────────────────

@Serializable
data class CockpitRoomItem(
    val id: String = "",
    val prompt: String = "",
    @SerialName("image_b64") val imageB64: String? = null,
    val x: Float = 0.5f,
    val y: Float = 0.62f,
)

@Serializable
data class PlaceItemRequest(val x: Float, val y: Float)

@Serializable
data class CockpitRoomList(
    val items: List<CockpitRoomItem> = emptyList(),
    @SerialName("image_generation") val imageGeneration: Boolean = false,
)

@Serializable
data class GenerateRoomRequest(val prompt: String)

// ─── Server capabilities (feature negotiation) ────────────────────────────

/**
 * Wire model for `GET /v1/cockpit/capabilities` — what *this backend* can do
 * (distinct from the curated in-app [com.aci.hermes.data.model.Capability]
 * picker). Lets the app negotiate against the live server: which subsystems
 * import, which worker lanes are present, and whether execute lanes are
 * permitted (loopback guard). Never carries the owner phrase or any secret.
 */
@Serializable
data class ServerCapabilities(
    @SerialName("api_version") val apiVersion: String = "",
    @SerialName("gateway_version") val gatewayVersion: String = "",
    val subsystems: Map<String, Boolean> = emptyMap(),
    /** Orchestrator lane ids the coding/execute + jobs/run routes accept. */
    @SerialName("available_workers") val availableWorkers: List<ServerWorkerLane> = emptyList(),
    /** Informational: external CLIs detected on the host (not execute-validated). */
    @SerialName("detected_clis") val detectedClis: List<String> = emptyList(),
    @SerialName("execute_allowed") val executeAllowed: Boolean = false,
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = true,
    @SerialName("generated_at") val generatedAt: String? = null,
)

@Serializable
data class ServerWorkerLane(
    val id: String = "",
    @SerialName("requires_approval") val requiresApproval: Boolean = true,
)

// ─── Emergency stop (real backend halt) ───────────────────────────────────

@Serializable
data class EmergencyStopRequest(val reason: String? = null)

/**
 * Result of `POST /v1/cockpit/emergency-stop`. A genuine backend halt: owner
 * gates cleared, proactive tick disabled, worker branch leases released, and
 * every non-terminal queued/running job paused (reversible via resume).
 */
@Serializable
data class EmergencyStopResult(
    val engaged: Boolean = false,
    val reason: String = "",
    @SerialName("cleared_actions") val clearedActions: List<String> = emptyList(),
    @SerialName("branch_leases_cleared") val branchLeasesCleared: Int = 0,
    @SerialName("tick_disabled") val tickDisabled: Boolean = false,
    @SerialName("cancelled_jobs") val cancelledJobs: List<String> = emptyList(),
    @SerialName("cancelled_count") val cancelledCount: Int = 0,
    @SerialName("autonomy_level") val autonomyLevel: String = "read_only",
    val errors: List<String> = emptyList(),
    @SerialName("halted_at") val haltedAt: String? = null,
)

// ─── Job pause / resume ───────────────────────────────────────────────────

@Serializable
data class JobControlRequest(val reason: String? = null)

// ─── Coding lanes (audit / plan / execute) ────────────────────────────────

@Serializable
data class CodingRequest(
    val prompt: String,
    @SerialName("repo_root") val repoRoot: String? = null,
    @SerialName("worker_id") val workerId: String? = null,
    /** Owner phrase — required only to actually dispatch an execute lane. */
    val authorization: String? = null,
    /**
     * Staged job id to **resume** on an execute. The first (unauthorized) call
     * stages a job; the authorize retry passes that id so the backend dispatches
     * the same job instead of creating (and leaking) a second one.
     */
    @SerialName("job_id") val jobId: String? = null,
)

/** Result of `POST /v1/cockpit/coding/audit` — classify + route (read-only). */
@Serializable
data class CodingAuditResult(
    val intent: String = "",
    @SerialName("risk_class") val riskClass: String = "",
    @SerialName("primary_worker") val primaryWorker: String = "",
    @SerialName("reviewer_worker") val reviewerWorker: String = "",
    @SerialName("model_lane_hint") val modelLaneHint: String = "",
    @SerialName("owner_gates") val ownerGates: List<String> = emptyList(),
    val blocked: Boolean = false,
    val rationale: String = "",
    val mission: String = "",
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = false,
)

/** A bounded coding work packet (mirrors the natural-language coder packet). */
@Serializable
data class CodingPacket(
    val mission: String = "",
    val intent: String = "",
    val branch: String = "",
    @SerialName("risk_class") val riskClass: String = "",
    @SerialName("repo_root") val repoRoot: String = ".",
    @SerialName("allowed_files") val allowedFiles: List<String> = emptyList(),
    @SerialName("forbidden_files") val forbiddenFiles: List<String> = emptyList(),
    @SerialName("acceptance_criteria") val acceptanceCriteria: List<String> = emptyList(),
    @SerialName("verification_plan") val verificationPlan: List<String> = emptyList(),
    @SerialName("rollback_plan") val rollbackPlan: List<String> = emptyList(),
    @SerialName("owner_gates") val ownerGates: List<String> = emptyList(),
    @SerialName("primary_worker") val primaryWorker: String = "",
    @SerialName("model_lane_hint") val modelLaneHint: String = "",
    val blocked: Boolean = false,
)

@Serializable
data class CodingValidationFinding(
    val field: String = "",
    val severity: String = "",
    val message: String = "",
)

@Serializable
data class CodingValidation(
    val ok: Boolean = false,
    val findings: List<CodingValidationFinding> = emptyList(),
)

/** Result of `POST /v1/cockpit/coding/plan` — stage/validate only. */
@Serializable
data class CodingPlanResult(
    val packet: CodingPacket = CodingPacket(),
    val validation: CodingValidation = CodingValidation(),
    val markdown: String = "",
    @SerialName("owner_gate_required") val ownerGateRequired: Boolean = false,
)

/**
 * Result of `POST /v1/cockpit/coding/execute`. When `status` is
 * `approval_required` the job is staged (created, pending the owner phrase);
 * when `dispatched` it ran through the existing gated orchestrator path.
 */
@Serializable
data class CodingExecuteResult(
    val status: String = "",
    val job: CockpitOrchestratorJob? = null,
    val packet: CodingPacket = CodingPacket(),
    @SerialName("worker_id") val workerId: String = "",
    @SerialName("risk_class") val riskClass: String? = null,
    @SerialName("workspace_path") val workspacePath: String? = null,
    @SerialName("model_lane_hint") val modelLaneHint: String? = null,
    @SerialName("verification_plan") val verificationPlan: List<String> = emptyList(),
    @SerialName("authorization_required") val authorizationRequired: Boolean = false,
    @SerialName("authorization_hint") val authorizationHint: String? = null,
    val error: String? = null,
)

/** Minimal orchestrator-job view returned inside coding/execute. */
@Serializable
data class CockpitOrchestratorJob(
    val id: String = "",
    val status: String = "",
    val prompt: String = "",
)

// ─── Evidence (Research Vault) ────────────────────────────────────────────

@Serializable
data class EvidenceArtifact(
    val id: String = "",
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("evidence_strength") val evidenceStrength: String = "",
    val excerpt: String = "",
    val summary: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("freshness_due") val freshnessDue: String? = null,
    @SerialName("added_at") val addedAt: String? = null,
)

@Serializable
data class EvidenceList(val items: List<EvidenceArtifact> = emptyList())
// ─── GraphRAG knowledge graph (contract: /v1/cockpit/graph/*) ──────────────
//
// Mirrors gateway/cockpit/contract.py graph_related_view / graph_answer_view.
// Surfaces related files/sources/decisions on job & evidence screens and the
// dedicated Knowledge Graph screen. Source-backed; nothing fabricated.

/** Bucket a related item falls into (mirrors contract RELATED_KINDS). */
enum class RelatedKind {
    FILE, SOURCE, DECISION, UNKNOWN;

    companion object {
        fun fromWire(value: String?): RelatedKind =
            when (value?.uppercase()) {
                "FILE" -> FILE
                "SOURCE" -> SOURCE
                "DECISION" -> DECISION
                else -> UNKNOWN
            }
    }
}

@Serializable
data class GraphSource(
    val uri: String = "",
    val kind: String = "",
)

@Serializable
data class RelatedItem(
    val kind: String = "FILE",
    @SerialName("node_type") val nodeType: String = "",
    val title: String = "",
    val ref: String = "",
    val relation: String = "related",
    @SerialName("source_backed") val sourceBacked: Boolean = false,
    val sources: List<GraphSource> = emptyList(),
) {
    val bucket: RelatedKind get() = RelatedKind.fromWire(kind)
}

@Serializable
data class RelatedItemList(
    val node: String = "",
    val origin: String = "",
    val related: List<RelatedItem> = emptyList(),
)

@Serializable
data class GraphNode(
    val id: String = "",
    val type: String = "",
    val title: String = "",
    val key: String = "",
)

@Serializable
data class GraphEdge(
    val src: String = "",
    val dst: String = "",
    val type: String = "",
)

@Serializable
data class GraphCommunity(
    val label: String = "",
    val size: Int = 0,
    val relevance: Double = 0.0,
    @SerialName("top_titles") val topTitles: List<String> = emptyList(),
    @SerialName("edge_types") val edgeTypes: Map<String, Int> = emptyMap(),
)

@Serializable
data class GraphAnswer(
    val mode: String = "",
    val question: String = "",
    val nodes: List<GraphNode> = emptyList(),
    val edges: List<GraphEdge> = emptyList(),
    val citations: List<GraphSource> = emptyList(),
    val communities: List<GraphCommunity> = emptyList(),
)

@Serializable
data class GraphBuildResult(
    val saved: String = "",
    val nodes: Int = 0,
    val edges: Int = 0,
    @SerialName("by_node_type") val byNodeType: Map<String, Int> = emptyMap(),
    @SerialName("by_edge_type") val byEdgeType: Map<String, Int> = emptyMap(),
)

// ─── Autonomy (Owner High-Autonomy Coding mode) ───────────────────────────
//
// Mirrors `gateway/cockpit/contract.autonomy_status`. The capability lists
// come straight from `approval_policy.capabilities()` so the Android UI shows
// the policy engine's truth, never a hand-maintained copy.

@Serializable
data class AutonomyCapabilities(
    @SerialName("auto_approved") val autoApproved: List<String> = emptyList(),
    @SerialName("requires_approval") val requiresApproval: List<String> = emptyList(),
    @SerialName("always_deny") val alwaysDeny: List<String> = emptyList(),
    @SerialName("workspace_scoped") val workspaceScoped: List<String> = emptyList(),
)

@Serializable
data class AutonomyStatus(
    val level: String = "assisted",
    @SerialName("display_name") val displayName: String = "Assisted",
    @SerialName("workspace_root") val workspaceRoot: String = "",
    @SerialName("updated_at") val updatedAt: Double = 0.0,
    @SerialName("set_by") val setBy: String = "owner",
    val revocable: Boolean = true,
    val capabilities: AutonomyCapabilities = AutonomyCapabilities(),
)

/** Body for `POST /v1/cockpit/autonomy`. Either set [level] (+ workspace) or [revoke]. */
@Serializable
data class SetAutonomyRequest(
    val level: String? = null,
    @SerialName("workspace_path") val workspacePath: String? = null,
    val revoke: Boolean? = null,
)

@Serializable
data class AutonomyDecision(
    val ts: Double = 0.0,
    val actor: String = "",
    val action: String = "",
    val summary: String = "",
    val decision: String = "",
    val reason: String = "",
)

@Serializable
data class AutonomyDecisionList(
    val decisions: List<AutonomyDecision> = emptyList(),
)

// ─── Ledger timeline (Activity) ───────────────────────────────────────────

/**
 * Wire models for the cockpit *Activity timeline* (`/v1/cockpit/ledger`) —
 * the redacted projection of the orchestrator's per-job event ledger. One
 * row per ledger entry; enum-like fields (`category`, `risk_tier`) are raw
 * Strings mapped to typed domain enums by the repository. Timestamps are
 * ISO-8601 strings. All text is already secret-scrubbed server-side; the
 * repository re-applies `SecretRedactor` as defense in depth.
 */
@Serializable
data class CockpitLedgerEventList(val events: List<CockpitLedgerEvent> = emptyList())

@Serializable
data class CockpitLedgerEvent(
    val id: String,
    @SerialName("job_id") val jobId: String = "",
    val index: Int = 0,
    val timestamp: String = "",
    val category: String = "LIFECYCLE",
    val kind: String = "",
    val worker: String? = null,
    @SerialName("risk_tier") val riskTier: String = "LOW",
    val summary: String = "",
    val files: List<String> = emptyList(),
    @SerialName("has_rollback") val hasRollback: Boolean = false,
    @SerialName("has_evidence") val hasEvidence: Boolean = false,
    @SerialName("has_diff") val hasDiff: Boolean = false,
)

@Serializable
data class CockpitLedgerEventDetail(
    val id: String,
    @SerialName("job_id") val jobId: String = "",
    val index: Int = 0,
    val timestamp: String = "",
    val category: String = "LIFECYCLE",
    val kind: String = "",
    val worker: String? = null,
    @SerialName("risk_tier") val riskTier: String = "LOW",
    val summary: String = "",
    val files: List<String> = emptyList(),
    val payload: kotlinx.serialization.json.JsonObject =
        kotlinx.serialization.json.JsonObject(emptyMap()),
    val evidence: List<CockpitLedgerEvidence> = emptyList(),
    val diff: CockpitLedgerDiff? = null,
    val rollback: CockpitLedgerRollback? = null,
    @SerialName("rollback_available") val rollbackAvailable: Boolean = false,
)

@Serializable
data class CockpitLedgerEvidence(
    val id: String = "",
    val title: String = "",
    val body: String = "",
    @SerialName("source_path") val sourcePath: String? = null,
)

@Serializable
data class CockpitLedgerDiff(
    val body: String? = null,
    val files: List<String> = emptyList(),
)

@Serializable
data class CockpitLedgerRollback(
    val summary: String = "",
    val steps: List<String> = emptyList(),
)

/** POST body for a gated rollback request on a ledger event. */
@Serializable
data class LedgerRollbackRequest(val reason: String? = null)
// ─── Research Mode (Evidence Engine) ──────────────────────────────────────

/**
 * Wire models for Research Mode — one-to-one with the engine's JSON in
 * `gateway/cockpit/contract.py` (`research_report`). Enum-like fields stay raw
 * Strings so an unknown future tier never crashes deserialisation. Nothing
 * here is fabricated: an empty [cards] list with a populated [notes] string is
 * the gateway telling us no source-backed evidence was available.
 */
@Serializable
data class ResearchCard(
    val id: String,
    val title: String = "",
    @SerialName("source_uri") val sourceUri: String = "",
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("evidence_strength") val evidenceStrength: String = "",
    val excerpt: String = "",
    val claim: String = "",
    val relevance: Float = 0f,
    @SerialName("sub_question") val subQuestion: String = "",
)

@Serializable
data class ResearchClaim(
    val text: String = "",
    @SerialName("supporting_card_ids") val supportingCardIds: List<String> = emptyList(),
    val confidence: Float = 0f,
    val uncertainty: String = "",
    @SerialName("sub_question") val subQuestion: String = "",
)

@Serializable
data class ResearchContradiction(
    val subject: String = "",
    @SerialName("claim_a") val claimA: String = "",
    @SerialName("claim_b") val claimB: String = "",
    @SerialName("card_a_id") val cardAId: String = "",
    @SerialName("card_b_id") val cardBId: String = "",
    val reason: String = "",
)

@Serializable
data class ResearchReport(
    val id: String,
    val query: String = "",
    @SerialName("sub_questions") val subQuestions: List<String> = emptyList(),
    val cards: List<ResearchCard> = emptyList(),
    val claims: List<ResearchClaim> = emptyList(),
    val contradictions: List<ResearchContradiction> = emptyList(),
    @SerialName("final_answer") val finalAnswer: String = "",
    val uncertainty: String = "",
    val citations: List<String> = emptyList(),
    val notes: String = "",
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class ResearchReportList(val reports: List<ResearchReport> = emptyList())

/** POST body for `/v1/cockpit/research`. */
@Serializable
data class RunResearchRequest(
    val query: String,
    @SerialName("manual_sources") val manualSources: List<ManualSource> = emptyList(),
)

@Serializable
data class ManualSource(
    val title: String = "",
    val url: String,
    val excerpt: String = "",
)

/** POST body for `/v1/cockpit/research/{id}/promote`. */
@Serializable
data class PromoteFindingRequest(@SerialName("card_id") val cardId: String)

/** Mirrors the gateway's promote/create-memory envelope. */
@Serializable
data class PromoteFindingResponse(
    val stored: Boolean = false,
    val item: CockpitMemoryItem? = null,
    val reason: String? = null,
)

/** POST body for `/v1/cockpit/research/{id}/task`. */
@Serializable
data class CreateResearchTaskRequest(
    val title: String? = null,
    @SerialName("worker_id") val workerId: String? = null,
    @SerialName("workspace_path") val workspacePath: String? = null,
)
